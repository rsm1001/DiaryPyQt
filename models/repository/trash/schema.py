"""
垃圾桶数据库 Schema 初始化

负责：
- FTS5 自检
- 垃圾桶日记表 / 标签表 / 跨库协调表 (pending_trash_ops) 建表
- 兼容旧库：列补齐、updated_at 回填
- FTS5 全文搜索表与触发器
- PRAGMA 性能参数
"""
import logging
from typing import Optional

from .connection import TrashConnectionPool

logger = logging.getLogger(__name__)


class TrashSchemaInitializer:
    """垃圾桶数据库 Schema 初始化器"""

    def __init__(self, connection_pool: TrashConnectionPool):
        self._pool = connection_pool
        self._fts5_available: bool = False

    @property
    def fts5_available(self) -> bool:
        """FTS5 是否在当前 SQLite 构建中可用"""
        return self._fts5_available

    # ------------------------------------------------------------------
    # 公开入口
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        """初始化垃圾桶数据库（表 + 索引 + FTS5 + PRAGMA）"""
        conn = self._pool.connection
        cursor = conn.cursor()

        # FTS5 自检：未启用则跳过 FTS5 同步（搜索降级 LIKE）
        self._fts5_available = self._probe_fts5(cursor)
        if not self._fts5_available:
            logger.warning("垃圾桶数据库未启用 FTS5，搜索将降级 LIKE")

        self._create_diaries_table(cursor)
        self._create_pending_ops_table(cursor)
        self._create_tags_table(cursor)
        self._create_indexes(cursor)
        if self._fts5_available:
            self._create_fts5_artefacts(cursor)
        self._apply_perf_pragmas(cursor)

        conn.commit()
        logger.info("垃圾桶数据库初始化完成")

    # ------------------------------------------------------------------
    # FTS5 自检
    # ------------------------------------------------------------------

    def _probe_fts5(self, cursor) -> bool:
        """自检 FTS5 是否在当前 SQLite 构建中可用"""
        try:
            cursor.execute("CREATE VIRTUAL TABLE _trash_fts5_probe USING fts5(x)")
            cursor.execute("DROP TABLE _trash_fts5_probe")
            return True
        except Exception as exc:
            logger.debug("垃圾桶 FTS5 自检失败: %s", exc)
            return False

    # ------------------------------------------------------------------
    # 表 / 索引
    # ------------------------------------------------------------------

    def _create_diaries_table(self, cursor) -> None:
        """创建垃圾桶日记表，date=原日记创建时间，updated_at=原日记最近编辑时间"""
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
        self._safe_add_column(cursor, "trash_diaries", "tokens", "TEXT")
        # 兼容旧库：补 updated_at 列（与 diaries 同步）
        self._safe_add_column(cursor, "trash_diaries", "updated_at", "TEXT")

        # 回填旧库：updated_at 默认等于 date
        cursor.execute(
            'UPDATE trash_diaries SET updated_at = date '
            'WHERE updated_at IS NULL OR updated_at = ""'
        )

    def _create_pending_ops_table(self, cursor) -> None:
        """2PC 跨库协调：pending_trash_ops（垃圾桶库侧）"""
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

    def _create_tags_table(self, cursor) -> None:
        """创建垃圾桶标签表"""
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
        self._safe_add_column(cursor, "trash_tags", "original_tag_id", "INTEGER")

    def _create_indexes(self, cursor) -> None:
        """常用查询索引"""
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_trash_deleted_at '
            'ON trash_diaries(deleted_at)'
        )
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_trash_content '
            'ON trash_diaries(content)'
        )
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_trash_original_id '
            'ON trash_diaries(original_id)'
        )

    @staticmethod
    def _safe_add_column(cursor, table: str, column: str, decl: str) -> None:
        """安全的 ALTER TABLE ADD COLUMN（列已存在时忽略）"""
        try:
            cursor.execute(f'ALTER TABLE {table} ADD COLUMN {column} {decl}')
        except Exception:
            pass  # 列已存在

    # ------------------------------------------------------------------
    # FTS5（多语种）
    # ------------------------------------------------------------------

    def _create_fts5_artefacts(self, cursor) -> None:
        """建 FTS5 虚表、灌入历史数据、回填 tokens、建触发器"""
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
        cursor.execute(
            "SELECT id, content FROM trash_diaries "
            "WHERE tokens IS NULL OR tokens = ''"
        )
        rows = cursor.fetchall()
        if rows:
            from utils.text_tokenizer import tokenize
            for row in rows:
                tokens_str = ' '.join(tokenize(row['content'] or ''))
                cursor.execute(
                    "UPDATE trash_diaries SET tokens = ? WHERE id = ?",
                    (tokens_str, row['id'])
                )
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

    # ------------------------------------------------------------------
    # PRAGMA
    # ------------------------------------------------------------------

    @staticmethod
    def _apply_perf_pragmas(cursor) -> None:
        """启用 WAL 模式与常用性能参数"""
        cursor.execute('PRAGMA journal_mode=WAL')
        cursor.execute('PRAGMA synchronous=NORMAL')
        cursor.execute('PRAGMA cache_size=10000')
        cursor.execute('PRAGMA temp_store=memory')

    # ------------------------------------------------------------------
    # 预分词
    # ------------------------------------------------------------------

    def compute_tokens(self, content: Optional[str]) -> str:
        """对垃圾桶的日记内容算预分词串（FTS5 不可用时返回空）"""
        if not content or not self._fts5_available:
            return ''
        from utils.text_tokenizer import tokenize
        return ' '.join(tokenize(content))
