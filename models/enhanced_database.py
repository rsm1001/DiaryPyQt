"""
增强版数据库管理器，包含迁移功能
"""
import sqlite3
import os
import threading
import logging
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple
from contextlib import contextmanager
import json
import csv

# 导入新的标签管理混入类、迁移备份管理器、查询混入模块、统计服务模块和查看次数服务模块
from .mixins.tag_management_mixin import TagManagementMixin
from .migration_backup_manager import MigrationBackupManager
from .mixins.database_query_mixin import DatabaseQueryMixin
from .repository.diary_operations import DiaryOperationsMixin

# 导入服务模块 - 使用动态导入以避免循环依赖和相对导入问题
def _import_services_lazily():
    """延迟导入服务模块，避免相对导入问题"""
    from services.statistics_service import StatisticsService
    from services.view_count_service import ViewCountService
    from services.content_service import DiaryContentService
    return StatisticsService, ViewCountService, DiaryContentService

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EnhancedDatabaseManager(TagManagementMixin, DatabaseQueryMixin, DiaryOperationsMixin):
    """增强版SQLite数据库管理器 - 包含完整的迁移和备份功能"""
    
    def __init__(self, db_path: str = None):
        """
        初始化数据库管理器
        
        Args:
            db_path: 数据库文件路径
        """
        # 如果没有提供数据库路径，则使用默认的本地路径
        if db_path is None:
            import os
            from pathlib import Path
            # 使用项目根目录下的data文件夹
            db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "diary.db")
            # 确保目录存在
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        self.db_path = db_path
        self._local = threading.local()
        self._lock = threading.RLock()
        
        # 创建迁移备份管理器实例
        self.migration_backup_manager = None  # 稍后在初始化数据库之后创建
        # 创建统计服务实例
        self.statistics_service = None  # 稍后在初始化数据库之后创建
        # 创建查看次数服务实例
        self.view_count_service = None  # 稍后在初始化数据库之后创建
        # 创建日记内容服务实例
        self.diary_content_service = None  # 稍后在初始化数据库之后创建
        
        # 确保目录存在
        self._ensure_directory()
        
        # 初始化数据库
        self._init_database()
        
        # 初始化迁移备份管理器
        self.migration_backup_manager = MigrationBackupManager(self)
        
        # 初始化统计服务
        StatisticsService, ViewCountService, DiaryContentService = _import_services_lazily()
        self.statistics_service = StatisticsService(self)
        
        # 初始化查看次数服务
        self.view_count_service = ViewCountService(self)
        
        # 初始化日记内容服务
        self.diary_content_service = DiaryContentService(self)
        
        import os  # 在使用os之前重新导入，以避免作用域问题
        logger.info(f"EnhancedDatabaseManager初始化完成，数据库路径: {os.path.abspath(self.db_path)}")
    
    def get_all_diaries(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        获取所有日记（按日期倒序）- 符合DatabaseManagerInterface协议，带标签信息
        
        Returns:
            日记列表
        """
        # 使用日记内容服务获取日记，然后添加标签信息
        diaries = self.diary_content_service.get_all_diaries_with_tags(limit)
        return diaries
    
    def get_diaries_with_limit(self, limit: int) -> List[Dict[str, Any]]:
        """
        获取指定数量的日记（按日期倒序）- 符合DatabaseManagerInterface协议
        
        Args:
            limit: 限制数量
        
        Returns:
            日记列表
        """
        return self.diary_content_service.get_diaries_with_limit(limit)

    def _ensure_directory(self):
        """确保数据库目录存在"""
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
    
    def _get_connection(self) -> sqlite3.Connection:
        """获取线程本地的数据库连接"""
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            self._local.connection = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                isolation_level=None  # 自动提交模式
            )
            # 启用外键支持
            self._local.connection.execute("PRAGMA foreign_keys = ON")
            # 设置行工厂
            self._local.connection.row_factory = sqlite3.Row
        return self._local.connection
    
    def _init_database(self):
        """初始化数据库表和索引"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 创建日记表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS diaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    content TEXT NOT NULL,
                    view_count INTEGER DEFAULT 0
                )
            ''')
            
            # 创建标签表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 创建日记-标签关联表
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
            
            # 创建每日统计表
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
            
            # 创建索引
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_diaries_date ON diaries(date)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_diaries_view_count ON diaries(view_count)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_diaries_content ON diaries(content)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_diary_tags_diary_id ON diary_tags(diary_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_diary_tags_tag_id ON diary_tags(tag_id)')
            
            # 启用WAL模式以提高并发性能
            cursor.execute('PRAGMA journal_mode=WAL')
            cursor.execute('PRAGMA synchronous=NORMAL')
            cursor.execute('PRAGMA cache_size=10000')
            cursor.execute('PRAGMA temp_store=memory')
            cursor.execute('PRAGMA mmap_size=30000000000')
            
            conn.commit()
            logger.info("数据库初始化完成")
    
    @contextmanager
    def _transaction(self):
        """事务上下文管理器"""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("BEGIN")
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"事务回滚: {e}")
            raise
    
    def _execute(
        self, 
        query: str, 
        params: Tuple = (), 
        fetch: Optional[str] = None
    ) -> Optional[Any]:
        """
        执行SQL查询
        
        Args:
            query: SQL语句
            params: 参数元组
            fetch: 获取类型 ('one', 'all', 'rowcount', None)
        
        Returns:
            查询结果
        """
        with self._lock:
            try:
                with self._transaction() as cursor:
                    cursor.execute(query, params)
                    
                    if fetch == 'one':
                        row = cursor.fetchone()
                        return dict(row) if row else None
                    elif fetch == 'all':
                        rows = cursor.fetchall()
                        return [dict(row) for row in rows]
                    elif fetch == 'rowcount':
                        return cursor.rowcount
                    else:
                        return cursor.lastrowid
                        
            except sqlite3.Error as e:
                logger.error(f"SQL执行错误: {e}, 查询: {query}, 参数: {params}")
                raise
    
    # ========================================================================
    # 日记CRUD操作
    # ========================================================================
    


    # ========================================================================
    # 查看次数操作
    # ========================================================================
    
    def increment_view_count(self, diary_id: int) -> Optional[int]:
        """
        增加日记查看次数
        
        Args:
            diary_id: 日记ID
        
        Returns:
            新的查看次数或None
        """
        return self.view_count_service.increment_view_count(diary_id)
    
    def decrease_view_count(self, diary_id: int, penalty: int = 1) -> bool:
        """
        减少日记查看次数
        
        Args:
            diary_id: 日记ID
            penalty: 减少的数量
        
        Returns:
            是否操作成功
        """
        return self.view_count_service.decrease_view_count(diary_id, penalty)

    # ========================================================================
    # 统计功能
    # ========================================================================
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取统计信息
        
        Returns:
            统计信息字典
        """
        return self.statistics_service.get_statistics()
    
    def get_daily_stats(self) -> Dict[str, Any]:
        """
        获取每日统计信息（昨日查看总数 + 历史最佳）
        
        Returns:
            每日统计信息字典
        """
        return self.statistics_service.get_daily_stats()
    
    # ========================================================================
    # 代理方法 - 迁移和备份功能
    # ========================================================================
    
    def migrate_from_json(self, json_file_path: str) -> int:
        """
        从JSON文件迁移数据到SQLite（代理方法）
        
        Args:
            json_file_path: JSON文件路径
        
        Returns:
            迁移的日记数量
        """
        return self.migration_backup_manager.migrate_from_json(json_file_path)
    
    def migrate_from_csv(self, csv_file_path: str) -> int:
        """
        从CSV文件迁移数据到SQLite（代理方法）
        
        Args:
            csv_file_path: CSV文件路径
        
        Returns:
            迁移的日记数量
        """
        return self.migration_backup_manager.migrate_from_csv(csv_file_path)
    
    def export_to_json(self, json_file_path: str) -> bool:
        """
        导出数据到JSON文件（代理方法）
        
        Args:
            json_file_path: JSON文件路径
        
        Returns:
            是否导出成功
        """
        return self.migration_backup_manager.export_to_json(json_file_path)
    
    def export_to_csv(self, csv_file_path: str) -> bool:
        """
        导出数据到CSV文件（代理方法）
        
        Args:
            csv_file_path: CSV文件路径
        
        Returns:
            是否导出成功
        """
        return self.migration_backup_manager.export_to_csv(csv_file_path)
    
    def backup_database(self, backup_path: str) -> bool:
        """
        备份整个数据库（代理方法）
        
        Args:
            backup_path: 备份文件路径
        
        Returns:
            是否备份成功
        """
        return self.migration_backup_manager.backup_database(backup_path)
    
    def restore_database(self, backup_path: str) -> bool:
        """
        从备份恢复数据库（代理方法）
        
        Args:
            backup_path: 备份文件路径
        
        Returns:
            是否恢复成功
        """
        return self.migration_backup_manager.restore_database(backup_path)
    
    def validate_database_integrity(self) -> bool:
        """
        验证数据库完整性（代理方法）
        
        Returns:
            数据库是否完整有效
        """
        return self.migration_backup_manager.validate_database_integrity()

    def close(self):
        """关闭数据库连接"""
        if hasattr(self._local, 'connection') and self._local.connection:
            self._local.connection.close()
            self._local.connection = None
            logger.info("数据库连接已关闭")


# 单例模式
_enhanced_db_manager = None


def get_enhanced_db_manager(db_path: str = None) -> EnhancedDatabaseManager:
    """获取增强版数据库管理器单例"""
    global _enhanced_db_manager
    if _enhanced_db_manager is None:
        _enhanced_db_manager = EnhancedDatabaseManager(db_path)
    return _enhanced_db_manager