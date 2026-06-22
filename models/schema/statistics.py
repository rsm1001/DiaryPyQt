"""
统计Schema初始化器 - 负责daily_stats、view_log和app_config表
"""
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import sqlite3

logger = logging.getLogger(__name__)


class StatisticsSchemaInitializer:
    """统计表Schema初始化器"""

    def __init__(self, conn: 'sqlite3.Connection'):
        self._conn = conn

    def initialize(self, cursor: 'sqlite3.Cursor') -> None:
        """初始化统计相关表"""
        # ---- 每日统计表 ----
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stat_date TEXT NOT NULL UNIQUE,
                yesterday_total_views INTEGER DEFAULT 0,
                all_time_max_single_views INTEGER DEFAULT 0,
                all_time_max_diary_id INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # ---- 查看日志表 ----
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS view_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                diary_id INTEGER NOT NULL,
                viewed_at TEXT NOT NULL,
                FOREIGN KEY (diary_id) REFERENCES diaries(id) ON DELETE CASCADE
            )
        ''')

        # ---- 应用配置表 ----
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS app_config (
                key TEXT PRIMARY KEY,
                value INTEGER DEFAULT 0,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 初始化历史最佳值为 0
        cursor.execute(
            'INSERT OR IGNORE INTO app_config (key, value) VALUES (?, 0)',
            ('all_time_max_daily_views',)
        )

        # ---- 索引 ----
        cursor.execute('DROP INDEX IF EXISTS idx_view_log_viewed_at')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_view_log_viewed_at ON view_log(viewed_at)')
        cursor.execute('DROP INDEX IF EXISTS idx_view_log_diary_id')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_view_log_diary_id ON view_log(diary_id)')

        logger.info("统计表Schema初始化完成")
