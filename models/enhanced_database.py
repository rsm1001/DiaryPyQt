"""
增强版数据库管理器 - 核心入口
包含迁移功能，负责初始化各服务模块
"""
import os
import threading
import logging
from typing import List, Dict, Optional, Any

from .mixins._connection_mixin import ConnectionMixin
from .mixins.tag_management_mixin import TagManagementMixin
from .mixins.database_query_mixin import DatabaseQueryMixin
from .repository.diary_operations import DiaryOperationsMixin
from .repository.trash_mixin import TrashMixin
from .migration_backup_manager import MigrationBackupManager

logger = logging.getLogger(__name__)

# 延迟导入服务模块（避免循环依赖）
def _import_services_lazily():
    """延迟导入服务模块"""
    from services.statistics_service import StatisticsService
    from services.view_count_service import ViewCountService
    from services.content_service import DiaryContentService
    return StatisticsService, ViewCountService, DiaryContentService


class EnhancedDatabaseManager(
    ConnectionMixin,
    TagManagementMixin,
    DatabaseQueryMixin,
    DiaryOperationsMixin,
    TrashMixin
):
    """
    增强版SQLite数据库管理器

    继承自 ConnectionMixin，获取核心连接/事务/SQL执行能力；
    其余功能由各 Mixin 和 Service 提供。
    """

    # -------------------------------------------------------------------------
    # 属性实现（ConnectionMixin 要求）
    # -------------------------------------------------------------------------

    @property
    def db_path(self) -> str:
        return self._db_path

    @property
    def _lock(self) -> threading.RLock:
        return self._db_lock

    # -------------------------------------------------------------------------
    # 初始化
    # -------------------------------------------------------------------------

    def __init__(self, db_path: str = None):
        """
        初始化数据库管理器

        Args:
            db_path: 数据库文件路径
        """
        # 解析数据库路径
        if db_path is None:
            project_root = os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))
            )
            db_path = os.path.join(project_root, "data", "diary.db")

        self._db_path = db_path
        self._db_local = threading.local()
        self._db_lock = threading.RLock()

        # 服务占位（延迟初始化）
        self.migration_backup_manager: Optional[MigrationBackupManager] = None
        self.statistics_service = None
        self.view_count_service = None
        self.diary_content_service = None

        # 确保目录存在
        self._ensure_directory()

        # 初始化数据库
        self._init_database()

        # 初始化各服务
        self._init_services()

        # 初始化垃圾桶数据库
        self._init_trash_database()

        logger.info(f"EnhancedDatabaseManager 初始化完成，数据库路径: {os.path.abspath(self.db_path)}")

    def _ensure_directory(self):
        """确保数据库目录存在"""
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

    def _init_services(self):
        """初始化各服务实例"""
        StatisticsService, ViewCountService, DiaryContentService = _import_services_lazily()

        self.migration_backup_manager = MigrationBackupManager(self)
        self.statistics_service = StatisticsService(self)
        self.view_count_service = ViewCountService(self)
        self.diary_content_service = DiaryContentService(self)

    # -------------------------------------------------------------------------
    # 数据库Schema初始化
    # -------------------------------------------------------------------------

    def _init_database(self):
        """初始化数据库表、索引和性能配置"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # ---- 日记主表 ----
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS diaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                content TEXT NOT NULL,
                view_count INTEGER DEFAULT 0,
                last_viewed_at TEXT
            )
        ''')

        # 为已有表添加 last_viewed_at 列（兼容旧数据库）
        try:
            cursor.execute('ALTER TABLE diaries ADD COLUMN last_viewed_at TEXT')
        except Exception:
            pass  # 列已存在

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
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_diaries_date ON diaries(date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_diaries_view_count ON diaries(view_count)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_diaries_content ON diaries(content)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_diary_tags_diary_id ON diary_tags(diary_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_diary_tags_tag_id ON diary_tags(tag_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_view_log_viewed_at ON view_log(viewed_at)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_view_log_diary_id ON view_log(diary_id)')

        # ---- 性能优化PRAGMA ----
        cursor.execute('PRAGMA journal_mode=WAL')
        cursor.execute('PRAGMA synchronous=NORMAL')
        cursor.execute('PRAGMA cache_size=10000')
        cursor.execute('PRAGMA temp_store=memory')
        cursor.execute('PRAGMA mmap_size=30000000000')

        conn.commit()
        logger.info("数据库初始化完成")

    # -------------------------------------------------------------------------
    # 公开API（代理到各服务）
    # -------------------------------------------------------------------------

    def get_all_diaries(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """获取所有日记（按日期倒序），带标签信息"""
        return self.diary_content_service.get_all_diaries_with_tags(limit)

    def get_diaries_by_date(self, date_str: str) -> List[Dict[str, Any]]:
        """根据日期获取日记（LIKE 查询）

        Args:
            date_str: 日期字符串，格式如 '2026-05-20'

        Returns:
            该日期的所有日记
        """
        return self.diary_content_service.get_diaries_by_date(date_str)

    def get_diaries_with_limit(self, limit: int) -> List[Dict[str, Any]]:
        """获取指定数量的日记（按日期倒序）"""
        return self.diary_content_service.get_diaries_with_limit(limit)

    # ---- 查看次数 ----

    def increment_view_count(self, diary_id: int) -> Optional[int]:
        """增加日记查看次数"""
        return self.view_count_service.increment_view_count(diary_id)

    def decrease_view_count(self, diary_id: int, penalty: int = 1) -> bool:
        """减少日记查看次数"""
        return self.view_count_service.decrease_view_count(diary_id, penalty)

    # ---- 统计 ----

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return self.statistics_service.get_statistics()

    def get_daily_stats(self) -> Dict[str, Any]:
        """获取每日统计信息"""
        return self.statistics_service.get_daily_stats()

    # ---- 迁移/备份 ----

    def migrate_from_json(self, json_file_path: str) -> int:
        """从JSON文件迁移数据"""
        return self.migration_backup_manager.migrate_from_json(json_file_path)

    def migrate_from_csv(self, csv_file_path: str) -> int:
        """从CSV文件迁移数据"""
        return self.migration_backup_manager.migrate_from_csv(csv_file_path)

    def export_to_json(self, json_file_path: str) -> bool:
        """导出数据到JSON文件"""
        return self.migration_backup_manager.export_to_json(json_file_path)

    def export_to_csv(self, csv_file_path: str) -> bool:
        """导出数据到CSV文件"""
        return self.migration_backup_manager.export_to_csv(csv_file_path)

    def backup_database(self, backup_path: str) -> bool:
        """备份整个数据库"""
        return self.migration_backup_manager.backup_database(backup_path)

    def restore_database(self, backup_path: str) -> bool:
        """从备份恢复数据库"""
        return self.migration_backup_manager.restore_database(backup_path)

    def validate_database_integrity(self) -> bool:
        """验证数据库完整性"""
        return self.migration_backup_manager.validate_database_integrity()

    # -------------------------------------------------------------------------
    # 生命周期
    # -------------------------------------------------------------------------

    def close(self):
        """关闭数据库连接"""
        if hasattr(self._db_local, 'connection') and self._db_local.connection:
            self._db_local.connection.close()
            self._db_local.connection = None
            logger.info("数据库连接已关闭")

        if hasattr(self._db_local, 'trash_connection') and self._db_local.trash_connection:
            self._db_local.trash_connection.close()
            self._db_local.trash_connection = None
            logger.info("垃圾桶数据库连接已关闭")


# =============================================================================
# 单例模式
# =============================================================================

_enhanced_db_manager: Optional[EnhancedDatabaseManager] = None


def get_enhanced_db_manager(db_path: str = None) -> EnhancedDatabaseManager:
    """获取增强版数据库管理器单例"""
    global _enhanced_db_manager
    if _enhanced_db_manager is None:
        _enhanced_db_manager = EnhancedDatabaseManager(db_path)
    return _enhanced_db_manager
