"""
Schema初始化器工厂 - 统一管理和协调各Schema初始化器
"""
import logging
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    import sqlite3
    from models.schema.base import BaseSchemaInitializer

logger = logging.getLogger(__name__)


class SchemaInitializerFactory:
    """Schema初始化器工厂类"""

    def __init__(self, conn: 'sqlite3.Connection'):
        self._conn = conn
        self._fts5_available = False

    def _create_initializer(self, module_name: str, class_name: str):
        """动态创建初始化器实例"""
        try:
            module = __import__(f'models.schema.{module_name}', fromlist=[class_name])
            cls = getattr(module, class_name)
            return cls(self._conn)
        except Exception as e:
            logger.error("创建Schema初始化器失败 %s.%s: %s", module_name, class_name, e)
            return None

    def initialize_all(self) -> bool:
        """
        初始化所有Schema组件

        Returns:
            FTS5是否可用的布尔值
        """
        cursor = self._conn.cursor()

        # 1. 初始化日记表
        diary_init = self._create_initializer('diary', 'DiarySchemaInitializer')
        if diary_init:
            diary_init.initialize(cursor)

        # 2. 初始化标签表
        tag_init = self._create_initializer('tag', 'TagSchemaInitializer')
        if tag_init:
            tag_init.initialize(cursor)

        # 3. 初始化统计表
        stats_init = self._create_initializer('statistics', 'StatisticsSchemaInitializer')
        if stats_init:
            stats_init.initialize(cursor)

        # 4. 初始化2PC跨库协调表
        twophase_init = self._create_initializer('twophase', 'TwoPhaseCommitSchemaInitializer')
        if twophase_init:
            twophase_init.initialize(cursor)

        # 5. FTS5检测和初始化（需要知道FTS5是否可用）
        fts5_init = self._create_initializer('fts5', 'FTS5SchemaInitializer')
        if fts5_init:
            self._fts5_available = fts5_init.probe_fts5(cursor)
            if not self._fts5_available:
                logger.warning("当前 SQLite 构建未启用 FTS5，搜索将自动降级为 LIKE 模式")
            fts5_init.initialize(cursor, self._fts5_available)

        self._conn.commit()
        return self._fts5_available

    @property
    def fts5_available(self) -> bool:
        """返回FTS5可用性"""
        return self._fts5_available


class SchemaInitializerCoordinator:
    """Schema初始化协调器 - 协调多个子初始化器的执行"""

    def __init__(self, conn: 'sqlite3.Connection'):
        self._conn = conn
        self._factory = SchemaInitializerFactory(conn)

    def run_initialization(self) -> bool:
        """
        执行完整的Schema初始化

        Returns:
            FTS5是否可用
        """
        logger.info("开始Schema初始化...")
        result = self._factory.initialize_all()
        logger.info("Schema初始化完成")
        return result

    @property
    def fts5_available(self) -> bool:
        return self._factory.fts5_available
