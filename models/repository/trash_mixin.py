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

        # FTS5 自检：未启用则跳过 FTS5 同步（搜索降级 LIKE）
        self._trash_fts5_available = self._probe_trash_fts5(cursor)
        if not self._trash_fts5_available:
            logger.warning("垃圾桶数据库未启用 FTS5，搜索将降级 LIKE")

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
                source_db_path TEXT,
                tokens TEXT
            )
        ''')

        # 兼容旧库：补 tokens 列
        try:
            cursor.execute('ALTER TABLE trash_diaries ADD COLUMN tokens TEXT')
        except Exception:
            pass  # 列已存在

        # 创建垃圾桶标签表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trash_tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trash_diary_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                original_tag_id INTEGER,
                FOREIGN KEY (trash_diary_id) REFERENCES trash_diaries(id) ON DELETE CASCADE
            )
        ''')

        # 为已有表添加 original_tag_id 列（兼容旧数据库）
        try:
            cursor.execute('ALTER TABLE trash_tags ADD COLUMN original_tag_id INTEGER')
        except Exception:
            pass  # 列已存在

        # 创建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_trash_deleted_at ON trash_diaries(deleted_at)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_trash_content ON trash_diaries(content)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_trash_original_id ON trash_diaries(original_id)')

        # ---- FTS5（多语种）----
        if self._trash_fts5_available:
            cursor.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS trash_diary_fts USING fts5(
                    content,
                    tokens,
                    content='trash_diaries',
                    content_rowid='id',
                    tokenize='unicode61 remove_diacritics 2 categories ''L* N* Co'''
                )
            """)
            # 灌入已有数据
            cursor.execute(
                "INSERT OR REPLACE INTO trash_diary_fts(rowid, content, tokens) "
                "SELECT id, content, COALESCE(tokens, '') FROM trash_diaries"
            )
            # 回填缺失 tokens
            cursor.execute("SELECT id, content FROM trash_diaries WHERE tokens IS NULL OR tokens = ''")
            rows = cursor.fetchall()
            if rows:
                from utils.text_tokenizer import tokenize
                for row in rows:
                    tokens_str = ' '.join(tokenize(row['content'] or ''))
                    cursor.execute("UPDATE trash_diaries SET tokens = ? WHERE id = ?", (tokens_str, row['id']))
            # 触发器
            cursor.execute('''
                CREATE TRIGGER IF NOT EXISTS trash_fts_insert AFTER INSERT ON trash_diaries BEGIN
                    INSERT INTO trash_diary_fts(rowid, content, tokens) VALUES (new.id, new.content, COALESCE(new.tokens, ''));
                END
            ''')
            cursor.execute('''
                CREATE TRIGGER IF NOT EXISTS trash_fts_update AFTER UPDATE ON trash_diaries BEGIN
                    INSERT INTO trash_diary_fts(trash_diary_fts, rowid, content, tokens) VALUES ('delete', old.id, old.content, COALESCE(old.tokens, ''));
                    INSERT INTO trash_diary_fts(rowid, content, tokens) VALUES (new.id, new.content, COALESCE(new.tokens, ''));
                END
            ''')
            cursor.execute('''
                CREATE TRIGGER IF NOT EXISTS trash_fts_delete AFTER DELETE ON trash_diaries BEGIN
                    INSERT INTO trash_diary_fts(trash_diary_fts, rowid, content, tokens) VALUES ('delete', old.id, old.content, COALESCE(old.tokens, ''));
                END
            ''')

        # 启用WAL模式
        cursor.execute('PRAGMA journal_mode=WAL')
        cursor.execute('PRAGMA synchronous=NORMAL')
        cursor.execute('PRAGMA cache_size=10000')
        cursor.execute('PRAGMA temp_store=memory')

        conn.commit()
        logger.info("垃圾桶数据库初始化完成")

    def _probe_trash_fts5(self, cursor) -> bool:
        """自检 FTS5 是否在当前 SQLite 构建中可用"""
        try:
            cursor.execute("CREATE VIRTUAL TABLE _trash_fts5_probe USING fts5(x)")
            cursor.execute("DROP TABLE _trash_fts5_probe")
            return True
        except Exception as exc:
            logger.debug("垃圾桶 FTS5 自检失败: %s", exc)
            return False

    def compute_trash_tokens(self, content: str) -> str:
        """对垃圾桶的日记内容算预分词串（FTS5 不可用时返回空）"""
        if not content or not getattr(self, '_trash_fts5_available', False):
            return ''
        from utils.text_tokenizer import tokenize
        return ' '.join(tokenize(content))

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
            tokens = self.compute_trash_tokens(diary['content'])
            trash_cursor = trash_conn.cursor()
            trash_cursor.execute(
                """
                INSERT INTO trash_diaries
                (original_id, date, deleted_at, content, view_count, last_viewed_at, source_db_path, tokens)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    diary['id'],
                    diary['date'],
                    deleted_at,
                    diary['content'],
                    diary.get('view_count', 0),
                    diary.get('last_viewed_at'),
                    os.path.abspath(self.db_path),
                    tokens
                )
            )
            trash_diary_id = trash_cursor.lastrowid

            # 插入标签到垃圾桶
            for tag in tags:
                trash_cursor.execute(
                    "INSERT INTO trash_tags (trash_diary_id, name, original_tag_id) VALUES (?, ?, ?)",
                    (trash_diary_id, tag['name'], tag['id'])
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
            tokens = self.compute_tokens(trash_diary['content'])
            main_cursor.execute(
                """
                INSERT INTO diaries (date, content, view_count, last_viewed_at, tokens)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    trash_diary['date'],
                    trash_diary['content'],
                    trash_diary['view_count'],
                    trash_diary['last_viewed_at'],
                    tokens
                )
            )
            restored_diary_id = main_cursor.lastrowid

            # 恢复标签关联
            for tag in trash_tags:
                # 优先使用原始 tag_id 查找标签（精确恢复）
                tag_id = None
                if tag['original_tag_id']:
                    existing_tag = self.get_tag_by_id(tag['original_tag_id'])
                    if existing_tag:
                        tag_id = existing_tag['id']
                    else:
                        # 原始标签已被删除，通过名称查找或重建
                        existing_by_name = self.get_tag_by_name(tag['name'])
                        if existing_by_name:
                            tag_id = existing_by_name['id']
                        else:
                            # 标签完全不存在，需要重建
                            new_tag = self.add_tag(tag['name'])
                            if new_tag:
                                tag_id = new_tag['id']
                else:
                    # 兼容旧数据：没有 original_tag_id，通过名称查找
                    # 注意：tags.name 有唯一约束，同名标签必是同一标签，可直接关联
                    existing_by_name = self.get_tag_by_name(tag['name'])
                    if existing_by_name:
                        tag_id = existing_by_name['id']
                    else:
                        new_tag = self.add_tag(tag['name'])
                        if new_tag:
                            tag_id = new_tag['id']

                if tag_id:
                    main_cursor.execute(
                        "INSERT OR IGNORE INTO diary_tags (diary_id, tag_id) VALUES (?, ?)",
                        (restored_diary_id, tag_id)
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
        在垃圾桶中搜索日记（多语种分词 + FTS5 + LIKE 回退）

        Args:
            keyword: 搜索关键词
            limit: 限制数量

        Returns:
            匹配的垃圾桶日记列表
        """
        if not keyword or not keyword.strip():
            return self.get_all_trash_diaries(limit)

        from utils.text_tokenizer import build_fts_match, like_or_pattern

        fts_keyword = keyword.strip()
        match_expr, _ = build_fts_match(fts_keyword)
        if not match_expr:
            return []

        if getattr(self, '_trash_fts5_available', False):
            try:
                results = self._trash_execute(
                    """
                    SELECT td.*, GROUP_CONCAT(tt.name, ', ') as tag_names
                    FROM trash_diaries td
                    INNER JOIN trash_diary_fts fts ON td.id = fts.rowid
                    LEFT JOIN trash_tags tt ON td.id = tt.trash_diary_id
                    WHERE trash_diary_fts MATCH ?
                    GROUP BY td.id
                    ORDER BY td.deleted_at DESC
                    LIMIT ?
                    """,
                    (match_expr, limit),
                    fetch='all'
                ) or []
                if results:
                    return results
            except Exception as exc:
                logger.warning("垃圾桶 FTS5 MATCH 失败，回退 LIKE: %s", exc)

        # LIKE OR 兜底
        patterns = like_or_pattern(fts_keyword)
        if not patterns:
            return []
        conds = ' OR '.join('td.content LIKE ?' for _ in patterns)
        params = tuple(patterns) + (limit,)
        return self._trash_execute(
            f"""
            SELECT td.*, GROUP_CONCAT(tt.name, ', ') as tag_names
            FROM trash_diaries td
            LEFT JOIN trash_tags tt ON td.id = tt.trash_diary_id
            WHERE {conds}
            GROUP BY td.id
            ORDER BY td.deleted_at DESC
            LIMIT ?
            """,
            params,
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
