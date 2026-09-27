"""
垃圾桶数据库连接管理

提供独立的 sqlite3 连接池与事务上下文。

设计要点：
- 与主库同目录、文件名同主库（trash_<basename>.db），避免与历史全局单例串数据
- 读写均使用单连接 + 线程锁序列化；与主库读写分离连接池保持一致语义
- 通过 Protocol 暴露连接、锁、事务、execute 等接口，供上层 service 依赖注入
"""
import logging
import os
import sqlite3
import threading
from contextlib import contextmanager
from typing import Any, Optional, Protocol, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 连接 / 事务协议（供依赖注入）
# ---------------------------------------------------------------------------

class _TrashConnectionLike(Protocol):
    """垃圾桶连接模块对外暴露的最小接口协议。"""
    @property
    def connection(self) -> sqlite3.Connection: ...
    @property
    def lock(self) -> threading.Lock: ...
    def close(self) -> None: ...
    def execute(
        self,
        query: str,
        params: Tuple = (),
        fetch: Optional[str] = None,
    ) -> Optional[Any]: ...
    def transaction(self): ...


# ---------------------------------------------------------------------------
# 连接池实现
# ---------------------------------------------------------------------------

class TrashConnectionPool:
    """垃圾桶数据库单连接池（与主库目录绑定）"""

    def __init__(self, main_db_path: str):
        # 垃圾桶 DB 路径跟随主库 self.db_path，避免不同主库共用同一份垃圾文件
        # 旧实现走 get_db_config() 全局单例，会与历史默认路径串数据
        main_dir = os.path.dirname(main_db_path)
        main_basename = os.path.splitext(os.path.basename(main_db_path))[0]
        trash_db_path = os.path.join(main_dir, f"trash_{main_basename}.db")
        if main_dir:
            os.makedirs(main_dir, exist_ok=True)

        self._db_path = trash_db_path
        self._conn: Optional[sqlite3.Connection] = sqlite3.connect(
            trash_db_path,
            check_same_thread=False,
            isolation_level=None,
        )
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        logger.info("垃圾桶连接池已初始化: %s", trash_db_path)

    @property
    def db_path(self) -> str:
        """垃圾桶数据库文件路径"""
        return self._db_path

    @property
    def connection(self) -> sqlite3.Connection:
        """当前 sqlite3 连接"""
        if self._conn is None:
            raise RuntimeError("垃圾桶连接已关闭，无法访问")
        return self._conn

    @property
    def lock(self) -> threading.Lock:
        """垃圾桶连接访问锁（与主库 _db_lock 同语义）"""
        return self._lock

    def close(self) -> None:
        """关闭垃圾桶数据库连接（幂等）"""
        if self._conn is None:
            return
        try:
            self._conn.close()
            logger.info("垃圾桶连接池已关闭: %s", self._db_path)
        except Exception as exc:
            logger.warning("关闭垃圾桶连接失败: %s", exc)
        finally:
            self._conn = None

    @contextmanager
    def transaction(self):
        """垃圾桶数据库事务上下文管理器

        异常时自动回滚并重新抛出，调用方无需关心事务边界。
        """
        if self._conn is None:
            raise RuntimeError("垃圾桶连接已关闭，无法开启事务")
        cursor = self._conn.cursor()
        try:
            cursor.execute("BEGIN")
            yield cursor
            self._conn.commit()
        except Exception as exc:
            self._conn.rollback()
            logger.error("垃圾桶事务回滚: %s", exc)
            raise

    def execute(
        self,
        query: str,
        params: Tuple = (),
        fetch: Optional[str] = None,
    ) -> Optional[Any]:
        """执行垃圾桶数据库 SQL 查询

        Args:
            query: SQL 语句
            params: 参数元组
            fetch: 获取类型（'one' / 'all' / 'rowcount' / None）

        Returns:
            与 fetch 类型对应的结果
        """
        with self._lock:
            try:
                with self.transaction() as cursor:
                    cursor.execute(query, params)
                    if fetch == 'one':
                        row = cursor.fetchone()
                        return dict(row) if row else None
                    if fetch == 'all':
                        rows = cursor.fetchall()
                        return [dict(r) for r in rows]
                    if fetch == 'rowcount':
                        return cursor.rowcount
                    return cursor.lastrowid
            except sqlite3.Error as exc:
                logger.error(
                    "垃圾桶 SQL 执行错误: %s, 查询: %s, 参数: %s",
                    exc, query, params,
                )
                raise
