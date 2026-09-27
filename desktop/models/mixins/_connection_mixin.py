"""
数据库连接管理混入类
提供线程本地的数据库连接、事务管理和SQL执行功能
"""
from contextlib import contextmanager
import queue
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
    - 读连接借/还（_acquire_read_connection；基于 queue.Queue 借/还语义）
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

        设计要点：
        - 读池改为 queue.Queue，借/还语义清晰（get/put）
        - 每个连接有独立 Lock，但只在 cursor.execute 周围短暂持锁（见 _acquire_read_connection）
        - 写连接仍为单条，由 _db_lock 全局串行化
        """
        self._pool_size = pool_size
        # queue.Queue 提供原子 get/put；maxsize 与池大小一致即可
        self._read_pool: "queue.Queue[Tuple[sqlite3.Connection, threading.Lock]]" = queue.Queue(maxsize=pool_size)

        # 预创建读连接池
        for _ in range(pool_size):
            conn = self._create_connection()
            lock = threading.Lock()
            self._read_pool.put((conn, lock))

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
        # 排空读连接池
        while True:
            try:
                conn, _lock = self._read_pool.get_nowait()
            except queue.Empty:
                break
            try:
                conn.close()
            except Exception as e:
                logger.warning(f"关闭读连接失败: {e}")

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

        语义：借/还（不再轮转）。由 queue.Queue 保证并发安全。

        用法：
            with self._acquire_read_connection() as (conn, lock):
                cursor = conn.cursor()
                with lock:                # 只在 execute 周围持锁
                    cursor.execute(...)

        异常路径：
        - 任意异常时仍通过 finally 把连接 put 回池
        - 若异常发生在 cursor.execute 阶段，连接被污染，
          会替换为新连接再 put 回池（连接自愈）
        """
        try:
            conn, lock = self._read_pool.get(timeout=10.0)
        except queue.Empty as exc:
            raise RuntimeError("读连接池无可用连接（10s 超时）") from exc

        try:
            yield conn, lock
        except sqlite3.Error:
            # 连接可能已被污染：回滚 + 替换为新连接
            try:
                conn.rollback()
            except Exception:
                pass
            try:
                conn.close()
            except Exception:
                pass
            try:
                new_conn = self._create_connection()
                self._read_pool.put((new_conn, threading.Lock()))
            except Exception as heal_exc:
                logger.error(f"读连接自愈失败: {heal_exc}")
            raise
        finally:
            # 无论正常或异常归还，避免连接泄露
            # 注意：异常分支已 put(new_conn)，正常路径 put 原 conn
            # 池大小由 maxsize 保证；get 后 put 是 1:1
            try:
                self._read_pool.put_nowait((conn, lock))
            except queue.Full:
                # 池已满（理论上不会发生，除非有外部 put），关闭多余连接
                try:
                    conn.close()
                except Exception:
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
