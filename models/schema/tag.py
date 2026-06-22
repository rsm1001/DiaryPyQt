"""
标签Schema初始化器 - 负责tags表和diary_tags关联表
"""
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import sqlite3

logger = logging.getLogger(__name__)


class TagSchemaInitializer:
    """标签表Schema初始化器"""

    def __init__(self, conn: 'sqlite3.Connection'):
        self._conn = conn

    def initialize(self, cursor: 'sqlite3.Cursor') -> None:
        """初始化标签表及关联表"""
        # ---- 标签表 ----
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # ---- 日记-标签关联表 ----
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS diary_tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                diary_id INTEGER NOT NULL,
                tag_id INTEGER NOT NULL,
                FOREIGN KEY (diary_id) REFERENCES diaries(id) ON DELETE CASCADE,
                FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE,
                UNIQUE(diary_id, tag_id)
            )
        ''')

        # ---- 索引 ----
        cursor.execute('DROP INDEX IF EXISTS idx_diary_tags_diary_id')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_diary_tags_diary_id ON diary_tags(diary_id)')
        cursor.execute('DROP INDEX IF EXISTS idx_diary_tags_tag_id')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_diary_tags_tag_id ON diary_tags(tag_id)')

        logger.info("标签表Schema初始化完成")
