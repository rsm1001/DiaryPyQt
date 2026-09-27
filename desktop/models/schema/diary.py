"""
日记Schema初始化器 - 负责diaries表及相关结构
"""
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import sqlite3

logger = logging.getLogger(__name__)


class DiarySchemaInitializer:
    """日记表Schema初始化器"""

    def __init__(self, conn: 'sqlite3.Connection'):
        self._conn = conn

    def initialize(self, cursor: 'sqlite3.Cursor') -> None:
        """初始化日记表及历史数据兼容"""
        # ---- 日记主表 ----
        # date  = 创建时间（写入后永不变；update_diary 不得覆盖）
        # updated_at = 最近一次内容编辑时间（NULL 表示从未被编辑，仍等于 date）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS diaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                content TEXT NOT NULL,
                view_count INTEGER DEFAULT 0,
                last_viewed_at TEXT,
                tokens TEXT,
                updated_at TEXT
            )
        ''')

        # 为已有表添加 last_viewed_at 列（兼容旧数据库）
        try:
            cursor.execute('ALTER TABLE diaries ADD COLUMN last_viewed_at TEXT')
        except Exception:
            pass  # 列已存在

        # 为已有表添加 tokens 列（兼容旧数据库；多语种分词的预分词结果）
        try:
            cursor.execute('ALTER TABLE diaries ADD COLUMN tokens TEXT')
        except Exception:
            pass  # 列已存在

        # 为已有表添加 updated_at 列（兼容旧数据库；区分"何时写下"与"何时改了它"）
        try:
            cursor.execute('ALTER TABLE diaries ADD COLUMN updated_at TEXT')
        except Exception:
            pass  # 列已存在

        # 回填旧库：updated_at 默认等于 date（语义上"创建即最新"）
        cursor.execute(
            'UPDATE diaries SET updated_at = date '
            'WHERE updated_at IS NULL OR updated_at = ""'
        )

        # ---- 索引 ----
        cursor.execute('DROP INDEX IF EXISTS idx_diaries_date')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_diaries_date ON diaries(date)')
        cursor.execute('DROP INDEX IF EXISTS idx_diaries_view_count')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_diaries_view_count ON diaries(view_count)')
        cursor.execute('DROP INDEX IF EXISTS idx_diaries_content')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_diaries_content ON diaries(content)')
        cursor.execute('DROP INDEX IF EXISTS idx_diaries_content_lower')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_diaries_content_lower ON diaries(LOWER(content))')
        # updated_at 索引：支持"今日改过""最近编辑"等查询
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_diaries_updated_at ON diaries(updated_at)')

        logger.info("日记表Schema初始化完成")
