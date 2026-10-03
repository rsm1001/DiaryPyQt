"""日记业务服务。"""
from datetime import datetime, timezone
import hashlib
from typing import Any, Dict, List, Optional
from uuid import uuid4

from server.repository import DiaryRepository
from server.schemas import DiaryCreate, DiaryUpdate


class ServiceError(Exception):
    """业务异常：携带错误码、对外中文文案和 HTTP 状态码。"""

    def __init__(self, code: str, message: str, status_code: int, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


def utc_now() -> str:
    """返回当前 UTC 时间的 ISO8601 字符串（带 Z 后缀）。"""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def content_hash(content: str) -> str:
    """计算正文的 sha256 内容哈希，供三端校验一致性。"""
    return f"sha256:{hashlib.sha256(content.encode('utf-8')).hexdigest()}"


def validate_date(value: str) -> str:
    """校验日期必须是 YYYY-MM-DD，客户端传来的时间戳不能直接落库。"""
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise ServiceError("INVALID_DIARY_DATE", "日记日期必须是 YYYY-MM-DD 格式", 400) from exc
    return value


def normalize_tags(tags: List[str]) -> List[str]:
    """标签去空、去重并排序，保证三端比较结果一致。"""
    return sorted(set(tag.strip() for tag in tags if tag.strip()))


class DiaryService:
    """日记业务服务：负责校验、版本控制和同步变更记录。"""

    def __init__(self, repository: DiaryRepository, sync_repository: Any = None):
        self.repository = repository
        self.sync_repository = sync_repository

    def _record_change(self, record: Dict[str, Any], action: str) -> None:
        if self.sync_repository is not None:
            self.sync_repository.record_change(
                "diary", record["id"], action, record["version"], record["updated_at"]
            )

    def list_diaries(self, include_deleted: bool, limit: int, offset: int) -> List[Dict[str, Any]]:
        return self.repository.list_diaries(include_deleted, limit, offset)

    def get_diary(self, diary_id: str) -> Dict[str, Any]:
        record = self.repository.get(diary_id)
        if not record or record["deleted_at"]:
            raise ServiceError("DIARY_NOT_FOUND", "日记不存在", 404)
        return record

    def create_diary(self, payload: DiaryCreate) -> Dict[str, Any]:
        return self.create_diary_with_id(str(uuid4()), payload)

    def create_diary_with_id(self, diary_id: str, payload: DiaryCreate) -> Dict[str, Any]:
        content = payload.content.strip()
        if not content:
            raise ServiceError("EMPTY_DIARY_CONTENT", "日记正文不能为空", 400)
        now = utc_now()
        record = {
            "id": diary_id,
            "date": validate_date(payload.date),
            "content": content,
            "content_hash": content_hash(content),
            "version": 1,
            "tags": normalize_tags(payload.tags),
            "created_at": now,
            "updated_at": now,
            "deleted_at": None,
        }
        result = self.repository.create(record)
        self._record_change(result, "upsert")
        return result

    def update_diary(self, diary_id: str, payload: DiaryUpdate) -> Dict[str, Any]:
        current = self.get_diary(diary_id)
        if payload.version is not None and payload.version != current["version"]:
            raise ServiceError("DIARY_VERSION_CONFLICT", "日记版本冲突", 409,
                               {"server_version": current["version"]})
        if payload.date is None and payload.content is None and payload.tags is None:
            raise ServiceError("EMPTY_DIARY_UPDATE", "更新内容不能为空", 400)
        content = current["content"] if payload.content is None else payload.content.strip()
        if not content:
            raise ServiceError("EMPTY_DIARY_CONTENT", "日记正文不能为空", 400)
        record = {
            "date": current["date"] if payload.date is None else validate_date(payload.date),
            "content": content,
            "content_hash": content_hash(content),
            "tags": current["tags"] if payload.tags is None else normalize_tags(payload.tags),
            "updated_at": utc_now(),
        }
        if not self.repository.update(diary_id, record, current["version"]):
            raise ServiceError("DIARY_VERSION_CONFLICT", "日记版本冲突", 409)
        result = self.get_diary(diary_id)
        self._record_change(result, "upsert")
        return result

    def delete_diary(self, diary_id: str, version: Optional[int]) -> None:
        current = self.get_diary(diary_id)
        if version is not None and version != current["version"]:
            raise ServiceError("DIARY_VERSION_CONFLICT", "日记版本冲突", 409,
                               {"server_version": current["version"]})
        deleted_at = utc_now()
        if not self.repository.delete(diary_id, deleted_at, current["version"]):
            raise ServiceError("DIARY_VERSION_CONFLICT", "日记版本冲突", 409)
        self._record_change(
            {"id": diary_id, "version": current["version"] + 1, "updated_at": deleted_at}, "delete"
        )

    def record_view(self, diary_id: str, event_id: Optional[str] = None,
                    viewed_at: Optional[datetime] = None) -> Dict[str, Any]:
        self.get_diary(diary_id)
        if viewed_at is not None and viewed_at.tzinfo is None:
            raise ServiceError("INVALID_VIEW_TIME", "查看时间必须包含时区", 422)
        timestamp = viewed_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") if viewed_at else utc_now()
        try:
            return self.repository.record_view(diary_id, timestamp, event_id)
        except ValueError as error:
            raise ServiceError("VIEW_EVENT_CONFLICT", "查看事件 ID 已用于其他日记", 409) from error

    def import_view_baseline(self, diary_id: str, source_id: str, count: int,
                             viewed_at: Optional[datetime]) -> Dict[str, Any]:
        self.get_diary(diary_id)
        if (count > 0 and viewed_at is None) or (count == 0 and viewed_at is not None):
            raise ServiceError("INVALID_VIEW_BASELINE", "查看次数与时间不一致", 422)
        if viewed_at is not None and viewed_at.tzinfo is None:
            raise ServiceError("INVALID_VIEW_TIME", "查看时间必须包含时区", 422)
        timestamp = (viewed_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
                     if viewed_at else None)
        try:
            return self.repository.import_view_baseline(diary_id, source_id, count, timestamp)
        except ValueError as error:
            raise ServiceError("VIEW_BASELINE_CONFLICT", "历史查看基线已导入且与本次不同", 409) from error

    def view_statistics(self) -> Dict[str, Any]:
        return self.repository.view_statistics()

    def list_deleted(self, limit: int, offset: int) -> List[Dict[str, Any]]:
        return self.repository.list_deleted_diaries(limit, offset)

    def restore_diary(self, diary_id: str, version: Optional[int]) -> Dict[str, Any]:
        result = self.repository.restore(diary_id, version)
        if result is None:
            raise ServiceError("DIARY_RESTORE_CONFLICT", "日记恢复冲突，版本不匹配", 409)
        self._record_change(result, "upsert")
        return result

    def permanently_delete_diary(self, diary_id: str, version: Optional[int] = None) -> None:
        if not self.repository.permanently_delete(diary_id, version):
            if version is not None:
                raise ServiceError("DIARY_TRASH_VERSION_CONFLICT", "回收站日记版本已变化，请刷新后重试", 409)
            raise ServiceError("DIARY_TRASH_NOT_FOUND", "回收站中不存在该日记", 404)

    def list_tags(self) -> List[Dict[str, Any]]:
        return self.repository.list_tags()

    def create_tag(self, name: str) -> Dict[str, Any]:
        try:
            return self.repository.create_tag(name)
        except ValueError as exc:
            raise ServiceError("INVALID_TAG_NAME", "标签名无效", 400) from exc

    def update_tag(self, tag_id: str, name: str) -> Dict[str, Any]:
        try:
            result = self.repository.update_tag(tag_id, name)
        except ValueError as exc:
            # 仓储层用两种文案区分“重名”与“空名”，必须按精确文案分流，
            # 否则空标签名会被误报成 409 重名。
            if "已存在" in str(exc):
                raise ServiceError("TAG_NAME_EXISTS", "标签名已存在", 409) from exc
            raise ServiceError("INVALID_TAG_NAME", "标签名无效", 400) from exc
        if result is None:
            raise ServiceError("TAG_NOT_FOUND", "标签不存在", 404)
        return result

    def delete_tag(self, tag_id: str) -> None:
        if self.repository.delete_tag(tag_id):
            return
        if self.repository.get_tag(tag_id) is None:
            raise ServiceError("TAG_NOT_FOUND", "标签不存在", 404)
        raise ServiceError("TAG_IN_USE", "标签仍在使用中，无法删除", 409)
