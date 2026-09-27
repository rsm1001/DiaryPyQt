"""垃圾桶真实写入处理器及操作工厂。"""
import os
from datetime import datetime
from typing import Any, Callable, Dict, Optional, Protocol

from .contracts import MainDbLike


class TrashOperationHandler(Protocol):
    """单个操作类型在两个数据库中的真实写入策略。"""

    def apply_to_main(
        self,
        cursor: Any,
        diary_id: Optional[int],
        trash_id: Optional[int],
        payload: Dict[str, Any],
    ) -> None: ...

    def apply_to_trash(
        self,
        cursor: Any,
        diary_id: Optional[int],
        trash_id: Optional[int],
        payload: Dict[str, Any],
    ) -> None: ...


class MoveToTrashHandler:
    """处理 move 操作：主库删除，垃圾桶库插入。"""

    def __init__(self, main_db: MainDbLike, clock: Callable[[], str]):
        self._main_db = main_db
        self._clock = clock

    def apply_to_main(
        self,
        cursor: Any,
        diary_id: Optional[int],
        trash_id: Optional[int],
        payload: Dict[str, Any],
    ) -> None:
        del trash_id, payload
        cursor.execute("DELETE FROM diaries WHERE id = ?", (diary_id,))

    def apply_to_trash(
        self,
        cursor: Any,
        diary_id: Optional[int],
        trash_id: Optional[int],
        payload: Dict[str, Any],
    ) -> None:
        del trash_id
        cursor.execute(
            """
            INSERT INTO trash_diaries
            (original_id, date, deleted_at, content, view_count,
             last_viewed_at, source_db_path, tokens, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                diary_id,
                payload['date'],
                self._clock(),
                payload['content'],
                payload.get('view_count', 0),
                payload.get('last_viewed_at'),
                os.path.abspath(self._main_db.db_path),
                payload.get('tokens', ''),
                payload.get('updated_at'),
            ),
        )
        new_trash_id = cursor.lastrowid
        for tag in payload.get('tags', []):
            cursor.execute(
                "INSERT INTO trash_tags "
                "(trash_diary_id, name, original_tag_id) VALUES (?, ?, ?)",
                (new_trash_id, tag['name'], tag.get('original_tag_id')),
            )


class RestoreFromTrashHandler:
    """处理 restore 操作：主库插入，垃圾桶库删除。"""

    def __init__(self, main_db: MainDbLike):
        self._main_db = main_db

    def apply_to_main(
        self,
        cursor: Any,
        diary_id: Optional[int],
        trash_id: Optional[int],
        payload: Dict[str, Any],
    ) -> None:
        del diary_id, trash_id
        cursor.execute(
            """
            INSERT INTO diaries
            (date, content, view_count, last_viewed_at, tokens, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                payload['date'],
                payload['content'],
                payload.get('view_count', 0),
                payload.get('last_viewed_at'),
                payload.get('tokens', ''),
                payload.get('updated_at'),
            ),
        )
        for tag in payload.get('tags', []):
            tag_id = self._resolve_tag_id(tag)
            if tag_id:
                cursor.execute(
                    "INSERT OR IGNORE INTO diary_tags (diary_id, tag_id) "
                    "VALUES (?, ?)",
                    (cursor.lastrowid, tag_id),
                )

    def apply_to_trash(
        self,
        cursor: Any,
        diary_id: Optional[int],
        trash_id: Optional[int],
        payload: Dict[str, Any],
    ) -> None:
        del diary_id, payload
        cursor.execute("DELETE FROM trash_diaries WHERE id = ?", (trash_id,))

    def _resolve_tag_id(self, tag: Dict[str, Any]) -> Optional[int]:
        """优先复用原标签，再按名称复用或创建标签。"""
        original_tag_id = tag.get('original_tag_id')
        if original_tag_id:
            existing = self._main_db.get_tag_by_id(original_tag_id)
            if existing:
                return existing['id']

        name = tag.get('name')
        if not name:
            return None
        existing_by_name = self._main_db.get_tag_by_name(name)
        if existing_by_name:
            return existing_by_name['id']
        new_tag = self._main_db.add_tag(name)
        return new_tag['id'] if new_tag else None


class TrashOperationHandlerFactory:
    """按操作类型创建写入策略，隔离协调器与业务 SQL。"""

    VALID_OP_TYPES = ('move', 'restore')

    def __init__(self, main_db: MainDbLike, clock: Optional[Callable[[], str]] = None):
        timestamp_provider = clock or self._now
        self._handlers: Dict[str, TrashOperationHandler] = {
            'move': MoveToTrashHandler(main_db, timestamp_provider),
            'restore': RestoreFromTrashHandler(main_db),
        }

    def create(self, op_type: str) -> TrashOperationHandler:
        """返回对应策略；未知操作在进入数据库前失败。"""
        try:
            return self._handlers[op_type]
        except KeyError as exc:
            raise ValueError(f"未知 op_type: {op_type!r}") from exc

    @staticmethod
    def _now() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
