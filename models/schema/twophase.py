"""
两阶段提交Schema初始化器 - 负责pending_trash_ops跨库协调表
"""
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import sqlite3

logger = logging.getLogger(__name__)


class TwoPhaseCommitSchemaInitializer:
    """两阶段提交Schema初始化器"""

    def __init__(self, conn: 'sqlite3.Connection'):
        self._conn = conn

    def initialize(self, cursor: 'sqlite3.Cursor') -> None:
        """
        初始化2PC跨库协调表

        配合垃圾桶库的 pending_trash_ops 一起做两阶段提交
        - op_id: 全局唯一 UUID（在 2PC 入口处生成）
        - op_type: 'move' / 'restore'
        - state: 'pending' -> 'applied' -> 'committed'
        - payload: JSON 序列化的"真实写"所需的所有参数
        """
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pending_trash_ops (
                op_id TEXT PRIMARY KEY,
                op_type TEXT NOT NULL,
                diary_id INTEGER,
                trash_id INTEGER,
                payload TEXT NOT NULL,
                state TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL DEFAULT '',
                updated_at TEXT
            )
        ''')
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_pending_trash_state '
            'ON pending_trash_ops(state)'
        )

        logger.info("2PC跨库协调表初始化完成")
