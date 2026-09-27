"""下行变更的纯业务校验；不接触数据库或网络。"""
import hashlib
from typing import Any, Dict, List, Tuple

from .reconcile import canonical_payload, payload_digest


class DownstreamConflict(RuntimeError):
    """变更超出安全更新范围，交由桌面端人工审核。"""


def plan_page(
    items: List[Dict[str, Any]], entries: Dict[str, Dict[str, Any]],
    cursor: int, next_cursor: int,
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """只允许既有映射、无删除且日期未变的日记更新。"""
    if (not isinstance(cursor, int) or not isinstance(next_cursor, int) or cursor < 0
            or (items and next_cursor <= cursor) or (not items and next_cursor != cursor)):
        raise DownstreamConflict("服务端同步游标异常，未修改本地数据")
    by_remote = {entry.get("remote_id"): (local_id, entry) for local_id, entry in entries.items()}
    if len(by_remote) != len(entries):
        raise DownstreamConflict("本地 ID 映射重复或损坏")

    latest = {}
    last_change_cursor = cursor
    for item in items:
        change = item.get("change") or {}
        data = item.get("data") or {}
        change_cursor = change.get("cursor")
        remote_id = change.get("entity_id")
        if (not isinstance(change_cursor, int) or not last_change_cursor < change_cursor <= next_cursor
                or change.get("entity_type") != "diary"):
            raise DownstreamConflict("服务端同步记录无效")
        last_change_cursor = change_cursor
        if change.get("action") != "upsert" or data.get("deleted_at"):
            raise DownstreamConflict("服务器删除待人工审核，未修改本地数据")
        if remote_id not in by_remote or data.get("id") != remote_id:
            raise DownstreamConflict("服务器新日记或 ID 不一致，待人工审核")
        expected = "sha256:" + hashlib.sha256(str(data.get("content", "")).encode("utf-8")).hexdigest()
        if data.get("content_hash") != expected:
            raise DownstreamConflict("服务器日记正文哈希不一致")
        remote_version = data.get("version")
        change_version = change.get("version")
        if (not isinstance(remote_version, int) or not isinstance(change_version, int)
                or remote_version < change_version or change_version < 1):
            raise DownstreamConflict("服务器日记版本信息无效")
        previous = latest.get(remote_id)
        if previous and previous != data:
            raise DownstreamConflict("同一页服务器日记版本不一致")
        latest[remote_id] = data

    if items and last_change_cursor != next_cursor:
        raise DownstreamConflict("服务端同步游标与变更不一致")

    checks = []
    updates = {}
    for remote_id, data in latest.items():
        local_id, saved = by_remote[remote_id]
        baseline = saved.get("payload_hash")
        if not baseline or not saved.get("date") or not isinstance(saved.get("version"), int):
            raise DownstreamConflict("同步映射缺少基线数据")
        payload = canonical_payload(data)
        if payload["date"] != saved["date"]:
            raise DownstreamConflict("服务器日记日期变化待人工审核")
        digest = payload_digest(data)
        if data["version"] < saved["version"]:
            raise DownstreamConflict("服务器日记版本回退")
        if data["version"] == saved["version"] and digest != baseline:
            raise DownstreamConflict("相同版本的日记内容不一致")
        checks.append({"local_id": local_id, "expected_hash": baseline,
                       "payload": payload if digest != baseline else None})
        updates[local_id] = {"version": data["version"], "content_hash": data["content_hash"],
                             "payload_hash": digest}
    return checks, updates
