"""
FTS5全文搜索Schema初始化器 - 负责diaries_fts虚拟表及触发器
"""
import logging
import sqlite3

logger = logging.getLogger(__name__)


class FTS5SchemaInitializer:
    """FTS5全文搜索Schema初始化器"""

    def __init__(self, conn: 'sqlite3.Connection'):
        self._conn = conn

    def probe_fts5(self, cursor: 'sqlite3.Cursor') -> bool:
        """
        自检当前 SQLite 构建是否启用 FTS5。

        通过 ``CREATE VIRTUAL TABLE t USING fts5(x)`` 试探；失败则降级 LIKE-only。
        """
        try:
            cursor.execute("CREATE VIRTUAL TABLE _fts5_probe USING fts5(x)")
            cursor.execute("DROP TABLE _fts5_probe")
            return True
        except Exception as exc:  # FTS5 未编译进 sqlite3 时抛 OperationalError
            logger.debug("FTS5 自检失败: %s", exc)
            return False

    def initialize(self, cursor: 'sqlite3.Cursor', fts5_available: bool) -> None:
        """
        初始化FTS5虚拟表及触发器

        Args:
            cursor: 数据库游标
            fts5_available: FTS5是否可用
        """
        if not fts5_available:
            logger.warning("FTS5不可用，跳过全文搜索表初始化")
            return

        # ---- FTS5 全文搜索表 ----
        # 3 列：原 content（兼容 unicode61 短语）+ 预分词 tokens（覆盖 CJK / 日韩 / 扩展汉字）
        # 应用层在写库前算好 tokens 串，写入 diaries.tokens；触发器镜像到 FTS5
        # 外层用 """ 以便内层 tokenize 字符串可写 '' 转义形式
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS diaries_fts USING fts5(
                content,
                tokens,
                content='diaries',
                content_rowid='id',
                tokenize='unicode61 remove_diacritics 2 categories ''L* N* Co'''
            )
        """)

        # 旧库迁移：若 FTS5 仍是单列（content）布局，删掉重建为 3 列
        self._migrate_fts5_schema(cursor)

        # 初始化 FTS 表（将已有数据灌入，使用 REPLACE 确保已存在的行也被更新）
        cursor.execute(
            "INSERT OR REPLACE INTO diaries_fts(rowid, content, tokens) "
            "SELECT id, content, COALESCE(tokens, '') FROM diaries"
        )

        # 回填缺失的 tokens（兼容旧库：tokens 列为 NULL 的日记）
        self._backfill_tokens(cursor)

        # ---- FTS5 同步触发器 ----
        self._create_triggers(cursor)

        logger.info("FTS5表Schema初始化完成")

    def _migrate_fts5_schema(self, cursor: 'sqlite3.Cursor') -> None:
        """
        若 FTS5 仍是单列（content）布局，删掉重建为 3 列（content, tokens）。

        SQLite 不支持 ALTER VIRTUAL TABLE，因此直接 DROP 后依赖后续 CREATE
        （CREATE VIRTUAL TABLE IF NOT EXISTS 已经走过，这里走老路径清理）。
        """
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='diaries_fts'")
            row = cursor.fetchone()
            if not row:
                return
            # 用 PRAGMA table_info 拿列数（contentless 表仍支持）
            cursor.execute("PRAGMA table_info(diaries_fts)")
            cols = cursor.fetchall()
            # contentless FTS5 表 PRAGMA 拿不到列；用另一种方式：直接尝试三列 INSERT
            cursor.execute("SELECT 1 FROM diaries_fts LIMIT 0")
        except Exception:
            return

        # 探查是否已经支持 tokens 列：尝试一次三列写
        try:
            cursor.execute(
                "INSERT INTO diaries_fts(rowid, content, tokens) VALUES (-1, '', '')"
            )
            cursor.execute("INSERT INTO diaries_fts(diaries_fts, rowid, content, tokens) VALUES ('delete', -1, '', '')")
            return  # 三列已支持，无需迁移
        except Exception:
            pass  # 仍是旧 schema，需要重建

        logger.info("检测到旧版 FTS5 schema（单列），开始迁移到 3 列布局")
        # 删除旧 FTS5 表和旧触发器
        cursor.execute("DROP TABLE IF EXISTS diaries_fts")
        # 触发器名为固定白名单，避免动态拼接 SQL 标识符。
        for statement in (
            "DROP TRIGGER IF EXISTS diaries_fts_insert",
            "DROP TRIGGER IF EXISTS diaries_fts_update",
            "DROP TRIGGER IF EXISTS diaries_fts_delete",
        ):
            cursor.execute(statement)
        # 重新建（3 列）
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS diaries_fts USING fts5(
                content,
                tokens,
                content='diaries',
                content_rowid='id',
                tokenize='unicode61 remove_diacritics 2 categories ''L* N* Co'''
            )
        """)

    def _backfill_tokens(self, cursor: 'sqlite3.Cursor') -> None:
        """回填 diaries.tokens（NULL 或空串的行）"""
        from utils.text_tokenizer import tokenize
        try:
            cursor.execute("SELECT id, content FROM diaries WHERE tokens IS NULL OR tokens = ''")
        except Exception:
            return
        rows = cursor.fetchall()
        if not rows:
            return
        updated = 0
        for row in rows:
            diary_id = row['id'] if isinstance(row, sqlite3.Row) else row[0]
            content = row['content'] if isinstance(row, sqlite3.Row) else row[1]
            tokens_str = ' '.join(tokenize(content or ''))
            cursor.execute("UPDATE diaries SET tokens = ? WHERE id = ?", (tokens_str, diary_id))
            updated += 1
        if updated:
            logger.info("回填 tokens 完成，共 %d 条", updated)

    def _create_triggers(self, cursor: 'sqlite3.Cursor') -> None:
        """创建FTS5同步触发器"""
        # INSERT 触发器
        cursor.execute('''
            CREATE TRIGGER IF NOT EXISTS diaries_fts_insert AFTER INSERT ON diaries BEGIN
                INSERT INTO diaries_fts(rowid, content, tokens) VALUES (new.id, new.content, COALESCE(new.tokens, ''));
            END
        ''')

        # UPDATE 触发器
        cursor.execute('''
            CREATE TRIGGER IF NOT EXISTS diaries_fts_update AFTER UPDATE ON diaries BEGIN
                INSERT INTO diaries_fts(diaries_fts, rowid, content, tokens) VALUES ('delete', old.id, old.content, COALESCE(old.tokens, ''));
                INSERT INTO diaries_fts(rowid, content, tokens) VALUES (new.id, new.content, COALESCE(new.tokens, ''));
            END
        ''')

        # DELETE 触发器
        cursor.execute('''
            CREATE TRIGGER IF NOT EXISTS diaries_fts_delete AFTER DELETE ON diaries BEGIN
                INSERT INTO diaries_fts(diaries_fts, rowid, content, tokens) VALUES ('delete', old.id, old.content, COALESCE(old.tokens, ''));
            END
        ''')

    def compute_tokens(self, content: str, fts5_available: bool = True) -> str:
        """
        对外暴露：把内容算成 tokens 空格串（写库前用）。

        Args:
            content: 待分词内容
            fts5_available: FTS5是否可用

        Returns:
            tokens空格串（无FTS5时返回空串）
        """
        if not content:
            return ''
        if not fts5_available:
            return ''
        from utils.text_tokenizer import tokenize
        return ' '.join(tokenize(content))
