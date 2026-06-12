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
        """
        初始化垃圾桶数据库连接池（单连接）

        垃圾桶 DB 路径跟随主库 self.db_path，避免不同主库共用同一份垃圾文件
        （旧实现走 get_db_config() 全局单例，会与历史默认路径串数据）
        """
        main_dir = os.path.dirname(self.db_path)
        main_basename = os.path.splitext(os.path.basename(self.db_path))[0]
        trash_db_path = os.path.join(main_dir, f"trash_{main_basename}.db")
        if main_dir:
            os.makedirs(main_dir, exist_ok=True)

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
        # date = 原日记创建时间；updated_at = 原日记最近编辑时间（可能为 NULL）
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
                tokens TEXT,
                updated_at TEXT
            )
        ''')

        # 兼容旧库：补 tokens 列
        try:
            cursor.execute('ALTER TABLE trash_diaries ADD COLUMN tokens TEXT')
        except Exception:
            pass  # 列已存在

        # 兼容旧库：补 updated_at 列（与 diaries 同步）
        try:
            cursor.execute('ALTER TABLE trash_diaries ADD COLUMN updated_at TEXT')
        except Exception:
            pass  # 列已存在

        # 回填旧库：updated_at 默认等于 date
        cursor.execute(
            'UPDATE trash_diaries SET updated_at = date '
            'WHERE updated_at IS NULL OR updated_at = ""'
        )

        # ---- 2PC 跨库协调：pending_trash_ops（垃圾桶库侧）----
        # 与主库的 pending_trash_ops 同构，op_id 全局对应
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pending_trash_ops (
                op_id TEXT PRIMARY KEY,
                op_type TEXT NOT NULL,
                diary_id INTEGER,
                trash_id INTEGER,
                payload TEXT NOT NULL,
                state TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL DEFAULT '',
                updated_at TEXT
            )
        ''')
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_pending_trash_state '
            'ON pending_trash_ops(state)'
        )

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
        将日记移动到垃圾桶（软删除）— 2PC 版本

        三阶段：
            1) precommit: 两库写 pending (state=pending)
            2) apply    : 主库 DELETE FROM diaries WHERE id=?
            3) commit   : 垃圾桶库 INSERT INTO trash_diaries/trash_tags

        Args:
            diary_id: 原日记ID

        Returns:
            被移动的日记字典或None
        """
        # 先获取日记完整信息（含标签）
        diary = self.get_diary_by_id(diary_id)
        if not diary:
            logger.warning(f"移动到垃圾桶失败，日记不存在: {diary_id}")
            return None

        # 获取日记的标签
        tags = self.get_tags_by_diary_id(diary_id)

        # 准备 payload（阶段 3 实际写入垃圾桶库所需）
        tokens = self.compute_trash_tokens(diary['content'])
        payload = {
            'date': diary['date'],
            'content': diary['content'],
            'view_count': diary.get('view_count', 0),
            'last_viewed_at': diary.get('last_viewed_at'),
            'updated_at': diary.get('updated_at'),
            'tokens': tokens,
            'tags': [
                {'name': t['name'], 'original_tag_id': t['id']}
                for t in tags
            ],
        }

        op_id = self._new_op_id()

        # 主库侧加 _db_lock 串行化（垃圾桶侧的事务都先经过主库）
        with self._db_lock:
            try:
                # 阶段 1
                self._precommit_trash_op(
                    op_id=op_id, op_type='move',
                    diary_id=diary_id, trash_id=None, payload=payload
                )
                # 阶段 2
                self._apply_trash_op_main(
                    op_id=op_id, op_type='move',
                    diary_id=diary_id, trash_id=None, payload=payload
                )
                # 阶段 3
                self._commit_trash_op_trash(
                    op_id=op_id, op_type='move',
                    diary_id=diary_id, trash_id=None, payload=payload
                )
            except Exception as e:
                # 任意阶段失败：清理 pending 行（两库）
                logger.error(f"2PC move_to_trash 失败: {e}")
                self._cleanup_pending_op(op_id)
                raise

        # 容量管理（保持原行为）
        self._enforce_trash_cache_size()

        # 取回新建的 trash_id
        new_trash = self._trash_execute(
            "SELECT id FROM trash_diaries WHERE original_id = ? "
            "ORDER BY id DESC LIMIT 1",
            (diary_id,),
            fetch='one'
        )
        new_trash_id = new_trash['id'] if new_trash else None

        deleted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"日记 {diary_id} 已移动到垃圾桶，op_id: {op_id}")
        return {
            'trash_id': new_trash_id,
            'original_id': diary_id,
            'deleted_at': deleted_at,
            'op_id': op_id,
        }

    # ============================================================
    # 从垃圾桶恢复
    # ============================================================

    def restore_from_trash(self, trash_id: int) -> Optional[Dict[str, Any]]:
        """
        从垃圾桶恢复日记 — 2PC 版本

        三阶段：
            1) precommit: 两库写 pending (state=pending)
            2) apply    : 主库 INSERT INTO diaries + diary_tags
            3) commit   : 垃圾桶库 DELETE FROM trash_diaries

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
        ) or []

        # 准备 payload（阶段 2 实际写入主库所需）
        tokens = self.compute_tokens(trash_diary['content'])
        payload = {
            'date': trash_diary['date'],
            'content': trash_diary['content'],
            'view_count': trash_diary.get('view_count', 0),
            'last_viewed_at': trash_diary.get('last_viewed_at'),
            'updated_at': trash_diary.get('updated_at'),
            'tokens': tokens,
            'tags': [
                {
                    'name': t['name'],
                    'original_tag_id': t.get('original_tag_id'),
                }
                for t in trash_tags
            ],
        }

        op_id = self._new_op_id()

        with self._db_lock:
            try:
                # 阶段 1
                self._precommit_trash_op(
                    op_id=op_id, op_type='restore',
                    diary_id=trash_diary.get('original_id'),
                    trash_id=trash_id, payload=payload
                )
                # 阶段 2
                self._apply_trash_op_main(
                    op_id=op_id, op_type='restore',
                    diary_id=trash_diary.get('original_id'),
                    trash_id=trash_id, payload=payload
                )
                # 阶段 3
                self._commit_trash_op_trash(
                    op_id=op_id, op_type='restore',
                    diary_id=trash_diary.get('original_id'),
                    trash_id=trash_id, payload=payload
                )
            except Exception as e:
                logger.error(f"2PC restore_from_trash 失败: {e}")
                self._cleanup_pending_op(op_id)
                raise

        # 取回新插入的 diary_id
        new_diary = self._execute(
            "SELECT id FROM diaries WHERE date = ? AND content = ? "
            "ORDER BY id DESC LIMIT 1",
            (trash_diary['date'], trash_diary['content']),
            fetch='one'
        )
        if new_diary:
            logger.info(f"日记已从垃圾桶恢复，op_id: {op_id}, 新ID: {new_diary['id']}")
            return self.get_diary_by_id(new_diary['id'])
        return None

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

    # ============================================================
    # 2PC 跨库两阶段提交（move / restore 协调器 + 启动恢复）
    # ============================================================
    #
    # 旧实现的隐患：
    #   move_to_trash 在两个不同的 sqlite3 连接上完成 INSERT/DELETE；
    #   中间崩溃会留下"主库已删但垃圾桶无记录"或"主库未删但垃圾桶已记录"，
    #   造成永久丢失或重复。
    #
    # 新实现（三阶段，2PC 风格）：
    #   1) precommit  : 在主库 + 垃圾桶库各写一行 pending_trash_ops（state='pending'）
    #   2) apply      : 在主库做"真实写"（move=DELETE, restore=INSERT），并把双方 state 标 'applied'
    #   3) commit     : 在垃圾桶库做"真实写"（move=INSERT, restore=DELETE），并把双方 state 标 'committed'
    #
    # 崩溃恢复（_recover_pending_trash_ops，启动时调用一次）：
    #   - state='committed'           -> 无事可做
    #   - state='applied' (两库一致)  -> 走 phase 3 commit
    #   - state='pending' (两库一致)  -> 删除两侧 pending（无副作用回滚）
    #   - 状态不一致                 -> 以主库为准，垃圾桶库补齐到与主库一致后重放后续阶段
    # ----------------------------------------------------------------

    @staticmethod
    def _new_op_id() -> str:
        """生成全局唯一 op_id（3.8 兼容：用 uuid4）"""
        import uuid
        return str(uuid.uuid4())

    def _precommit_trash_op(self, op_id: str, op_type: str,
                            diary_id, trash_id, payload: Dict[str, Any]) -> None:
        """阶段1：在两库各写一行 pending（state=pending）"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        import json
        payload_text = json.dumps(payload, ensure_ascii=False, default=str)

        # 主库写 pending
        with self._transaction() as cursor:
            cursor.execute(
                """
                INSERT INTO pending_trash_ops
                (op_id, op_type, diary_id, trash_id, payload, state, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)
                """,
                (op_id, op_type, diary_id, trash_id, payload_text, now, now)
            )

        # 垃圾桶库写 pending
        with self._trash_lock:
            trash_conn = self._get_trash_connection()
            trash_cursor = trash_conn.cursor()
            try:
                trash_cursor.execute("BEGIN")
                trash_cursor.execute(
                    """
                    INSERT INTO pending_trash_ops
                    (op_id, op_type, diary_id, trash_id, payload, state, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)
                    """,
                    (op_id, op_type, diary_id, trash_id, payload_text, now, now)
                )
                trash_conn.commit()
            except Exception:
                trash_conn.rollback()
                raise

    def _apply_trash_op_main(self, op_id: str, op_type: str,
                             diary_id, trash_id, payload: Dict[str, Any]) -> None:
        """
        阶段2：在主库做"真实写"，并把两库 state 标 'applied'

        - move   : DELETE FROM diaries WHERE id = ?
        - restore: INSERT INTO diaries (...) VALUES (...)
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with self._transaction() as cursor:
            if op_type == 'move':
                cursor.execute("DELETE FROM diaries WHERE id = ?", (diary_id,))
            elif op_type == 'restore':
                cursor.execute(
                    """
                    INSERT INTO diaries
                    (date, content, view_count, last_viewed_at, tokens, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        payload['date'],
                        payload['content'],
                        payload.get('view_count', 0),
                        payload.get('last_viewed_at'),
                        payload.get('tokens', ''),
                        payload.get('updated_at'),
                    )
                )
                # 恢复标签
                for tag in payload.get('tags', []):
                    tag_id = None
                    if tag.get('original_tag_id'):
                        existing = self.get_tag_by_id(tag['original_tag_id'])
                        if existing:
                            tag_id = existing['id']
                    if tag_id is None and tag.get('name'):
                        existing_by_name = self.get_tag_by_name(tag['name'])
                        if existing_by_name:
                            tag_id = existing_by_name['id']
                        else:
                            new_tag = self.add_tag(tag['name'])
                            if new_tag:
                                tag_id = new_tag['id']
                    if tag_id:
                        cursor.execute(
                            "INSERT OR IGNORE INTO diary_tags (diary_id, tag_id) "
                            "VALUES (?, ?)",
                            (cursor.lastrowid, tag_id)
                        )
            else:
                raise ValueError(f"未知 op_type: {op_type!r}")

            # 把状态推进到 applied
            cursor.execute(
                "UPDATE pending_trash_ops SET state = 'applied', updated_at = ? "
                "WHERE op_id = ?",
                (now, op_id)
            )

        # 同步垃圾桶库的 state
        with self._trash_lock:
            trash_conn = self._get_trash_connection()
            trash_cursor = trash_conn.cursor()
            try:
                trash_cursor.execute("BEGIN")
                trash_cursor.execute(
                    "UPDATE pending_trash_ops SET state = 'applied', updated_at = ? "
                    "WHERE op_id = ?",
                    (now, op_id)
                )
                trash_conn.commit()
            except Exception:
                trash_conn.rollback()
                raise

    def _commit_trash_op_trash(self, op_id: str, op_type: str,
                               diary_id, trash_id, payload: Dict[str, Any]) -> None:
        """
        阶段3：在垃圾桶库做"真实写"，并把两库 state 标 'committed'

        - move   : INSERT INTO trash_diaries/trash_tags
        - restore: DELETE FROM trash_diaries WHERE id = ?
        """
        import os
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with self._trash_lock:
            trash_conn = self._get_trash_connection()
            trash_cursor = trash_conn.cursor()
            try:
                trash_cursor.execute("BEGIN")

                if op_type == 'move':
                    deleted_at = now
                    trash_cursor.execute(
                        """
                        INSERT INTO trash_diaries
                        (original_id, date, deleted_at, content, view_count,
                         last_viewed_at, source_db_path, tokens, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            diary_id,
                            payload['date'],
                            deleted_at,
                            payload['content'],
                            payload.get('view_count', 0),
                            payload.get('last_viewed_at'),
                            os.path.abspath(self.db_path),
                            payload.get('tokens', ''),
                            payload.get('updated_at'),
                        )
                    )
                    new_trash_id = trash_cursor.lastrowid
                    for tag in payload.get('tags', []):
                        trash_cursor.execute(
                            "INSERT INTO trash_tags "
                            "(trash_diary_id, name, original_tag_id) VALUES (?, ?, ?)",
                            (new_trash_id, tag['name'], tag.get('original_tag_id'))
                        )
                elif op_type == 'restore':
                    trash_cursor.execute(
                        "DELETE FROM trash_diaries WHERE id = ?", (trash_id,)
                    )
                else:
                    raise ValueError(f"未知 op_type: {op_type!r}")

                trash_cursor.execute(
                    "UPDATE pending_trash_ops SET state = 'committed', updated_at = ? "
                    "WHERE op_id = ?",
                    (now, op_id)
                )
                trash_conn.commit()
            except Exception:
                trash_conn.rollback()
                raise

        # 同步主库的 state
        with self._transaction() as cursor:
            cursor.execute(
                "UPDATE pending_trash_ops SET state = 'committed', updated_at = ? "
                "WHERE op_id = ?",
                (now, op_id)
            )

    def _recover_pending_trash_ops(self) -> int:
        """
        启动恢复：扫描两库 pending_trash_ops，推进到稳定态

        状态机：
            两库 state 一致且 committed -> 删除两侧记录（清理）
            两库 state 一致且 applied   -> 重放阶段3 commit
            两库 state 一致且 pending   -> 删除两侧记录（视为未发生）
            状态不一致                  -> 以主库为准，把垃圾桶库补齐后重放

        Returns:
            恢复/清理的 op 数量
        """
        try:
            main_rows = self._execute(
                "SELECT op_id, op_type, diary_id, trash_id, payload, state, "
                "created_at, updated_at "
                "FROM pending_trash_ops",
                fetch='all'
            ) or []
        except Exception as exc:
            logger.warning(f"读取主库 pending_trash_ops 失败: {exc}")
            main_rows = []

        try:
            with self._trash_lock:
                trash_conn = self._get_trash_connection()
                trash_cursor = trash_conn.cursor()
                trash_cursor.execute(
                    "SELECT op_id, op_type, diary_id, trash_id, payload, state, "
                    "created_at, updated_at "
                    "FROM pending_trash_ops"
                )
                trash_rows = [dict(r) for r in trash_cursor.fetchall()]
        except Exception as exc:
            logger.warning(f"读取垃圾桶库 pending_trash_ops 失败: {exc}")
            trash_rows = []

        main_by_id = {r['op_id']: r for r in main_rows}
        trash_by_id = {r['op_id']: r for r in trash_rows}
        all_op_ids = set(main_by_id) | set(trash_by_id)

        recovered = 0
        import json

        for op_id in all_op_ids:
            m = main_by_id.get(op_id)
            t = trash_by_id.get(op_id)
            # 主库已 committed -> 垃圾桶库可能漏写 phase 3
            if m and m['state'] == 'committed' and (not t or t['state'] != 'committed'):
                payload = json.loads(m['payload']) if isinstance(m['payload'], str) else m['payload']
                try:
                    self._commit_trash_op_trash(
                        op_id, m['op_type'], m['diary_id'], m['trash_id'], payload
                    )
                    logger.info(f"2PC 恢复: {op_id} 阶段3 重放 (主库已 committed)")
                    recovered += 1
                except Exception as exc:
                    logger.error(f"2PC 恢复失败 {op_id}: {exc}")
                continue

            # 两库都 applied -> 重放阶段 3
            if m and t and m['state'] == 'applied' and t['state'] == 'applied':
                payload = json.loads(m['payload']) if isinstance(m['payload'], str) else m['payload']
                try:
                    self._commit_trash_op_trash(
                        op_id, m['op_type'], m['diary_id'], m['trash_id'], payload
                    )
                    logger.info(f"2PC 恢复: {op_id} 阶段3 重放 (两库 applied)")
                    recovered += 1
                except Exception as exc:
                    logger.error(f"2PC 恢复失败 {op_id}: {exc}")
                continue

            # 两库都 pending -> 安全清理（无副作用）
            if (not m or m['state'] == 'pending') and (not t or t['state'] == 'pending'):
                self._cleanup_pending_op(op_id)
                logger.info(f"2PC 恢复: {op_id} 阶段1 pending 清理")
                recovered += 1
                continue

            # 其他不一致情形 -> 以主库为准：把垃圾桶库对齐到主库
            if m and not t:
                # 垃圾桶库缺行：补上
                self._mirror_pending_to_trash(m)
                logger.info(f"2PC 恢复: {op_id} 补齐垃圾桶库 pending 行")
            elif t and not m:
                # 主库缺行：补上
                self._mirror_pending_to_main(t)
                logger.info(f"2PC 恢复: {op_id} 补齐主库 pending 行")

        return recovered

    def _cleanup_pending_op(self, op_id: str) -> None:
        """删除两库指定 op_id 的 pending 行"""
        try:
            with self._transaction() as cursor:
                cursor.execute("DELETE FROM pending_trash_ops WHERE op_id = ?", (op_id,))
        except Exception as exc:
            logger.warning(f"清理主库 pending 失败 {op_id}: {exc}")
        try:
            with self._trash_lock:
                trash_conn = self._get_trash_connection()
                trash_cursor = trash_conn.cursor()
                trash_cursor.execute("BEGIN")
                trash_cursor.execute(
                    "DELETE FROM pending_trash_ops WHERE op_id = ?", (op_id,)
                )
                trash_conn.commit()
        except Exception as exc:
            logger.warning(f"清理垃圾桶库 pending 失败 {op_id}: {exc}")

    def _mirror_pending_to_trash(self, main_row) -> None:
        """把主库的 pending 行镜像到垃圾桶库"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._trash_lock:
            trash_conn = self._get_trash_connection()
            trash_cursor = trash_conn.cursor()
            try:
                trash_cursor.execute("BEGIN")
                trash_cursor.execute(
                    """
                    INSERT OR REPLACE INTO pending_trash_ops
                    (op_id, op_type, diary_id, trash_id, payload, state,
                     created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, COALESCE(?, ''), ?)
                    """,
                    (
                        main_row['op_id'],
                        main_row['op_type'],
                        main_row['diary_id'],
                        main_row['trash_id'],
                        main_row['payload'],
                        main_row['state'],
                        main_row.get('created_at') or '',
                        main_row.get('updated_at') or now,
                    )
                )
                trash_conn.commit()
            except Exception:
                trash_conn.rollback()
                raise

    def _mirror_pending_to_main(self, trash_row) -> None:
        """把垃圾桶库的 pending 行镜像到主库"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._transaction() as cursor:
            cursor.execute(
                """
                INSERT OR REPLACE INTO pending_trash_ops
                (op_id, op_type, diary_id, trash_id, payload, state,
                 created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, COALESCE(?, ''), ?)
                """,
                (
                    trash_row['op_id'],
                    trash_row['op_type'],
                    trash_row['diary_id'],
                    trash_row['trash_id'],
                    trash_row['payload'],
                    trash_row['state'],
                    trash_row.get('created_at') or '',
                    trash_row.get('updated_at') or now,
                )
            )
