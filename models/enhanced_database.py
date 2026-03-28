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

# 导入新的标签管理器、迁移备份管理器、查询混入模块、统计服务模块和查看次数服务模块
from .tag_manager import TagManager
from .migration_backup_manager import MigrationBackupManager
from .database_query_mixin import DatabaseQueryMixin

# 导入服务模块 - 使用动态导入以避免循环依赖和相对导入问题
def _import_services_lazily():
    """延迟导入服务模块，避免相对导入问题"""
    from services.statistics_service import StatisticsService
    from services.view_count_service import ViewCountService
    from services.diary_content_service import DiaryContentService
    return StatisticsService, ViewCountService, DiaryContentService

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EnhancedDatabaseManager(DatabaseQueryMixin):
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
        
        # 创建标签管理器实例
        self.tag_manager = None  # 稍后在初始化数据库之后创建
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
        
        # 初始化标签管理器
        self.tag_manager = TagManager(self)
        
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
    
    def get_all_diaries(self) -> List[Dict[str, Any]]:
        """
        获取所有日记（按日期倒序）- 符合DatabaseManagerInterface协议
        
        Returns:
            日记列表
        """
        # 使用日记内容服务获取日记，然后添加标签信息
        diaries = self.diary_content_service.get_all_diaries()
        
        # 对每篇日记获取完整的标签列表
        for diary in diaries:
            diary['tags'] = self.get_tags_by_diary_id(diary['id'])
        
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
    
    def add_diary(self, content: str) -> Optional[Dict[str, Any]]:
        """
        添加新日记
        
        Args:
            content: 日记内容
        
        Returns:
            新创建的日记字典
        """
        return self.diary_content_service.add_diary(content)
    
    def get_diary_by_id(self, diary_id: int) -> Optional[Dict[str, Any]]:
        """
        根据ID获取日记
        
        Args:
            diary_id: 日记ID
        
        Returns:
            日记字典或None
        """
        return self.diary_content_service.get_diary_by_id(diary_id)
    
    def update_diary(self, diary_id: int, new_content: str) -> bool:
        """
        更新日记内容
        
        Args:
            diary_id: 日记ID
            new_content: 新内容
        
        Returns:
            是否更新成功
        """
        return self.diary_content_service.update_diary(diary_id, new_content)
    
    def delete_diary_by_id(self, diary_id: int) -> Optional[Dict[str, Any]]:
        """
        根据ID删除日记
        
        Args:
            diary_id: 日记ID
        
        Returns:
            被删除的日记字典或None
        """
        return self.diary_content_service.delete_diary_by_id(diary_id)
    
    def update_diary(self, diary_id: int, new_content: str) -> bool:
        """
        更新日记内容
        
        Args:
            diary_id: 日记ID
            new_content: 新内容
        
        Returns:
            是否更新成功
        """
        if not new_content or not new_content.strip():
            logger.warning("尝试更新为空内容")
            return False
        
        date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rowcount = self._execute(
            "UPDATE diaries SET content = ?, date = ? WHERE id = ?",
            (new_content.strip(), date, diary_id),
            fetch='rowcount'
        )
        
        if rowcount > 0:
            logger.info(f"更新日记成功，ID: {diary_id}")
            return True
        logger.warning(f"更新日记失败，ID: {diary_id} 不存在")
        return False
    
    def delete_diary_by_id(self, diary_id: int) -> Optional[Dict[str, Any]]:
        """
        根据ID删除日记
        
        Args:
            diary_id: 日记ID
        
        Returns:
            被删除的日记字典或None
        """
        # 先获取日记信息
        diary = self.get_diary_by_id(diary_id)
        if not diary:
            logger.warning(f"删除失败，日记不存在: {diary_id}")
            return None
        
        # 删除日记
        self._execute(
            "DELETE FROM diaries WHERE id = ?",
            (diary_id,)
        )
        
        logger.info(f"删除日记成功，ID: {diary_id}")
        return diary
    
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
    
    def get_all_diaries(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        获取所有日记（按日期倒序）
        
        Args:
            limit: 限制数量
        
        Returns:
            日记列表
        """
        # 使用新方法获取带标签的日记
        return self.get_all_diaries_with_tags(limit)
    
    # 以下是与标签管理器的代理方法，以保持原有接口兼容
    def add_tag(self, name: str) -> Optional[Dict[str, Any]]:
        """
        添加新标签
        
        Args:
            name: 标签名称
        
        Returns:
            新创建的标签字典或None
        """
        return self.tag_manager.add_tag(name)
    
    def get_tag_by_id(self, tag_id: int) -> Optional[Dict[str, Any]]:
        """
        根据ID获取标签
        
        Args:
            tag_id: 标签ID
        
        Returns:
            标签字典或None
        """
        return self.tag_manager.get_tag_by_id(tag_id)
    
    def get_tag_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """
        根据名称获取标签
        
        Args:
            name: 标签名
        
        Returns:
            标签字典或None
        """
        return self.tag_manager.get_tag_by_name(name)
    
    def get_all_tags(self) -> List[Dict[str, Any]]:
        """
        获取所有标签
        
        Returns:
            标签列表
        """
        return self.tag_manager.get_all_tags()
    
    def update_tag(self, tag_id: int, new_name: str) -> bool:
        """
        更新标签名称
        
        Args:
            tag_id: 标签ID
            new_name: 新名称
        
        Returns:
            是否更新成功
        """
        return self.tag_manager.update_tag(tag_id, new_name)
    
    def delete_tag_by_id(self, tag_id: int) -> bool:
        """
        根据ID删除标签（仅在没有日记使用该标签的前提下）
        
        Args:
            tag_id: 标签ID
        
        Returns:
            是否删除成功
        """
        return self.tag_manager.delete_tag_by_id(tag_id)
    
    def get_unused_tags(self) -> List[Dict[str, Any]]:
        """
        获取未被使用的标签（没有日记关联的标签）
        
        Returns:
            未被使用的标签列表
        """
        return self.tag_manager.get_unused_tags()
    
    def add_diary_tag(self, diary_id: int, tag_id: int) -> bool:
        """
        为日记添加标签
        
        Args:
            diary_id: 日记ID
            tag_id: 标签ID
        
        Returns:
            是否添加成功
        """
        return self.tag_manager.add_diary_tag(diary_id, tag_id)
    
    def remove_diary_tag(self, diary_id: int, tag_id: int) -> bool:
        """
        移除日记的特定标签
        
        Args:
            diary_id: 日记ID
            tag_id: 标签ID
        
        Returns:
            是否移除成功
        """
        return self.tag_manager.remove_diary_tag(diary_id, tag_id)
    
    def get_tags_by_diary_id(self, diary_id: int) -> List[Dict[str, Any]]:
        """
        获取某篇日记的所有标签
        
        Args:
            diary_id: 日记ID
        
        Returns:
            标签列表
        """
        return self.tag_manager.get_tags_by_diary_id(diary_id)
    
    def get_diaries_by_tag_id(self, tag_id: int) -> List[Dict[str, Any]]:
        """
        获取标记了特定标签的所有日记
        
        Args:
            tag_id: 标签ID
        
        Returns:
            日记列表
        """
        return self.tag_manager.get_diaries_by_tag_id(tag_id)
    
    def assign_tags_to_diary(self, diary_id: int, tag_ids: List[int]) -> bool:
        """
        为日记分配一组标签（替换原有标签）
        
        Args:
            diary_id: 日记ID
            tag_ids: 标签ID列表
        
        Returns:
            是否分配成功
        """
        return self.tag_manager.assign_tags_to_diary(diary_id, tag_ids)
    
    def get_diary_with_tags_by_id(self, diary_id: int) -> Optional[Dict[str, Any]]:
        """
        获取日记及其所有标签
        
        Args:
            diary_id: 日记ID
        
        Returns:
            包含标签的日记字典
        """
        diary = self.get_diary_by_id(diary_id)
        if not diary:
            return None
        
        tags = self.get_tags_by_diary_id(diary_id)
        diary['tags'] = tags
        return diary
    
    def get_all_diaries_with_tags(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        获取所有日记及其标签
        
        Args:
            limit: 限制数量
        
        Returns:
            包含标签的日记列表
        """
        return self.diary_content_service.get_all_diaries_with_tags(limit)

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