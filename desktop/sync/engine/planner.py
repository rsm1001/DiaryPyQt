"""同步决策的纯逻辑层：不接触数据库和网络。

沿用原先只做"已映射既有日记更新"时的全部防护（游标单调、正文哈希、
版本回退、同页版本一致性），只是把服务器新增与删除从"一律中止"
改成可判定的动作。
"""
import hashlib
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from ..reconcile import canonical_payload, payload_digest
from .timing import pick_newer


class PlanConflict(RuntimeError):
    """服务端数据结构不符合安全同步范围，必须停止本轮并交人工审核。"""


class Kind(str, Enum):
    """单条变更的处置方向。"""

    NOOP = "noop"                    # 摘要一致或无需动作
    APPLY_REMOTE = "apply_remote"    # 用服务器版本覆盖本地
    PUSH_LOCAL = "push_local"        # 保留本地版本，留给推送阶段
    CREATE_LOCAL = "create_local"    # 服务器新日记，写入本地
    TRASH_LOCAL = "trash_local"      # 服务器已删除，本地进回收站
    CONFLICT = "conflict"            # 无法安全判定，转人工


@dataclass(frozen=True)
class Action:
    """一条决策结果；payload 只在下行写入时有值。

    is_conflict 表示"双方都改过、靠时间裁决"，只有这类才需要写冲突日志；
    单纯"本地未改、接受服务器版本"是正常同步，写日志会淹没真正的问题。
    """

    kind: Kind
    local_id: Optional[int] = None
    remote_id: str = ""
    payload: Optional[Dict[str, Any]] = None
    remote_data: Optional[Dict[str, Any]] = None
    remote_version: Optional[int] = None
    reason: str = ""
    is_conflict: bool = False


def validate_remote_data(data: Dict[str, Any], remote_id: str) -> None:
    """服务器正文哈希必须自洽，否则拒绝用它覆盖本地。"""
    if data.get("id") != remote_id:
        raise PlanConflict("服务器日记 ID 不一致")
    expected = "sha256:" + hashlib.sha256(
        str(data.get("content", "")).encode("utf-8")
    ).hexdigest()
    if data.get("content_hash") != expected:
        raise PlanConflict("服务器日记正文哈希不一致")
    version = data.get("version")
    if not isinstance(version, int) or version < 1:
        raise PlanConflict("服务器日记版本信息无效")


def validate_page(items: List[Dict[str, Any]], cursor: int,
                  next_cursor: int) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]:
    """逐页结构性校验，返回 (change, data) 列表。

    这些校验原本就在下行链路里，不能因为支持新增与删除而放宽。
    """
    if (not isinstance(cursor, int) or not isinstance(next_cursor, int) or cursor < 0
            or (items and next_cursor <= cursor) or (not items and next_cursor != cursor)):
        raise PlanConflict("服务端同步游标异常，未修改本地数据")

    collected: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    latest: Dict[str, Dict[str, Any]] = {}
    last_change_cursor = cursor
    for item in items:
        change = item.get("change") or {}
        data = item.get("data") or {}
        change_cursor = change.get("cursor")
        remote_id = change.get("entity_id")
        if (not isinstance(change_cursor, int) or not last_change_cursor < change_cursor <= next_cursor
                or change.get("entity_type") != "diary"):
            raise PlanConflict("服务端同步记录无效")
        last_change_cursor = change_cursor
        action = change.get("action")
        if action not in ("upsert", "delete"):
            raise PlanConflict("服务端同步动作无效")
        if data:
            validate_remote_data(data, remote_id)
        previous = latest.get(remote_id)
        if previous is not None and previous != data:
            raise PlanConflict("同一页服务器日记版本不一致")
        latest[remote_id] = data
        collected.append((change, data))

    if items and last_change_cursor != next_cursor:
        raise PlanConflict("服务端同步游标与变更不一致")
    return collected


def build_reverse(entries: Dict[str, Dict[str, Any]]) -> Dict[str, str]:
    """服务器 ID 反查本地 ID；重复或损坏直接判为映射损坏。"""
    reverse: Dict[str, str] = {}
    for local_id, entry in entries.items():
        remote_id = entry.get("remote_id") if isinstance(entry, dict) else None
        if not isinstance(remote_id, str) or not remote_id:
            raise PlanConflict("同步映射损坏，缺少服务器 ID")
        if remote_id in reverse:
            raise PlanConflict("同步映射重复，无法安全同步")
        reverse[remote_id] = local_id
    return reverse


