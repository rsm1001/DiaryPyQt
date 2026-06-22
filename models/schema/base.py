"""
Schema初始化器基类 - 工厂模式抽象基类
定义Schema初始化器的统一接口
"""
import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import sqlite3

logger = logging.getLogger(__name__)


class BaseSchemaInitializer(ABC):
    """Schema初始化器抽象基类"""

    def __init__(self, conn: 'sqlite3.Connection'):
        self._conn = conn

    @abstractmethod
    def initialize(self) -> None:
        """执行初始化"""
        pass

    @abstractmethod
    def migrate(self, cursor: 'sqlite3.Cursor') -> None:
        """执行数据迁移（如需要）"""
        pass

    def _execute_ignore_exists(self, cursor: 'sqlite3.Cursor', sql: str, *args) -> None:
        """执行SQL，忽略已存在的错误"""
        try:
            cursor.execute(sql, *args)
        except Exception as e:
            logger.debug("SQL执行忽略: %s", e)
