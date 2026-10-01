"""日记同步业务服务。"""
from typing import Any, Dict, List

from server.schemas import DiaryCreate, DiaryUpdate
from server.service import DiaryService, ServiceError, normalize_tags
from server.sync.repository import SyncRepository


class SyncService:
    """处理日记增量同步和播放记录。"""

    def __init__(self, diary_service: DiaryService, repository: SyncRepository):
        self.diary_service = diary_service
        self.repository = repository

    def pull(self, cursor: int, limit: int) -> Dict[str, Any]:
        changes = self.repository.pull_changes(cursor, limit)
        items = []
        next_cursor = cursor
        for change in changes:
            data = self.diary_service.repository.get(change["entity_id"])
            items.append({"change": change, "data": data})
            next_cursor = max(next_cursor, change["cursor"])
        return {"items": items, "next_cursor": next_cursor}

    def push(self, operations: List[Dict[str, Any]]) -> Dict[str, Any]:
        results = []
        for operation in operations:
            if operation.get("entity_type") != "diary":
                raise ServiceError("UNSUPPORTED_SYNC_ENTITY", "不支持的同步实体", 400)
            entity_id = operation["entity_id"]
            action = operation["action"]
            data = operation.get("data") or {}
            current = self.diary_service.repository.get(entity_id)
            base_version = operation.get("base_version")
            if action == "delete" and current and current["deleted_at"]:
                results.append({"entity_id": entity_id, "status": "accepted"})
                continue
            if current and action == "upsert":
                incoming_content = str(data.get("content", "")).strip()
                same_payload = (
                    data.get("date") == current["date"]
                    and incoming_content == current["content"]
                    and normalize_tags(data.get("tags") or []) == current["tags"]
                )
                if same_payload and base_version != current["version"]:
                    results.append({"entity_id": entity_id, "status": "accepted", "data": current})
                    continue
                if base_version is None and not same_payload:
                    raise ServiceError(
                        "DIARY_VERSION_CONFLICT", "该 ID 已被其他内容占用", 409,
                        {"server_version": current["version"], "server_data": current},
                    )
            if current and base_version is not None and current["version"] != base_version:
                raise ServiceError(
                    "DIARY_VERSION_CONFLICT",
                    "日记版本冲突",
                    409,
                    {"server_version": current["version"], "server_data": current},
                )
            if action == "delete":
                if current and not current["deleted_at"]:
                    self.diary_service.delete_diary(entity_id, base_version)
                results.append({"entity_id": entity_id, "status": "accepted"})
                continue
            if action != "upsert":
                raise ServiceError("INVALID_SYNC_ACTION", "无效的同步操作", 400)
            if current is None:
                result = self.diary_service.create_diary_with_id(entity_id, DiaryCreate(**data))
            else:
                result = self.diary_service.update_diary(
                    entity_id,
                    DiaryUpdate(
                        date=data.get("date"),
                        content=data.get("content"),
                        tags=data.get("tags"),
                        version=base_version,
                    ),
                )
            results.append({"entity_id": entity_id, "status": "accepted", "data": result})
        return {"items": results}

    def save_playback(self, record: Dict[str, Any]) -> Dict[str, Any]:
        if record["round_number"] not in (1, 2):
            raise ServiceError("INVALID_PLAYBACK_ROUND", "播放轮次必须是 1 或 2", 400)
        if record["status"] not in {"playing", "paused", "waiting", "completed", "skipped"}:
            raise ServiceError("INVALID_PLAYBACK_STATUS", "无效的播放状态", 400)
        self.diary_service.get_diary(record["diary_id"])
        return self.repository.save_playback(record)
