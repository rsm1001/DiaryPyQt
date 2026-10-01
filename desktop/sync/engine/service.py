"""日记正文双向同步编排：先拉取落地，再推送本地变更。

顺序固定为"先拉后推"：拉取可能把冲突判给服务器，从而省掉一次注定
失败的推送；而且本轮自己推上去的变更不会出现在本轮的拉取里，下一轮
拉到时摘要必然等于已保存的基线，被短路掉，不会自激。
"""
import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from uuid import NAMESPACE_URL, uuid4, uuid5

from ..reconcile import canonical_payload, payload_digest
from ..service import SyncConflict
from .apply import RemoteApplier
from .conflicts import ConflictJournal
from .planner import (Kind, PlanConflict, build_reverse, decide_local_change,
                      decide_remote_delete, decide_remote_upsert, validate_page)
from .push import PushExecutor
from .timing import now_iso, pick_newer

logger = logging.getLogger(__name__)


def read_status(state_path: Path) -> Dict[str, Any]:
    """只读同步状态，供界面刷新；不联网、不建客户端。"""
    path = Path(state_path)
    if not path.is_file():
        return {"exists": False, "mapped": False, "entries": 0, "cursor": 0, "conflicts": []}
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"exists": True, "mapped": False, "entries": 0, "cursor": 0, "conflicts": [],
                "error": "同步状态文件无法读取"}
    entries = state.get("entries") if isinstance(state.get("entries"), dict) else {}
    conflicts = state.get("conflicts") if isinstance(state.get("conflicts"), list) else []
    return {
        "exists": True,
        "mapped": state.get("mapped") is True,
        "entries": len(entries),
        "cursor": int(state.get("cursor", 0) or 0),
        "last_sync_at": state.get("last_sync_at"),
        "last_sync_stats": state.get("last_sync_stats") or {},
        "conflicts": conflicts,
    }


