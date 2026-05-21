"""
数据库连接管理混入类
提供线程本地的数据库连接、事务管理和SQL执行功能
"""
from contextlib import contextmanager
import sqlite3
import threading
import logging
from typing import Tuple, Optional, Any, List

logger = logging.getLogger(__name__)

# 默认读连接池大小
DEFAULT_READ_POOL_SIZE = 3


class ConnectionMixin:
    """
    数据库连接管理混入类

    提供：
    - 读写分离连接池（_init_pool, _close_pool）
    - 读连接获取/归还（_acquire_read_connection, _release_read_connection）
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
    # 连接池初始化（由子类在 __init__ 中调用）
    # -------------------------------------------------------------------------

    def _init_pool(self, pool_size: int = DEFAULT_READ_POOL_SIZE):
        """
        初始化读写分离连接池

        Args:
            pool_size: 读连接池大小，默认3
        """
        self._read_pool: List[tuple] = []  # (connection, lock) 列表
        self._write_conn: Optional[sqlite3.Connection] = None
        self._pool_size = pool_size

        # 预创建读连接池
        for _ in range(pool_size):
            conn = self._create_connection()
            lock = threading.Lock()
            self._read_pool.append((conn, lock))

        # 创建写连接
        self._write_conn = self._create_connection()

        logger.info(f"连接池初始化完成，读连接池大小: {pool_size}")

    def _create_connection(self) -> sqlite3.Connection:
        """创建一个配置好的数据库连接"""
        conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
            isolation_level=None  # 自动提交模式
        )
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        return conn

    def _close_pool(self):
        """关闭所有连接"""
        # 关闭读连接池
        for conn, _ in self._read_pool:
            try:
                conn.close()
            except Exception as e:
                logger.warning(f"关闭读连接失败: {e}")
        self._read_pool.clear()

        # 关闭写连接
        if self._write_conn:
            try:
                self._write_conn.close()
            except Exception as e:
                logger.warning(f"关闭写连接失败: {e}")
            self._write_conn = None

        logger.info("连接池已关闭")

    # -------------------------------------------------------------------------
    # 连接获取与归还
    # -------------------------------------------------------------------------

    @contextmanager
    def _acquire_read_connection(self):
        """
        从池中获取一个读连接的上下文管理器

        Usage:
            with self._acquire_read_connection() as (conn, lock):
                cursor = conn.cursor()
                cursor.execute(...)
        """
        if not self._read_pool:
            raise RuntimeError("连接池未初始化")

        # 获取一个可用连接（轮询选择）
        conn, lock = self._read_pool[0]
        # 简单轮询策略：每次从池首部取，用完后移到末尾
        self._read_pool = self._read_pool[1:] + [(conn, lock)]

        acquired = False
        try:
            yield conn, lock
            acquired = True
        finally:
            # 如果异常发生在 yield 之前，连接已在上面；异常后连接已归还
            pass

    def _get_write_connection(self) -> sqlite3.Connection:
        """获取写连接（内部使用，不对外暴露）"""
        if self._write_conn is None:
            raise RuntimeError("写连接未初始化")
        return self._write_conn

    # -------------------------------------------------------------------------
    # 事务管理（用于写操作）
    # -------------------------------------------------------------------------

    @contextmanager
    def _transaction(self):
        """
        事务上下文管理器（使用写连接）

        Usage:
            with self._transaction() as cursor:
                cursor.execute(...)
        """
        conn = self._get_write_connection()
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

    @staticmethod
    def _is_read_query(query: str) -> bool:
        """判断是否为读查询"""
        q = query.strip().upper()
        return q.startswith('SELECT') or q.startswith('PRAGMA')

    def _execute(
        self,
        query: str,
        params: Tuple = (),
        fetch: Optional[str] = None
    ) -> Optional[Any]:
        """
        执行SQL查询（读写分离）

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
        if self._is_read_query(query):
            return self._execute_read(query, params, fetch)
        else:
            return self._execute_write(query, params, fetch)

    def _execute_read(
        self,
        query: str,
        params: Tuple = (),
        fetch: Optional[str] = None
    ) -> Optional[Any]:
        """执行读查询（从连接池获取连接）"""
        try:
            with self._acquire_read_connection() as (conn, lock):
                with lock:
                    cursor = conn.cursor()
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
            logger.error(f"SQL读查询错误: {e}, 查询: {query}, 参数: {params}")
            raise

    def _execute_write(
        self,
        query: str,
        params: Tuple = (),
        fetch: Optional[str] = None
    ) -> Optional[Any]:
        """执行写查询（使用写连接 + 全局锁）"""
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
                logger.error(f"SQL写查询错误: {e}, 查询: {query}, 参数: {params}")
                raise
