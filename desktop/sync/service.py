"""桌面端日记同步状态管理与首次 ID 映射。"""
import json
from copy import deepcopy
import logging
import os
from pathlib import Path
from typing import Any, Dict, List
from uuid import NAMESPACE_URL, uuid4, uuid5

from .client import DiaryServerClient, RemoteApiError
from .downstream import DownstreamConflict, plan_page
from .local_repository import LocalDiaryConflict, LocalDiaryRepository
from .reconcile import MappingPlan, canonical_payload, payload_digest, plan_mapping
from .view_repository import LocalViewRepository, ViewSyncConflict

logger = logging.getLogger(__name__)


class SyncConflict(RuntimeError):
    """存在未处理的服务器变更、歧义或版本冲突时停止写入。"""


class DesktopSyncService:
    """同步状态独立存储；只允许已映射的安全更新下行。"""

    def __init__(self, client: DiaryServerClient, state_path: Path):
        self.client = client
        self.state_path = Path(state_path)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        if not self.state_path.exists():
            return {"cursor": 0, "entries": {}}
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or not isinstance(data.get("entries"), dict):
                raise ValueError("同步状态结构损坏")
            return data
        except (OSError, ValueError) as exc:
            logger.error("桌面同步状态无法读取", extra={"request_id": str(uuid4()), "path": str(self.state_path)})
            raise SyncConflict("同步状态损坏；请先备份并人工处理") from exc

    def _save_state(self) -> None:
        """新状态先写同目录临时文件，避免中断后留下半份映射。"""
        temp_path = self.state_path.with_name(self.state_path.name + "." + uuid4().hex + ".tmp")
        try:
            temp_path.write_text(json.dumps(self.state, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(temp_path, self.state_path)
        finally:
            temp_path.unlink(missing_ok=True)

    def _remote_snapshot(self) -> List[Dict[str, Any]]:
        """从完整列表取活跃日记；增量日志可能缺少历史数据。"""
        try:
            return self.client.list_all_diaries()
        except ValueError as exc:
            raise SyncConflict("服务器分页数据不稳定，已停止映射或上传") from exc

    def plan_initial_mapping(self, diaries: List[Dict[str, Any]]) -> MappingPlan:
        """仅预览唯一匹配；不写同步状态，也不上传日记。"""
        return plan_mapping(diaries, self._remote_snapshot())

    def initialize_mapping(self, diaries: List[Dict[str, Any]]) -> MappingPlan:
        """仅当全部日记一对一匹配且服务端快照稳定时写入新状态。"""
        request_id = str(uuid4())
        if self.state_path.exists():
            raise SyncConflict("已有同步状态，禁止覆盖已有 ID 映射")
        before = self._remote_snapshot()
        plan = plan_mapping(diaries, before)
        if not plan.complete:
            raise SyncConflict("有未匹配或重复日记，需人工核对后再建立 ID 映射")
        after = self._remote_snapshot()
        if sorted(before, key=lambda item: item["id"]) != sorted(after, key=lambda item: item["id"]):
            raise SyncConflict("服务器日记在映射期间发生变化，请重试")
        self.state = {"cursor": 0, "entries": plan.matches, "mapped": True}
        self._save_state()
        logger.info("桌面日记 ID 映射已建立", extra={"request_id": request_id, "mapped": len(plan.matches)})
        return plan

    def build_push_operations(self, diaries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        operations = []
        entries = self.state.setdefault("entries", {})
        for diary in diaries:
            local_id = str(diary["id"])
            remote_id = entries.setdefault(local_id, {}).setdefault(
                "remote_id", str(uuid5(NAMESPACE_URL, f"diarypyqt:{local_id}"))
            )
            digest = payload_digest(diary)
            saved = entries[local_id]
            if saved.get("payload_hash") == digest:
                continue
            operations.append({
                "entity_type": "diary", "entity_id": remote_id, "action": "upsert",
                "base_version": saved.get("version"),
                "data": canonical_payload(diary),
            })
        return operations

    def sync_once(self, diaries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """保留旧手动上传流程；服务端有未落地变更时必须先停止。"""
        request_id = str(uuid4())
        if self.state.get("mapped"):
            raise SyncConflict("已映射日记尚未开放安全上传，请先处理下行与冲突")
        if not self.state.get("mapped") and self._remote_snapshot():
            raise SyncConflict("服务器已有日记但 ID 映射未经验证，禁止上传")
        pending = self.client.pull(int(self.state.get("cursor", 0)))
        if pending.get("items"):
            raise SyncConflict("服务器有未写入本地的变更，已停止上传；同步状态未推进")
        operations = self.build_push_operations(diaries)
        accepted = []
        entries = {entry.get("remote_id"): entry for entry in self.state["entries"].values()}
        payloads = {op["entity_id"]: payload_digest(op["data"]) for op in operations}
        for offset in range(0, len(operations), 100):
            try:
                batch = self.client.push(operations[offset:offset + 100])
            except RemoteApiError as exc:
                if exc.status_code == 409:
                    raise SyncConflict("日记版本冲突，停止上传并人工处理") from exc
                raise
            expected_ids = {op["entity_id"] for op in operations[offset:offset + 100]}
            if ({item.get("entity_id") for item in batch.get("items", [])} != expected_ids
                    or len(batch.get("items", [])) != len(expected_ids)):
                raise SyncConflict("服务器未确认全部上传操作，停止同步")
            for item in batch.get("items", []):
                if item.get("status") != "accepted":
                    raise SyncConflict("日记版本冲突，停止上传并人工处理")
                entry = entries.get(item.get("entity_id"))
                if entry is not None:
                    data = item.get("data") or {}
                    entry["content_hash"] = data.get("content_hash", entry.get("content_hash"))
                    entry["version"] = data.get("version", entry.get("version", 1))
                    entry["payload_hash"] = payloads[item["entity_id"]]
                    entry["date"] = next(op["data"]["date"] for op in operations
                                         if op["entity_id"] == item["entity_id"])
            accepted.extend(batch.get("items", []))
            self._save_state()
        pulled = self.client.pull(int(self.state.get("cursor", 0)))
        accepted_data = {item["entity_id"]: item.get("data") or {} for item in accepted}
        for item in pulled.get("items", []):
            change = item.get("change") or {}
            remote_id = change.get("entity_id")
            data = item.get("data") or {}
            acknowledged = accepted_data.get(remote_id)
            if (acknowledged is None or change.get("action") != "upsert"
                    or data.get("version") != acknowledged.get("version")
                    or data.get("content_hash") != acknowledged.get("content_hash")
                    or payload_digest(data) != payloads[remote_id]):
                raise SyncConflict("服务器存在其他设备的变更，未推进同步游标")
        self.state["cursor"] = pulled.get("next_cursor", self.state.get("cursor", 0))
        self._save_state()
        logger.info("桌面手动上传完成", extra={"request_id": request_id, "pushed": len(accepted)})
        return {"pushed": accepted, "pulled": pulled.get("items", [])}

    def _recover_receipt(self, repository: LocalDiaryRepository, request_id: str) -> None:
        """SQLite 已提交而 JSON 未写成功时，按收据恢复游标。"""
        if self._load_state() != self.state:
            raise SyncConflict("同步状态文件已被其他进程修改，请人工审核")
        try:
            receipt = repository.read_receipt()
        except LocalDiaryConflict as exc:
            raise SyncConflict("本地同步恢复记录损坏，请人工审核") from exc
        if receipt is None:
            return
        before = receipt["before_state"]
        after = receipt["after_state"]
        if self.state == after:
            return
        if self.state != before:
            raise SyncConflict("SQLite 与同步状态不一致，请人工审核")
        try:
            repository.verify_targets(receipt["targets"])
        except LocalDiaryConflict as exc:
            raise SyncConflict("本地数据在恢复前发生变化，请人工审核") from exc
        self.state = after
        try:
            self._save_state()
        except OSError as exc:
            self.state = before
            logger.exception("桌面同步游标恢复失败", extra={"request_id": request_id})
            raise SyncConflict("本地同步游标恢复失败，未继续拉取") from exc
        logger.info("桌面同步游标已从 SQLite 收据恢复", extra={"request_id": request_id,
                                                     "cursor": after["cursor"]})

    def sync_views(self, repository: LocalViewRepository) -> Dict[str, int]:
        """先补服务器缺失的电脑历史，再幂等同步两端新增查看。"""
        request_id = str(uuid4())
        if not self.state_path.exists() or self.state.get("mapped") is not True:
            raise SyncConflict("上传查看基线前必须确认 ID 映射")
        before = deepcopy(self.state)
        entries = before.get("entries", {})
        if not isinstance(entries, dict) or not entries:
            raise SyncConflict("同步映射为空")
        remote_ids = [entry.get("remote_id") for entry in entries.values() if isinstance(entry, dict)]
        if (len(remote_ids) != len(entries) or len(set(remote_ids)) != len(entries)
                or any(not isinstance(remote_id, str) or not remote_id for remote_id in remote_ids)):
            raise SyncConflict("同步映射损坏")

        def mapped_snapshot() -> Dict[str, Dict[str, Any]]:
            remote = self._remote_snapshot()
            by_id = {item.get("id"): item for item in remote}
            if len(remote) != len(by_id) or any(remote_id not in by_id for remote_id in remote_ids):
                raise SyncConflict("服务器列表不完整或有重复日记")
            return {remote_id: by_id[remote_id] for remote_id in remote_ids}

        def mapped_rows(snapshot: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
            rows = []
            for local_id, entry in entries.items():
                data = snapshot[entry["remote_id"]]
                if (not isinstance(local_id, str) or not local_id.isdecimal()
                        or not entry.get("date") or data.get("deleted_at")
                        or str(data.get("date", ""))[:10] != entry["date"]):
                    raise SyncConflict("映射日记已删除或日期变化，需人工审核")
                rows.append({"local_id": int(local_id), "remote_id": entry["remote_id"],
                             "date": entry["date"], "view_count": data.get("view_count"),
                             "last_viewed_at": data.get("last_viewed_at")})
            return rows

        first = mapped_snapshot()
        if first != mapped_snapshot() or self._load_state() != before:
            raise SyncConflict("服务器或本地映射在读取期间变化，请重试")
        preliminary = mapped_rows(first)
        self.client.require_idempotent_views()
        try:
            baselines = repository.prepare_baselines(preliminary)
        except ViewSyncConflict as exc:
            raise SyncConflict("电脑初始查看数据与映射冲突，未上传") from exc
        for baseline in baselines:
            self.client.import_view_baseline(
                baseline["remote_id"], baseline["source_id"],
                baseline["view_count"], baseline["last_viewed_at"],
            )
            repository.acknowledge_baseline(baseline["source_id"])
        pending = repository.read_pending()
        for event in pending:
            entry = entries.get(str(event["local_id"]))
            if entry is None:
                raise SyncConflict("待同步查看事件没有经确认的 ID 映射")
            self.client.record_view(entry["remote_id"], event["event_id"], event["viewed_at"])
        first = mapped_snapshot()
        if first != mapped_snapshot() or self._load_state() != before:
            raise SyncConflict("服务器查看记录或同步映射在读取期间变化，请重试")
        try:
            result = repository.merge(mapped_rows(first), acknowledged=pending)
        except ViewSyncConflict as exc:
            raise SyncConflict("服务器与电脑查看记录冲突，未清理待同步队列") from exc
        result["baseline_count"] = sum(item["view_count"] for item in baselines)
        logger.info("桌面查看历史上传与新事件同步完成", extra={"request_id": request_id, **result})
        return result

    def pull_once(self, repository: LocalDiaryRepository) -> Dict[str, int]:
        """逐页落地已映射的正文/标签更新，优先恢复未完成的游标写入。"""
        request_id = str(uuid4())
        if not self.state_path.exists() or self.state.get("mapped") is not True:
            raise SyncConflict("下行前必须完成并保存首次 ID 映射")
        self._recover_receipt(repository, request_id)
        applied = 0
        pages = 0
        while True:
            cursor = int(self.state.get("cursor", 0))
            page = self.client.pull(cursor)
            items = page.get("items", [])
            next_cursor = page.get("next_cursor", cursor)
            try:
                checks, updates = plan_page(items, self.state["entries"], cursor, next_cursor)
            except DownstreamConflict as exc:
                logger.warning("桌面日记下行需人工审核", extra={"request_id": request_id, "cursor": cursor})
                raise SyncConflict("服务器变更需人工审核；未覆盖本地数据") from exc
            if not items:
                break
            before = deepcopy(self.state)
            after = deepcopy(before)
            for local_id, entry_updates in updates.items():
                after["entries"][local_id].update(entry_updates)
            after["cursor"] = next_cursor
            if self._load_state() != before:
                raise SyncConflict("同步状态在分页期间被修改，拒绝写入本地数据")
            try:
                changed = repository.apply_updates(checks, before, after)
            except LocalDiaryConflict as exc:
                raise SyncConflict("本地日记已变更，下行停止且游标未推进") from exc
            self.state = after
            try:
                self._save_state()
            except OSError as exc:
                self.state = before
                logger.exception("本地更新已提交但同步状态保存失败", extra={"request_id": request_id})
                raise SyncConflict("游标未保存；下次下行会尝试从 SQLite 恢复") from exc
            applied += changed
            pages += 1
            logger.info("桌面日记下行页完成", extra={"request_id": request_id,
                                                 "cursor": next_cursor, "updated": changed})
        return {"applied": applied, "pages": pages, "cursor": int(self.state["cursor"])}