def _guard_version(entry: Dict[str, Any], data: Dict[str, Any]) -> None:
    """服务器版本回退、或同版本不同内容，都说明服务器数据异常。"""
    saved_version = entry.get("version")
    if not isinstance(saved_version, int):
        return
    if data["version"] < saved_version:
        raise PlanConflict("服务器日记版本回退")
    if data["version"] == saved_version and payload_digest(data) != entry.get("payload_hash"):
        raise PlanConflict("相同版本的日记内容不一致")


def decide_remote_upsert(local_id: int, entry: Dict[str, Any],
                         local_row: Optional[Dict[str, Any]],
                         data: Dict[str, Any], epsilon_seconds: int) -> Action:
    """判断服务器的一条 upsert 该怎么落地。

    摘要一致必须最先短路：既覆盖"双方内容本来就相同"，也覆盖
    "这是我自己刚推上去的回声"，避免把服务器因我而变新的时间戳
    误判成远端冲突。
    """
    remote_id = str(data["id"])
    if entry.get("payload_hash") == payload_digest(data):
        return Action(Kind.NOOP, local_id=local_id, remote_id=remote_id, remote_data=data,
                      remote_version=data["version"], reason="摘要一致（含自我推送回声）")

    # 日期是日记的身份标记，桌面侧没有"改名"语义：静默跟着改会让两边摘要
    # 永久对不上而反复互推，因此一律转人工。
    if entry.get("date") and canonical_payload(data)["date"] != entry["date"]:
        return Action(Kind.CONFLICT, local_id=local_id, remote_id=remote_id, remote_data=data,
                      remote_version=data["version"],
                      reason="服务器日记日期变化，需人工处理", is_conflict=True)

    _guard_version(entry, data)

    if local_row is None:
        # 本地已删除、服务器仍在：留到推送阶段按时间比较决定谁赢
        return Action(Kind.PUSH_LOCAL, local_id=local_id, remote_id=remote_id, remote_data=data,
                      remote_version=data["version"], reason="本地缺失，删除待传播")

    if payload_digest(local_row) == entry.get("payload_hash"):
        return Action(Kind.APPLY_REMOTE, local_id=local_id, remote_id=remote_id,
                      payload=canonical_payload(data), remote_data=data,
                      remote_version=data["version"], reason="本地未改，接受服务器版本")

    verdict = pick_newer(local_row.get("updated_at"), data.get("updated_at"), epsilon_seconds)
    if verdict == "remote":
        return Action(Kind.APPLY_REMOTE, local_id=local_id, remote_id=remote_id,
                      payload=canonical_payload(data), remote_data=data,
                      remote_version=data["version"], reason="双方均改，服务器较新",
                      is_conflict=True)
    if verdict == "local":
        return Action(Kind.PUSH_LOCAL, local_id=local_id, remote_id=remote_id, remote_data=data,
                      remote_version=data["version"], reason="双方均改，本地较新", is_conflict=True)
    return Action(Kind.CONFLICT, local_id=local_id, remote_id=remote_id, remote_data=data,
                  remote_version=data["version"],
                  reason="修改时间相等或不可解析，需人工处理", is_conflict=True)


def decide_remote_delete(local_id: int, remote_id: str,
                         local_row: Optional[Dict[str, Any]],
                         remote_updated_at: Optional[str],
                         local_deleted_at: Optional[str],
                         epsilon_seconds: int) -> Action:
    """服务器软删除：本地编辑得更晚就复活，否则进回收站。

    本地删除时间取自回收站记录；记录已被容量淘汰时取不到，
    此时按"删除优先"处理，并在调用方留冲突日志。
    """
    if local_row is None:
        return Action(Kind.NOOP, local_id=local_id, remote_id=remote_id, reason="本地已无该日记")
    verdict = pick_newer(local_deleted_at, remote_updated_at, epsilon_seconds)
    if verdict == "remote":
        return Action(Kind.PUSH_LOCAL, local_id=local_id, remote_id=remote_id,
                      reason="服务器删除后本地又有编辑，本地版本较新")
    return Action(Kind.TRASH_LOCAL, local_id=local_id, remote_id=remote_id,
                  reason="服务器已删除，本地进回收站")


def decide_local_change(local_id: int, entry: Optional[Dict[str, Any]],
                        local_row: Dict[str, Any]) -> Action:
    """本地新增或修改；摘要没变则无需推送。"""
    if entry is None:
        return Action(Kind.CREATE_LOCAL, local_id=local_id, reason="本地新日记待上传")
    remote_id = str(entry.get("remote_id", ""))
    if payload_digest(local_row) == entry.get("payload_hash"):
        return Action(Kind.NOOP, local_id=local_id, remote_id=remote_id, reason="与上次同步一致")
    return Action(Kind.PUSH_LOCAL, local_id=local_id, remote_id=remote_id, reason="本地已修改待上传")
