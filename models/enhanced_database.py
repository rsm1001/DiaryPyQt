"""
增强版数据库管理器 - 核心入口
包含迁移功能，负责初始化各服务模块
"""
import os
import sqlite3
import threading
import logging
from typing import List, Dict, Optional, Any

from .mixins._connection_mixin import ConnectionMixin
from .mixins.tag_management_mixin import TagManagementMixin
from .mixins.database_query_mixin import DatabaseQueryMixin
from .repository.diary_operations import DiaryOperationsMixin
from .repository.trash_mixin import TrashMixin
from .migration_backup_manager import MigrationBackupManager
from .schema.factory import SchemaInitializerCoordinator

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
        self._db_lock = threading.RLock()
        self._fts5_available = True  # 默认值，实际值在_init_database中设置

        # 初始化读写分离连接池
        self._init_pool()

        # 服务占位（公开名：调用方用 self.diary_content_service / self.view_count_service 等）
        self._services_initialized = False
        self.migration_backup_manager = None
        self.statistics_service = None
        self.view_count_service = None
        self.diary_content_service = None

        # 确保目录存在
        self._ensure_directory()

        # 初始化数据库
        self._init_database()

        # 初始化垃圾桶数据库
        self._init_trash_database()

        # 启动恢复：扫描两库 pending_trash_ops，推进到稳定态
        # 必须在 __init_services 之前；recovery 不依赖服务
        try:
            recovered = self._recover_pending_trash_ops()
            if recovered:
                logger.info(f"启动恢复：处理 {recovered} 个未完成的跨库操作")
        except Exception as exc:
            logger.error(f"启动恢复失败（已忽略，不影响本次启动）: {exc}")

        # 显式初始化各服务（不再依赖 __getattr__ 兜底）
        self._init_services()

        logger.info(f"EnhancedDatabaseManager 初始化完成，数据库路径: {os.path.abspath(self.db_path)}")

    def _ensure_directory(self):
        """确保数据库目录存在"""
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

    def _init_services(self):
        """
        初始化各服务实例（线程安全，只跑一次）

        - 由 __init__ 末尾显式调用；不依赖 __getattr__ 兜底
        - 用 _db_lock 串行化防止多线程并发 __init__ 时重复创建服务实例
        """
        with self._db_lock:
            if self._services_initialized:
                return
            StatisticsService, ViewCountService, DiaryContentService = _import_services_lazily()

            self.migration_backup_manager = MigrationBackupManager(self)
            self.statistics_service = StatisticsService(self)
            self.view_count_service = ViewCountService(self)
            self.diary_content_service = DiaryContentService(self)
            self._services_initialized = True

    def __getattr__(self, name):
        """
        显式属性兜底：未知属性直接抛 AttributeError，不再触发 _init_services。

        旧实现会在 hasattr / 调试 / 自动补全时副作用式地初始化服务，带来：
        (1) hasattr 出现副作用
        (2) 调试期 __getattr__ 栈掩盖真实异常
        (3) _init_services 缺锁保护，并发下可能重复创建服务实例
        现在服务在 __init__ 末尾显式完成初始化，所有服务字段都是真实属性。
        """
        raise AttributeError(
            f"{type(self).__name__!r} object has no attribute {name!r} "
            f"(services are initialized explicitly in __init__)"
        )

    # -------------------------------------------------------------------------
    # 数据库Schema初始化（委托给Schema协调器）
    # -------------------------------------------------------------------------

    def _init_database(self):
        """初始化数据库表、索引和性能配置（委托给Schema协调器）"""
        # 确保连接池已初始化（restore_database 等场景可能已关闭连接池）
        if self._write_conn is None:
            self._init_pool()

        conn = self._get_write_connection()

        # 使用Schema初始化器协调器进行初始化
        coordinator = SchemaInitializerCoordinator(conn)
        self._fts5_available = coordinator.run_initialization()

        # ---- 性能优化PRAGMA ----
        cursor = conn.cursor()
        cursor.execute('PRAGMA journal_mode=WAL')
        cursor.execute('PRAGMA synchronous=NORMAL')
        cursor.execute('PRAGMA cache_size=10000')
        cursor.execute('PRAGMA temp_store=memory')
        cursor.execute('PRAGMA mmap_size=30000000000')

        conn.commit()
        logger.info("数据库初始化完成")

    def compute_tokens(self, content: str) -> str:
        """
        对外暴露：把内容算成 tokens 空格串（写库前用）。

        - 无 FTS5 时返回空串（旧 LIKE 行为）
        - 委托给 FTS5SchemaInitializer 实现
        """
        if not content:
            return ''
        if not getattr(self, '_fts5_available', True):
            return ''
        from models.schema.fts5 import FTS5SchemaInitializer
        fts5_init = FTS5SchemaInitializer(self._get_write_connection())
        return fts5_init.compute_tokens(content, self._fts5_available)

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
        """关闭数据库连接池"""
        self._close_pool()
        self._close_trash_pool()
        logger.info("数据库连接池已关闭")


# =============================================================================
# 实例池模式（按路径缓存）
# =============================================================================

_enhanced_db_managers: Dict[str, EnhancedDatabaseManager] = {}


def get_enhanced_db_manager(db_path: str = None) -> EnhancedDatabaseManager:
    """获取增强版数据库管理器（按路径缓存实例）"""
    global _enhanced_db_managers

    if db_path is None:
        from config.config import get_db_path
        db_path = get_db_path()

    if db_path not in _enhanced_db_managers:
        _enhanced_db_managers[db_path] = EnhancedDatabaseManager(db_path)

    return _enhanced_db_managers[db_path]


def reset_enhanced_db_manager(db_path: str = None):
    """重置指定路径的实例（下次调用会重新创建）"""
    global _enhanced_db_managers

    if db_path is None:
        from config.config import get_db_path
        db_path = get_db_path()

    if db_path in _enhanced_db_managers:
        _enhanced_db_managers[db_path].close()
        del _enhanced_db_managers[db_path]