class BidirectionalSyncService:
    """一轮同步的全部编排；正文改动直接落在主库，因此不需要出站队列。"""

    def __init__(self, sync_service, repository, move_to_trash: Callable[[int], Any], *,
                 backup: Optional[Callable[[], Any]] = None,
                 max_auto_push: int = 50, max_auto_trash: int = 20,
                 max_auto_delete: int = 20, epsilon_seconds: int = 120) -> None:
        self.service = sync_service
        self.repository = repository
        self.move_to_trash = move_to_trash
        self.backup = backup
        self.max_auto_push = max_auto_push
        self.max_auto_trash = max_auto_trash
        self.max_auto_delete = max_auto_delete
        self.epsilon_seconds = epsilon_seconds
        self._server_snapshot: Optional[List[Dict[str, Any]]] = None

    # ------------------------------------------------------------------
    # 主流程
    # ------------------------------------------------------------------
    def sync_round(self, plan_only: bool = False) -> Dict[str, Any]:
        """执行一轮双向同步；plan_only 只预演，不写任何数据。"""
        request_id = str(uuid4())
        entries = self.service.state.get("entries")
        # 全部日记都被删除时映射为空是合法状态，因此只校验结构不校验条数
        if self.service.state.get("mapped") is not True or not isinstance(entries, dict):
            raise SyncConflict("尚未建立一对一映射，禁止自动同步")

        try:
            # 先恢复收据：它会比对内存状态与磁盘状态，任何提前的内存改动都会被判成
            # "状态文件被外部修改"而中止同步
            self.service.recover_receipt(self.repository, request_id)
            self.service.state.setdefault("conflicts", [])
            # 收据恢复会整体替换 state，必须重新取一次 entries 引用
            entries = self.service.state["entries"]
            journal = ConflictJournal(self.service.state)
            # 收据的 before 必须等于磁盘上的状态：崩溃恢复时就是拿它比对磁盘的，
            # 用内存副本会带上本轮新增的冲突日志而被判成"状态不一致"
            before_state = self.service.load_state()
            local = self.repository.snapshot_with_tags()

            def persist() -> None:
                """状态一落盘收据即作废：它的作用域只到"数据库已提交、状态未保存"。"""
                self.service.save_state()
                self.repository.clear_receipt()

            stats: Dict[str, int] = defaultdict(int)
            remote_plan = self._plan_remote(dict(entries), local, journal, stats)
            local_plan = self._plan_local(entries, local, remote_plan)
            self._check_thresholds(local_plan, remote_plan)

            if plan_only:
                stats["planned_push"] = len(local_plan["operations"])
                stats["planned_pull"] = len(remote_plan["apply"]) + len(remote_plan["insert"])
                stats["planned_trash"] = len(remote_plan["trash"])
                return {"plan_only": True, **stats}

            # 首次真正写入前必须先备份：自动同步会改写用户真实日记库，
            # 没有可回滚的快照就不允许动手
            if self.service.state.get("backup_done") is not True:
                if self.backup is None:
                    raise SyncConflict("未配置同步前备份，拒绝写入本地日记")
                self.backup()
                self.service.state["backup_done"] = True

            RemoteApplier(self.service, self.repository, self.move_to_trash).apply(
                remote_plan, entries, local, before_state, request_id, stats)
            # 下行提交同样会替换 state，推送回执必须写进最新的 entries
            entries = self.service.state["entries"]
            PushExecutor(self.service.client, persist, self.epsilon_seconds).execute(
                local_plan["operations"], local_plan["meta"], entries, local, journal, stats)
        except PlanConflict as exc:
            # 服务端数据结构异常属于必须人工介入的情况，统一转成同步冲突
            raise SyncConflict(str(exc)) from exc

        self.service.state["cursor"] = remote_plan["cursor"]
        self.service.state["last_sync_at"] = now_iso()
        self.service.state["last_sync_stats"] = dict(stats)
        persist()
        logger.info("日记内容同步轮完成", extra={"request_id": request_id, **stats})
        return dict(stats)

    def _check_thresholds(self, local_plan, remote_plan) -> None:
        """批量闸门：误判时宁可停下等人工，也不能一次改动大量真实日记。"""
        operations = local_plan["operations"]
        creates = [op for op in operations
                   if op["action"] == "upsert" and op["base_version"] is None]
        if len(creates) > self.max_auto_push:
            raise SyncConflict(
                f"本轮待上传新日记 {len(creates)} 篇，超过自动同步上限 "
                f"{self.max_auto_push}，已停止并等待人工确认")
        # 本地库与映射不匹配时会把整库当成"已删除"推给服务器，必须同样设闸
        deletes = [op for op in operations if op["action"] == "delete"]
        if len(deletes) > self.max_auto_delete:
            raise SyncConflict(
                f"本轮待删除服务器日记 {len(deletes)} 篇，超过自动同步上限 "
                f"{self.max_auto_delete}，已停止并等待人工确认")
        if len(remote_plan["trash"]) > self.max_auto_trash:
            raise SyncConflict(
                f"本轮服务器删除 {len(remote_plan['trash'])} 篇，超过自动同步上限 "
                f"{self.max_auto_trash}，已停止并等待人工确认")

    # ------------------------------------------------------------------
    # 计划：远端 → 本地（不写任何数据）
    # ------------------------------------------------------------------
    def _plan_remote(self, entries, local, journal, stats) -> Dict[str, Any]:
        cursor = int(self.service.state.get("cursor", 0))
        remote_seen: Dict[str, Tuple[Dict[str, Any], Dict[str, Any]]] = {}
        while True:
            page = self.service.client.pull(cursor)
            items = page.get("items") or []
            next_cursor = page.get("next_cursor", cursor)
            for change, data in validate_page(items, cursor, next_cursor):
                remote_seen[str(change["entity_id"])] = (change, data)
            cursor = next_cursor
            if not items:
                break

        reverse = build_reverse(entries)
        plan: Dict[str, Any] = {"cursor": cursor, "apply": [], "insert": [], "resurrect": [],
                                "trash": [], "removed_keys": [], "blocked": set()}
        for remote_id, (change, data) in remote_seen.items():
            key = reverse.get(remote_id)
            local_id = int(key) if key is not None else None
            row = local.get(local_id) if local_id is not None else None

            if change.get("action") == "delete" or (data or {}).get("deleted_at"):
                if key is None:
                    continue
                action = decide_remote_delete(
                    local_id, remote_id, row, (data or {}).get("updated_at"),
                    self.repository.trash_deleted_at(local_id), self.epsilon_seconds)
                if action.kind is Kind.TRASH_LOCAL:
                    journal.append("server_deleted", remote_id=remote_id, local_id=local_id,
                                   local_payload=canonical_payload(row) if row else None,
                                   note="服务器已删除，本地内容留档以便找回")
                    plan["trash"].append((local_id, remote_id))
                # 计划阶段不改真实状态：阈值检查失败时内存与磁盘必须仍然一致
                plan["removed_keys"].append(key)
                local.pop(local_id, None)
                continue

            if not data:
                continue

            if key is None:
                plan["insert"].append((remote_id, data))
                stats["created"] += 1
                continue

            action = decide_remote_upsert(local_id, entries[key], row, data, self.epsilon_seconds)
            if action.kind is Kind.APPLY_REMOTE:
                if action.is_conflict:
                    journal.append("local_overwritten", remote_id=remote_id, local_id=local_id,
                                   local_updated_at=row.get("updated_at"),
                                   remote_updated_at=data.get("updated_at"),
                                   remote_version=data.get("version"),
                                   local_payload=canonical_payload(row),
                                   remote_payload=action.payload,
                                   note="双方都改过，按修改时间取服务器版本；本地旧稿已留档")
                plan["apply"].append(action)
            elif action.kind is Kind.PUSH_LOCAL and row is None:
                # 本地删过、服务器又改过：比较删除时间与服务器修改时间
                deleted_at = self.repository.trash_deleted_at(local_id)
                if pick_newer(deleted_at, data.get("updated_at"),
                              self.epsilon_seconds) == "remote":
                    journal.append("delete_vs_remote_edit", remote_id=remote_id, local_id=local_id,
                                   local_updated_at=deleted_at,
                                   remote_updated_at=data.get("updated_at"),
                                   remote_payload=canonical_payload(data),
                                   note="服务器在本地删除之后又改过，按时间复活本地")
                    plan["resurrect"].append((local_id, remote_id, data))
                    stats["created"] += 1
                # 其余情况保持映射不动，留给推送阶段传播删除
            elif action.kind is Kind.CONFLICT:
                journal.append("timestamp_ambiguous", remote_id=remote_id, local_id=local_id,
                               local_updated_at=row.get("updated_at") if row else None,
                               remote_updated_at=data.get("updated_at"),
                               remote_version=data.get("version"),
                               local_payload=canonical_payload(row) if row else None,
                               remote_payload=canonical_payload(data),
                               note=action.reason)
                # 已转人工的日记本轮两端都不许再动，否则会再撞一次 409
                plan["blocked"].add(local_id)
                stats["conflicts"] += 1
            else:
                stats["noop"] += 1
        return plan

    # ------------------------------------------------------------------
    # 计划：本地 → 远端
    # ------------------------------------------------------------------
    def _plan_local(self, entries, local, remote_plan) -> Dict[str, Any]:
        """汇总本地新增、修改与删除，生成推送操作。"""
        applied = {action.local_id for action in remote_plan["apply"]}
        resurrected = {local_id for local_id, _, _ in remote_plan["resurrect"]}
        adopted = self._adoptable_local_ids(entries, local, remote_plan["insert"])
        blocked = remote_plan["blocked"]
        nodelete = blocked | resurrected

        operations: List[Dict[str, Any]] = []
        meta: Dict[str, Dict[str, Any]] = {}

        # 回收站恢复会给新本地 ID：映射指向的旧行消失，却出现内容完全相同的新行。
        # 这时必须把映射改指到新 ID，既不能当删除传下去，也不能再传一份新日记。
        rekey = self._detect_rekey(entries, local, remote_plan["removed_keys"])
        remote_plan["rekey"] = rekey
        rekeyed_rows = set(rekey.values())

        # 本地删除：映射还在，但主库已经没有这一行
        removed = set(remote_plan["removed_keys"])
        for key, entry in list(entries.items()):
            local_id = int(key)
            # 本轮已判定要复活的日记，绝不能同时又把删除推上去
            if key in removed or key in rekey or local_id in local or local_id in nodelete:
                continue
            remote_id = entry.get("remote_id")
            if not remote_id:
                continue
            operations.append({"entity_type": "diary", "entity_id": remote_id, "action": "delete",
                               "base_version": entry.get("version")})
            meta[remote_id] = {"kind": "delete", "local_id": key}

        for local_id, row in local.items():
            if (local_id in applied or local_id in resurrected or local_id in adopted
                    or local_id in blocked or local_id in rekeyed_rows):
                continue
            key = str(local_id)
            decision = decide_local_change(local_id, entries.get(key), row)
            if decision.kind is Kind.CREATE_LOCAL:
                remote_id = self._resolve_new_remote_id(row, entries)
                operations.append({"entity_type": "diary", "entity_id": remote_id,
                                   "action": "upsert", "base_version": None,
                                   "data": canonical_payload(row)})
                meta[remote_id] = {"kind": "create", "local_id": key,
                                   "payload_hash": payload_digest(row)}
            elif decision.kind is Kind.PUSH_LOCAL:
                entry = entries.get(key)
                if entry is None:
                    continue
                operations.append({"entity_type": "diary", "entity_id": decision.remote_id,
                                   "action": "upsert", "base_version": entry.get("version"),
                                   "data": canonical_payload(row)})
                meta[decision.remote_id] = {"kind": "update", "local_id": key,
                                            "payload_hash": payload_digest(row)}
        return {"operations": operations, "meta": meta}

    def _detect_rekey(self, entries, local, removed_keys) -> Dict[str, int]:
        """识别"回收站恢复换了本地 ID"的映射，返回 旧映射键 -> 新本地 ID。

        判定依据是内容摘要与上次同步的基线完全一致：只有恢复才会出现
        "旧行消失、同时又冒出一行一模一样的新行"。
        """
        removed = set(removed_keys)
        unmapped = {local_id: row for local_id, row in local.items()
                    if str(local_id) not in entries}
        rekey: Dict[str, int] = {}
        for key, entry in entries.items():
            if key in removed or int(key) in local:
                continue
            for local_id, row in unmapped.items():
                if local_id in rekey.values():
                    continue
                if payload_digest(row) == entry.get("payload_hash"):
                    rekey[key] = local_id
                    break
        return rekey

    def _adoptable_local_ids(self, entries, local, inserts) -> set:
        """找出会被"采纳"的本地行，避免刚采纳又反手推一份上去。

        采纳发生在服务器新日记与本地未映射日记内容完全相同时（回收站
        恢复会换本地 ID），此时该行不该再作为"本地新增"上传。
        """
        adopted = set()
        for _, data in inserts:
            payload = canonical_payload(data)
            for local_id, row in local.items():
                if str(local_id) not in entries and canonical_payload(row) == payload:
                    adopted.add(local_id)
        return adopted

    def _resolve_new_remote_id(self, row: Dict[str, Any], entries) -> str:
        """本地新日记的服务器 ID。

        先看服务器上是否已有内容相同、本地却还没映射的日记；没有才用
        确定性的 uuid5 新建，保证同一篇本地日记重跑时 ID 不变。
        """
        payload = canonical_payload(row)
        used = {entry.get("remote_id") for entry in entries.values()}
        for remote in self._get_server_snapshot():
            if remote.get("id") in used or remote.get("deleted_at"):
                continue
            if canonical_payload(remote) == payload:
                return str(remote["id"])
        return str(uuid5(NAMESPACE_URL, f"diarypyqt:{row['id']}"))

    def _get_server_snapshot(self) -> List[Dict[str, Any]]:
        """服务器完整列表按需加载一次。"""
        if self._server_snapshot is None:
            self._server_snapshot = self.service.client.list_all_diaries()
        return self._server_snapshot
