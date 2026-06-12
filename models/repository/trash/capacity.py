"""
垃圾桶容量管理

负责垃圾桶 LRU 淘汰：超容量时按 deleted_at 升序淘汰最旧记录。
"""
import logging

from .connection import TrashConnectionPool

logger = logging.getLogger(__name__)


class TrashCapacityManager:
    """垃圾桶容量管理器"""

    def __init__(self, connection_pool: TrashConnectionPool):
        self._pool = connection_pool

    def enforce(self, max_size: int) -> int:
        """强制执行垃圾桶容量限制（LRU 淘汰）

        Args:
            max_size: 容量上限

        Returns:
            实际淘汰的记录数（0 表示未触发淘汰）
        """
        conn = self._pool.connection
        with self._pool.lock:
            cursor = conn.cursor()
            cursor.execute("BEGIN")
            try:
                cursor.execute("SELECT COUNT(*) as count FROM trash_diaries")
                row = cursor.fetchone()
                current_count = row['count'] if row else 0

                if current_count <= max_size:
                    conn.commit()
                    return 0

                delete_count = current_count - max_size
                cursor.execute(
                    """
                    DELETE FROM trash_diaries
                    WHERE id IN (
                        SELECT id FROM trash_diaries
                        ORDER BY deleted_at ASC
                        LIMIT ?
                    )
                    """,
                    (delete_count,),
                )
                conn.commit()
                logger.info(
                    "垃圾桶容量超限，已自动淘汰最早的 %d 条记录（容量=%d，当前=%d）",
                    delete_count, max_size, current_count,
                )
                return delete_count
            except Exception:
                conn.rollback()
                logger.error("垃圾桶容量强制执行失败")
                raise
