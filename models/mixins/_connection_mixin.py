"""
数据库连接管理混入类
提供线程本地的数据库连接、事务管理和SQL执行功能
"""
from contextlib import contextmanager
import sqlite3
import threading
import logging
from typing import Tuple, Optional, Any

logger = logging.getLogger(__name__)


class ConnectionMixin:
    """
    数据库连接管理混入类

    提供：
    - 线程本地的数据库连接（_get_connection）
    - 事务上下文管理器（_transaction）
    - 通用SQL执行方法（_execute）
    """

    # -------------------------------------------------------------------------
    # 子类必须实现的抽象属性
    # -------------------------------------------------------------------------

    @property
    def db_path(self) -> str:
        """数据库文件路径，由子类提供"""
        raise NotImplementedError

    @property
    def _lock(self) -> threading.RLock:
        """线程锁，由子类提供"""
        raise NotImplementedError

    # -------------------------------------------------------------------------
    # 连接管理
    # -------------------------------------------------------------------------

    def _get_connection(self) -> sqlite3.Connection:
        """
        获取线程本地的数据库连接

        Returns:
            sqlite3.Connection 实例
        """
        if not hasattr(self._db_local, 'connection') or self._db_local.connection is None:
            self._db_local.connection = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                isolation_level=None  # 自动提交模式
            )
            # 启用外键支持
            self._db_local.connection.execute("PRAGMA foreign_keys = ON")
            # 设置行工厂
            self._db_local.connection.row_factory = sqlite3.Row
        return self._db_local.connection

    # -------------------------------------------------------------------------
    # 事务管理
    # -------------------------------------------------------------------------

    @contextmanager
    def _transaction(self):
        """
        事务上下文管理器

        用法:
            with self._transaction() as cursor:
                cursor.execute(...)
        """
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

    # -------------------------------------------------------------------------
    # SQL执行
    # -------------------------------------------------------------------------

    def _execute(
        self,
        query: str,
        params: Tuple = (),
        fetch: Optional[str] = None
    ) -> Optional[Any]:
        """
        执行SQL查询（线程安全）

        Args:
            query:  SQL语句
            params: 参数元组
            fetch:  获取类型 ('one' / 'all' / 'rowcount' / None)

        Returns:
            - 'one':     单行字典 或 None
            - 'all':     行字典列表 或 []
            - 'rowcount':受影响行数
            - None:      lastrowid
        """
        with self._db_lock:
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
