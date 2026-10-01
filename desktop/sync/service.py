"""桌面端日记同步状态管理、首次 ID 映射与查看记录同步。"""
import json
from copy import deepcopy
import logging
import os
from pathlib import Path
from typing import Any, Dict, List
from uuid import uuid4

from .client import DiaryServerClient
from .local_repository import LocalDiaryConflict, LocalDiaryRepository
from .reconcile import MappingPlan, plan_mapping
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

    def recover_receipt(self, repository: LocalDiaryRepository,
                        request_id: str = None) -> None:
        """对外入口：从 SQLite 收据补写丢失的游标（供自动同步引擎复用）。"""
        self._recover_receipt(repository, request_id or str(uuid4()))

    def save_state(self) -> None:
        """对外入口：原子保存同步状态与冲突日志。"""
        self._save_state()

    def load_state(self) -> Dict[str, Any]:
        """对外入口：重新从磁盘读取状态，用于生成可恢复的收据基线。"""
        return self._load_state()

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

