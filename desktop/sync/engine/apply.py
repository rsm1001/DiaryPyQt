"""下行落地：把已经决策好的服务器变更写进本地库。"""
import logging
from copy import deepcopy
from typing import Any, Callable, Dict

from ..local_repository import LocalDiaryConflict
from ..reconcile import canonical_payload, payload_digest
from ..service import SyncConflict
from .timing import to_desktop_date, to_local_string

logger = logging.getLogger(__name__)


def local_updated_at(data: Dict[str, Any]) -> str:
    """服务器修改时间转桌面本地时间。

    服务器缺时间或格式异常时退回日期零点：需要比时间的场合此前已经
    判成 unknown 并转人工，这里只负责给出确定性的写库值。
    """
    try:
        return to_local_string(data.get("updated_at"))
    except ValueError:
        return to_desktop_date(data.get("date"))


def build_entry(data: Dict[str, Any]) -> Dict[str, Any]:
    """由服务器记录生成同步映射条目。"""
    return {"remote_id": str(data["id"]), "version": int(data["version"]),
            "content_hash": data.get("content_hash"),
            "date": canonical_payload(data)["date"],
            "payload_hash": payload_digest(data),
            "remote_updated_at": data.get("updated_at"),
            "local_updated_at": None}


class RemoteApplier:
    """执行下行：覆盖已映射日记、写入服务器新日记、服务端删除进回收站。"""

    def __init__(self, service, repository, move_to_trash: Callable[[int], Any]) -> None:
        self.service = service
        self.repository = repository
        self.move_to_trash = move_to_trash

    def apply(self, plan, entries, local, before_state, request_id, stats) -> None:
        for key in plan["removed_keys"]:
            entries.pop(key, None)
        # 回收站恢复换了本地 ID 时，把映射改指到新行，旧键在这里失效
        for old_key, new_local_id in plan.get("rekey", {}).items():
            entry = entries.pop(old_key, None)
            if entry is not None:
                entries[str(new_local_id)] = entry

        if plan["apply"]:
            self._apply_updates(plan, local, before_state)
            stats["updated"] += len(plan["apply"])

        for local_id, remote_id, data in plan["resurrect"]:
            payload = canonical_payload(data)
            self.repository.restore_with_local_id(
                local_id, payload, to_desktop_date(data.get("date"), data.get("updated_at")),
                local_updated_at(data))
            local[local_id] = {"id": local_id, "content": payload["content"],
                               "updated_at": local_updated_at(data), "tags": payload["tags"]}
            entries[str(local_id)] = build_entry(data)
            stats["updated"] += 1

        for remote_id, data in plan["insert"]:
            payload = canonical_payload(data)
            unmapped = {lid: row for lid, row in local.items() if str(lid) not in entries}
            new_id = self.repository.adopt_or_create(
                payload, to_desktop_date(data.get("date"), data.get("updated_at")),
                local_updated_at(data), unmapped)
            local[new_id] = {"id": new_id, "content": payload["content"],
                             "updated_at": local_updated_at(data), "tags": payload["tags"]}
            entries[str(new_id)] = build_entry(data)

        for local_id, remote_id in plan["trash"]:
            try:
                self.move_to_trash(local_id)
            except Exception as exc:  # 回收站 2PC 失败时保留映射，下一轮重试
                logger.exception("服务器删除的日记无法移入本地回收站",
                                 extra={"request_id": request_id, "local_id": local_id})
                raise SyncConflict("本地回收站写入失败，本轮停止") from exc
            stats["trashed"] += 1

    def _apply_updates(self, plan, local, before_state) -> None:
        """下行覆盖已映射日记；与游标一起在同一事务提交并写恢复收据。"""
        checks = []
        after = deepcopy(self.service.state)
        after["cursor"] = plan["cursor"]
        for action in plan["apply"]:
            key = str(action.local_id)
            payload = dict(action.payload)
            payload["updated_at"] = local_updated_at(action.remote_data)
            # 期望哈希取本轮开始时的本地内容：冲突覆盖时本地也改过，
            # 用旧基线会让"本地已变更"的防护误报
            checks.append({"local_id": action.local_id,
                           "expected_hash": payload_digest(local[action.local_id]),
                           "payload": payload, "updated_at": payload["updated_at"]})
            after["entries"][key].update({
                "version": action.remote_version,
                "content_hash": action.remote_data.get("content_hash"),
                "date": payload["date"],
                "payload_hash": payload_digest(action.payload),
                "remote_updated_at": action.remote_data.get("updated_at")})
        try:
            self.repository.apply_updates(checks, before_state, after)
        except LocalDiaryConflict as exc:
            raise SyncConflict("本地日记已变更，本轮下行停止且游标未推进") from exc
        self.service.state = after
