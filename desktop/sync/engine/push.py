"""上行推送：分批发送本地变更，并在版本冲突时逐条降级。"""
import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional

from ..client import RemoteApiError
from ..reconcile import canonical_payload
from ..service import SyncConflict
from .apply import build_entry
from .timing import pick_newer

logger = logging.getLogger(__name__)

BATCH_SIZE = 100
MAX_PUSH_RETRIES = 2


class PushExecutor:
    """把本地新增、修改、删除推给服务器。

    服务器遇冲突会中断整批，因此冲突必须先用 server_data 定位到具体
    实体，再决定是重推、撤销，还是留档等人工处理。
    """

    def __init__(self, client, save_state, epsilon_seconds: int) -> None:
        self.client = client
        self.save_state = save_state
        self.epsilon_seconds = epsilon_seconds

    def execute(self, operations, meta, entries, local, journal, stats) -> None:
        queue = list(operations)
        retries: Dict[str, int] = defaultdict(int)
        guard_limit = len(operations) * (MAX_PUSH_RETRIES + 2) + BATCH_SIZE
        guard = 0
        while queue:
            guard += 1
            if guard > guard_limit:
                raise SyncConflict("推送重试次数异常，已停止同步")
            batch, queue = queue[:BATCH_SIZE], queue[BATCH_SIZE:]
            try:
                response = self.client.push(batch)
            except RemoteApiError as exc:
                if exc.status_code != 409:
                    raise
                conflict_op = self._locate_conflict(exc, batch)
                entity_id = conflict_op["entity_id"]
                retries[entity_id] += 1
                if retries[entity_id] > MAX_PUSH_RETRIES:
                    journal.append("push_rejected", remote_id=entity_id,
                                   local_id=(meta.get(entity_id) or {}).get("local_id"),
                                   remote_payload=(exc.details or {}).get("server_data"),
                                   note="服务器版本持续冲突，已跳过等待人工处理")
                    stats["conflicts"] += 1
                    queue = [op for op in batch if op is not conflict_op] + queue
                    continue
                replacement = self._resolve_conflict(conflict_op, exc, meta, local, journal, stats)
                # 之前已发送成功的操作由服务器幂等保护，可以安全重排
                queue = ([op for op in batch if op is not conflict_op] + queue
                         + ([replacement] if replacement else []))
                continue

            for item in response.get("items", []):
                if item.get("status") != "accepted":
                    raise SyncConflict("服务器未确认全部上传操作，本轮停止")
                self._ack(item, meta, entries)
                stats["pushed"] += 1
            self.save_state()

    @staticmethod
    def _locate_conflict(exc: RemoteApiError, batch: List[Dict[str, Any]]) -> Dict[str, Any]:
        """批量推送遇冲突会整批中断，必须用 server_data 定位是哪一条。"""
        server_data = (exc.details or {}).get("server_data")
        if not isinstance(server_data, dict) or not server_data.get("id"):
            raise SyncConflict("服务器版本冲突且未返回可核对数据，已停止")
        for operation in batch:
            if operation["entity_id"] == server_data["id"]:
                return operation
        raise SyncConflict("服务器冲突实体不在本批操作内，已停止")

    def _resolve_conflict(self, operation, exc, meta, local, journal, stats) -> Optional[Dict]:
        """按"修改时间较新者优先"处理冲突；无法判定时不覆盖、只留档。"""
        server_data = (exc.details or {}).get("server_data") or {}
        entity_id = operation["entity_id"]
        local_id_text = (meta.get(entity_id) or {}).get("local_id")
        local_row = local.get(int(local_id_text)) if local_id_text else None

        if operation["action"] == "delete":
            journal.append("delete_vs_remote_edit", remote_id=entity_id,
                           local_id=local_id_text, remote_version=server_data.get("version"),
                           remote_payload=canonical_payload(server_data),
                           note="服务器在本地删除后又改过，内容留档后重试删除")
            return {**operation, "base_version": server_data.get("version")}

        verdict = pick_newer((local_row or {}).get("updated_at"), server_data.get("updated_at"),
                             self.epsilon_seconds)
        if verdict == "local":
            journal.append("local_overwritten", remote_id=entity_id, local_id=local_id_text,
                           remote_updated_at=server_data.get("updated_at"),
                           remote_payload=canonical_payload(server_data),
                           note="推送冲突，本地较新；服务器版本已留档后重推")
            return {**operation, "base_version": server_data.get("version")}

        journal.append("push_rejected", remote_id=entity_id, local_id=local_id_text,
                       remote_updated_at=server_data.get("updated_at"),
                       remote_version=server_data.get("version"),
                       local_payload=canonical_payload(local_row) if local_row else None,
                       remote_payload=canonical_payload(server_data),
                       note="推送冲突且服务器不落后，保留服务器版本，撤销本次上传")
        stats["conflicts"] += 1
        return None

    @staticmethod
    def _ack(item: Dict[str, Any], meta: Dict[str, Any], entries: Dict[str, Any]) -> None:
        """按服务器回执更新基线，保证下一轮不会把自己的推送当成远端变更。"""
        info = meta.get(item["entity_id"])
        if info is None:
            return
        key = info["local_id"]
        if info["kind"] == "delete":
            entries.pop(key, None)
            return
        data = item.get("data") or {}
        if not data:
            return
        if key not in entries:
            entries[key] = build_entry(data)
        else:
            entries[key].update({"version": int(data["version"]),
                                 "content_hash": data.get("content_hash"),
                                 "date": canonical_payload(data)["date"],
                                 "payload_hash": info["payload_hash"],
                                 "remote_updated_at": data.get("updated_at")})
