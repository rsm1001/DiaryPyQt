"""pending_trash_ops 的跨库持久化适配器。"""
import logging
from typing import Any, Callable, Dict, List, Tuple

from ..connection import TrashConnectionPool
from .contracts import MainDbLike, PendingOperation

logger = logging.getLogger(__name__)

_INSERT_PENDING_SQL = """
INSERT INTO pending_trash_ops
(op_id, op_type, diary_id, trash_id, payload, state, created_at, updated_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?)
"""
_MIRROR_PENDING_SQL = """
INSERT OR REPLACE INTO pending_trash_ops
(op_id, op_type, diary_id, trash_id, payload, state, created_at, updated_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?)
"""
_SELECT_PENDING_SQL = """
SELECT op_id, op_type, diary_id, trash_id, payload, state, created_at, updated_at
FROM pending_trash_ops
"""


class PendingOperationStore:
    """封装两库 pending_trash_ops 的读写和镜像。"""

    def __init__(self, connection_pool: TrashConnectionPool, main_db: MainDbLike):
        self._pool = connection_pool
        self._main_db = main_db

    def create(self, operation: PendingOperation) -> None:
        """阶段一：先写主库，再写垃圾桶库的 pending 记录。"""
        values = operation.to_database_values()
        with self._main_db._transaction() as cursor:
            cursor.execute(_INSERT_PENDING_SQL, values)
        self._write_trash(_INSERT_PENDING_SQL, values)

    def apply_main_phase(
        self,
        callback: Callable[[Any], None],
        op_id: str,
        updated_at: str,
    ) -> None:
        """在同一主库事务内完成真实写入与 applied 状态更新。"""
        with self._main_db._transaction() as cursor:
            callback(cursor)
            self._update_state(cursor, op_id, 'applied', updated_at)

    def commit_trash_phase(
        self,
        callback: Callable[[Any], None],
        op_id: str,
        updated_at: str,
    ) -> None:
        """在同一垃圾桶事务内完成真实写入与 committed 状态更新。"""
        with self._pool.lock:
            with self._pool.transaction() as cursor:
                callback(cursor)
                self._update_state(cursor, op_id, 'committed', updated_at)

    def mark_trash_applied(self, op_id: str, updated_at: str) -> None:
        """同步阶段二状态到垃圾桶库。"""
        self._update_trash_state(op_id, 'applied', updated_at)

    def mark_main_committed(self, op_id: str, updated_at: str) -> None:
        """同步阶段三状态到主库。"""
        self._update_main_state(op_id, 'committed', updated_at)

    def cleanup(self, op_id: str) -> None:
        """尽力清理两库 pending 记录，单侧失败不阻断另一侧。"""
        try:
            with self._main_db._transaction() as cursor:
                cursor.execute("DELETE FROM pending_trash_ops WHERE op_id = ?", (op_id,))
        except Exception:
            self._log_warning("清理主库 pending 失败", op_id, exc_info=True)

        try:
            self._write_trash("DELETE FROM pending_trash_ops WHERE op_id = ?", (op_id,))
        except Exception:
            self._log_warning("清理垃圾桶库 pending 失败", op_id, exc_info=True)

    def mirror_to_trash(self, operation: PendingOperation) -> None:
        """将主库 pending 元数据镜像到垃圾桶库。"""
        self._write_trash(_MIRROR_PENDING_SQL, operation.to_database_values())

    def mirror_to_main(self, operation: PendingOperation) -> None:
        """将垃圾桶库 pending 元数据镜像到主库。"""
        with self._main_db._transaction() as cursor:
            cursor.execute(_MIRROR_PENDING_SQL, operation.to_database_values())

    def read_main(self) -> List[PendingOperation]:
        """读取主库所有待恢复操作；读取失败时降级为空列表。"""
        try:
            rows = self._main_db._execute(_SELECT_PENDING_SQL, fetch='all') or []
            return [PendingOperation.from_row(row) for row in rows]
        except Exception:
            self._log_warning("读取主库 pending_trash_ops 失败", 'recovery', exc_info=True)
            return []

    def read_trash(self) -> List[PendingOperation]:
        """读取垃圾桶库所有待恢复操作；读取失败时降级为空列表。"""
        try:
            with self._pool.lock:
                cursor = self._pool.connection.cursor()
                cursor.execute(_SELECT_PENDING_SQL)
                return [PendingOperation.from_row(dict(row)) for row in cursor.fetchall()]
        except Exception:
            self._log_warning("读取垃圾桶库 pending_trash_ops 失败", 'recovery', exc_info=True)
            return []

    def _update_main_state(self, op_id: str, state: str, updated_at: str) -> None:
        with self._main_db._transaction() as cursor:
            self._update_state(cursor, op_id, state, updated_at)

    def _update_trash_state(self, op_id: str, state: str, updated_at: str) -> None:
        self._write_trash_state(op_id, state, updated_at)

    def _write_trash_state(self, op_id: str, state: str, updated_at: str) -> None:
        self._write_trash(
            "UPDATE pending_trash_ops SET state = ?, updated_at = ? WHERE op_id = ?",
            (state, updated_at, op_id),
        )

    @staticmethod
    def _update_state(cursor: Any, op_id: str, state: str, updated_at: str) -> None:
        cursor.execute(
            "UPDATE pending_trash_ops SET state = ?, updated_at = ? WHERE op_id = ?",
            (state, updated_at, op_id),
        )

    def _write_trash(self, query: str, params: Tuple[Any, ...] = ()) -> None:
        """在锁和独立事务中写垃圾桶库，失败时回滚并向上抛出。"""
        with self._pool.lock:
            with self._pool.transaction() as cursor:
                cursor.execute(query, params)

    @staticmethod
    def _log_warning(message: str, trace_id: str, exc_info: bool) -> None:
        logger.warning(
            message,
            extra={"extra_data": {"trace_id": trace_id, "component": "pending_store"}},
            exc_info=exc_info,
        )
