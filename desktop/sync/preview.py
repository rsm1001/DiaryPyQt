"""只读检查服务器同步记录，避免未完成映射时误上传本地数据。"""
from typing import Any, Dict, List

from .client import DiaryServerClient


def preview_remote(client: DiaryServerClient, diaries: List[Dict[str, Any]]) -> Dict[str, int]:
    """逐页读取服务端变更，不推进桌面端游标或修改本地数据库。"""
    cursor = 0
    remote = {}
    changes = 0
    while True:
        page = client.pull(cursor)
        items = page.get("items", [])
        next_cursor = page.get("next_cursor", cursor)
        if items and next_cursor <= cursor:
            raise ValueError("服务端同步游标未前进，已停止检查")
        for item in items:
            change = item.get("change") or {}
            entity_id = change.get("entity_id")
            if not entity_id or change.get("entity_type") != "diary":
                continue
            data = item.get("data")
            if data and not data.get("deleted_at"):
                remote[entity_id] = (str(data.get("date", ""))[:10], data.get("content", ""))
            else:
                remote.pop(entity_id, None)
        changes += len(items)
        cursor = next_cursor
        if not items:
            break

    local_content = {(str(d.get("date", ""))[:10], d.get("content", "")) for d in diaries}
    return {
        "local": len(diaries),
        "remote": len(remote),
        "same_content": sum(value in local_content for value in remote.values()),
        "changes": changes,
    }
