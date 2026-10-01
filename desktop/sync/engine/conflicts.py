"""冲突日志：自动同步判给某一方时，把双方内容都留档，保证不丢数据。"""
import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .timing import now_iso

logger = logging.getLogger(__name__)

MAX_ENTRIES = 500


class ConflictJournal:
    """把冲突写入同步状态文件，与状态一起原子落盘。"""

    def __init__(self, state: Dict[str, Any], limit: int = MAX_ENTRIES):
        self._state = state
        self._limit = limit

    def append(self, kind: str, *, remote_id: str = "", local_id: Optional[int] = None,
               local_updated_at: Optional[str] = None, remote_updated_at: Optional[str] = None,
               remote_version: Optional[int] = None, local_payload: Optional[Dict[str, Any]] = None,
               remote_payload: Optional[Dict[str, Any]] = None, note: str = "") -> Dict[str, Any]:
        """记录一条冲突；双方正文都必须完整保留，便于人工找回。"""
        entries: List[Dict[str, Any]] = self._state.setdefault("conflicts", [])
        record = {
            "id": str(uuid4()),
            "at": now_iso(),
            "kind": kind,
            "local_id": local_id,
            "remote_id": remote_id,
            "local_updated_at": local_updated_at,
            "remote_updated_at": remote_updated_at,
            "remote_version": remote_version,
            "local_payload": local_payload,
            "remote_payload": remote_payload,
            "note": note,
        }
        entries.append(record)
        # 只在用户长期不清理时才会触发，丢弃最旧记录并留痕
        overflow = len(entries) - self._limit
        if overflow > 0:
            del entries[:overflow]
            logger.warning("冲突日志超出上限，已丢弃最旧 %d 条", overflow,
                           extra={"request_id": str(uuid4())})
        return record

    def entries(self) -> List[Dict[str, Any]]:
        return list(self._state.get("conflicts", []))

    def clear(self) -> None:
        self._state["conflicts"] = []
