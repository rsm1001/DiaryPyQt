"""
垃圾桶操作混入类
负责日记的删除（移动到垃圾桶）、恢复、搜索和容量管理
"""
import sqlite3
import os
import threading
import logging
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class TrashMixin:
    """垃圾桶操作混入类，提供日记的软删除和恢复功能"""

    # ============================================================
    # 垃圾桶数据库初始化
    # ============================================================

    def _init_trash_pool(self):
        """初始化垃圾桶数据库连接池（单连接）"""
        from models.config.db_config import get_db_config
        trash_db_path = get_db_config().get_trash_db_path()
        os.makedirs(os.path.dirname(trash_db_path) or '.', exist_ok=True)

        self._trash_conn = sqlite3.connect(
            trash_db_path,
            check_same_thread=False,
            isolation_level=None
        )
        self._trash_conn.execute("PRAGMA foreign_keys = ON")
        self._trash_conn.row_factory = sqlite3.Row
        self._trash_lock = threading.Lock()

    def _close_trash_pool(self):
        """关闭垃圾桶数据库连接"""
        if hasattr(self, '_trash_conn') and self._trash_conn:
            try:
                self._trash_conn.close()
            except Exception as e:
                logger.warning(f"关闭垃圾桶连接失败: {e}")
            self._trash_conn = None

    def _get_trash_connection(self) -> sqlite3.Connection:
        """获取垃圾桶数据库连接"""
        if not hasattr(self, '_trash_conn') or self._trash_conn is None:
            self._init_trash_pool()
        return self._trash_conn

    def _init_trash_database(self):
        """初始化垃圾桶数据库表"""
        conn = self._get_trash_connection()
        cursor = conn.cursor()

        # 创建垃圾桶日记表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trash_diaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_id INTEGER,
                date TEXT NOT NULL,
                deleted_at TEXT NOT NULL,
                content TEXT NOT NULL,
                view_count INTEGER DEFAULT 0,
                last_viewed_at TEXT,
                source_db_path TEXT
            )
        ''')

        # 创建垃圾桶标签表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trash_tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trash_diary_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                FOREIGN KEY (trash_diary_id) REFERENCES trash_diaries(id) ON DELETE CASCADE
            )
        ''')

        # 创建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_trash_deleted_at ON trash_diaries(deleted_at)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_trash_content ON trash_diaries(content)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_trash_original_id ON trash_diaries(original_id)')

        # 启用WAL模式
        cursor.execute('PRAGMA journal_mode=WAL')
        cursor.execute('PRAGMA synchronous=NORMAL')
        cursor.execute('PRAGMA cache_size=10000')
        cursor.execute('PRAGMA temp_store=memory')

        conn.commit()
        logger.info("垃圾桶数据库初始化完成")

    @contextmanager
    def _trash_transaction(self):
        """垃圾桶数据库事务上下文管理器"""
        conn = self._get_trash_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("BEGIN")
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"垃圾桶事务回滚: {e}")
            raise

    def _trash_execute(
        self,
        query: str,
        params: Tuple = (),
        fetch: Optional[str] = None
    ) -> Optional[Any]:
        """执行垃圾桶数据库SQL查询"""
        with self._trash_lock:
            try:
                with self._trash_transaction() as cursor:
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
                logger.error(f"垃圾桶SQL执行错误: {e}, 查询: {query}, 参数: {params}")
                raise

    # ============================================================
    # 移动到垃圾桶（软删除）
    # ============================================================

    def move_to_trash(self, diary_id: int) -> Optional[Dict[str, Any]]:
        """
        将日记移动到垃圾桶（软删除）

        Args:
            diary_id: 原日记ID

        Returns:
            被移动的日记字典或None
        """
        import os

        # 先获取日记完整信息（含标签）
        diary = self.get_diary_by_id(diary_id)
        if not diary:
            logger.warning(f"移动到垃圾桶失败，日记不存在: {diary_id}")
            return None

        # 获取日记的标签
        tags = self.get_tags_by_diary_id(diary_id)

        # 获取主数据库写连接和垃圾桶连接
        main_conn = self._get_write_connection()
        trash_conn = self._get_trash_connection()

        try:
            # 在垃圾桶数据库中插入
            deleted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            trash_cursor = trash_conn.cursor()
            trash_cursor.execute(
                """
                INSERT INTO trash_diaries
                (original_id, date, deleted_at, content, view_count, last_viewed_at, source_db_path)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    diary['id'],
                    diary['date'],
                    deleted_at,
                    diary['content'],
                    diary.get('view_count', 0),
                    diary.get('last_viewed_at'),
                    os.path.abspath(self.db_path)
                )
            )
            trash_diary_id = trash_cursor.lastrowid

            # 插入标签到垃圾桶
            for tag in tags:
                trash_cursor.execute(
                    "INSERT INTO trash_tags (trash_diary_id, name) VALUES (?, ?)",
                    (trash_diary_id, tag['name'])
                )

            # 从原数据库删除（外键会级联删除diary_tags）
            main_cursor = main_conn.cursor()
            main_cursor.execute("DELETE FROM diaries WHERE id = ?", (diary_id,))

            # 执行容量管理
            self._enforce_trash_cache_size()

            logger.info(f"日记 {diary_id} 已移动到垃圾桶，垃圾桶ID: {trash_diary_id}")
            return {
                'trash_id': trash_diary_id,
                'original_id': diary_id,
                'deleted_at': deleted_at
            }

        except Exception as e:
            logger.error(f"移动到垃圾桶失败: {e}")
            raise

    # ============================================================
    # 从垃圾桶恢复
    # ============================================================

    def restore_from_trash(self, trash_id: int) -> Optional[Dict[str, Any]]:
        """
        从垃圾桶恢复日记

        Args:
            trash_id: 垃圾桶中的日记ID

        Returns:
            恢复的日记字典或None
        """
        # 获取垃圾桶中的日记
        trash_diary = self._trash_execute(
            "SELECT * FROM trash_diaries WHERE id = ?",
            (trash_id,),
            fetch='one'
        )

        if not trash_diary:
            logger.warning(f"恢复失败，垃圾桶日记不存在: {trash_id}")
            return None

        # 获取垃圾桶中的标签
        trash_tags = self._trash_execute(
            "SELECT * FROM trash_tags WHERE trash_diary_id = ?",
            (trash_id,),
            fetch='all'
        )

        # 获取主数据库写连接和垃圾桶连接
        main_conn = self._get_write_connection()
        trash_conn = self._get_trash_connection()

        try:
            main_cursor = main_conn.cursor()
            trash_cursor = trash_conn.cursor()

            # 恢复到原数据库（使用新的自增ID）
            main_cursor.execute(
                """
                INSERT INTO diaries (date, content, view_count, last_viewed_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    trash_diary['date'],
                    trash_diary['content'],
                    trash_diary['view_count'],
                    trash_diary['last_viewed_at']
                )
            )
            restored_diary_id = main_cursor.lastrowid

            # 恢复标签关联
            for tag in trash_tags:
                # 先确保标签存在（可能已被删除）
                main_cursor.execute(
                    "INSERT OR IGNORE INTO tags (name) VALUES (?)",
                    (tag['name'],)
                )
                # 获取标签ID
                main_cursor.execute(
                    "SELECT id FROM tags WHERE name = ?",
                    (tag['name'],)
                )
                tag_row = main_cursor.fetchone()
                if tag_row:
                    main_cursor.execute(
                        "INSERT OR IGNORE INTO diary_tags (diary_id, tag_id) VALUES (?, ?)",
                        (restored_diary_id, tag_row['id'])
                    )

            # 从垃圾桶中删除
            trash_cursor.execute("DELETE FROM trash_diaries WHERE id = ?", (trash_id,))

            logger.info(f"日记已从垃圾桶恢复，新ID: {restored_diary_id}")
            return self.get_diary_by_id(restored_diary_id)

        except Exception as e:
            logger.error(f"从垃圾桶恢复失败: {e}")
            raise

    # ============================================================
    # 垃圾桶列表和搜索
    # ============================================================

    def get_all_trash_diaries(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        获取所有垃圾桶中的日记

        Args:
            limit: 限制数量

        Returns:
            垃圾桶日记列表（按删除时间倒序）
        """
        query = """
            SELECT td.*, GROUP_CONCAT(tt.name, ', ') as tag_names
            FROM trash_diaries td
            LEFT JOIN trash_tags tt ON td.id = tt.trash_diary_id
            GROUP BY td.id
            ORDER BY td.deleted_at DESC
        """
        params: Tuple = ()

        if limit is not None:
            query += " LIMIT ?"
            params = (limit,)

        return self._trash_execute(query, params, fetch='all') or []

    def get_trash_diary_by_id(self, trash_id: int) -> Optional[Dict[str, Any]]:
        """
        根据垃圾桶ID获取日记

        Args:
            trash_id: 垃圾桶日记ID

        Returns:
            垃圾桶日记字典或None
        """
        return self._trash_execute(
            "SELECT * FROM trash_diaries WHERE id = ?",
            (trash_id,),
            fetch='one'
        )

    def search_trash_by_keyword(self, keyword: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        在垃圾桶中搜索日记

        Args:
            keyword: 搜索关键词
            limit: 限制数量

        Returns:
            匹配的垃圾桶日记列表
        """
        if not keyword or not keyword.strip():
            return self.get_all_trash_diaries(limit)

        return self._trash_execute(
            """
            SELECT td.*, GROUP_CONCAT(tt.name, ', ') as tag_names
            FROM trash_diaries td
            LEFT JOIN trash_tags tt ON td.id = tt.trash_diary_id
            WHERE td.content LIKE ?
            GROUP BY td.id
            ORDER BY td.deleted_at DESC
            LIMIT ?
            """,
            (f"%{keyword.strip()}%", limit),
            fetch='all'
        ) or []

    def get_trash_count(self) -> int:
        """
        获取垃圾桶中的日记数量

        Returns:
            垃圾桶日记数量
        """
        result = self._trash_execute(
            "SELECT COUNT(*) as count FROM trash_diaries",
            fetch='one'
        )
        return result['count'] if result else 0

    # ============================================================
    # 永久删除
    # ============================================================

    def permanently_delete_trash(self, trash_id: int) -> bool:
        """
        永久删除垃圾桶中的日记

        Args:
            trash_id: 垃圾桶日记ID

        Returns:
            是否删除成功
        """
        rowcount = self._trash_execute(
            "DELETE FROM trash_diaries WHERE id = ?",
            (trash_id,),
            fetch='rowcount'
        )

        if rowcount > 0:
            logger.info(f"永久删除垃圾桶日记: {trash_id}")
            return True
        return False

    def empty_trash(self) -> int:
        """
        清空整个垃圾桶

        Returns:
            删除的日记数量
        """
        count = self.get_trash_count()
        self._trash_execute("DELETE FROM trash_diaries", fetch='rowcount')
        logger.info(f"垃圾桶已清空，共删除 {count} 篇日记")
        return count

    # ============================================================
    # 容量管理
    # ============================================================

    def _enforce_trash_cache_size(self):
        """强制执行垃圾桶容量限制（LRU淘汰）"""
        from models.config.db_config import get_db_config
        max_size = get_db_config().get_trash_cache_size()

        conn = self._get_trash_connection()
        with self._trash_lock:
            cursor = conn.cursor()
            cursor.execute("BEGIN")
            try:
                cursor.execute("SELECT COUNT(*) as count FROM trash_diaries")
                row = cursor.fetchone()
                current_count = row['count'] if row else 0

                if current_count <= max_size:
                    conn.commit()
                    return

                delete_count = current_count - max_size
                cursor.execute(
                    """
                    DELETE FROM trash_diaries
                    WHERE id IN (
                        SELECT id FROM trash_diaries
                        ORDER BY deleted_at ASC
                        LIMIT ?
                    )
                    """,
                    (delete_count,)
                )
                conn.commit()
                logger.info(f"垃圾桶容量超限，已自动淘汰最早的 {delete_count} 条记录")
            except Exception:
                conn.rollback()
                logger.error("垃圾桶容量强制执行失败")
                raise

    # ============================================================
    # 双击恢复快捷方法
    # ============================================================

    def restore_from_trash_by_double_click(self, trash_id: int) -> Optional[Dict[str, Any]]:
        """
        双击恢复日记（别名方法，行为同 restore_from_trash）

        Args:
            trash_id: 垃圾桶日记ID

        Returns:
            恢复的日记字典或None
        """
        return self.restore_from_trash(trash_id)
