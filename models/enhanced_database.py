"""
增强版数据库管理器 - 核心入口
包含迁移功能，负责初始化各服务模块
"""
import os
import sqlite3
import threading
import logging
from typing import List, Dict, Optional, Any

from .mixins._connection_mixin import ConnectionMixin
from .mixins.tag_management_mixin import TagManagementMixin
from .mixins.database_query_mixin import DatabaseQueryMixin
from .repository.diary_operations import DiaryOperationsMixin
from .repository.trash_mixin import TrashMixin
from .migration_backup_manager import MigrationBackupManager

logger = logging.getLogger(__name__)

# 延迟导入服务模块（避免循环依赖）
def _import_services_lazily():
    """延迟导入服务模块"""
    from services.statistics_service import StatisticsService
    from services.view_count_service import ViewCountService
    from services.content_service import DiaryContentService
    return StatisticsService, ViewCountService, DiaryContentService


class EnhancedDatabaseManager(
    ConnectionMixin,
    TagManagementMixin,
    DatabaseQueryMixin,
    DiaryOperationsMixin,
    TrashMixin
):
    """
    增强版SQLite数据库管理器

    继承自 ConnectionMixin，获取核心连接/事务/SQL执行能力；
    其余功能由各 Mixin 和 Service 提供。
    """

    # -------------------------------------------------------------------------
    # 属性实现（ConnectionMixin 要求）
    # -------------------------------------------------------------------------

    @property
    def db_path(self) -> str:
        return self._db_path

    @property
    def _lock(self) -> threading.RLock:
        return self._db_lock

    # -------------------------------------------------------------------------
    # 初始化
    # -------------------------------------------------------------------------

    def __init__(self, db_path: str = None):
        """
        初始化数据库管理器

        Args:
            db_path: 数据库文件路径
        """
        # 解析数据库路径
        if db_path is None:
            project_root = os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))
            )
            db_path = os.path.join(project_root, "data", "diary.db")

        self._db_path = db_path
        self._db_lock = threading.RLock()

        # 初始化读写分离连接池
        self._init_pool()

        # 服务占位（延迟初始化）
        self._services_initialized = False
        self._migration_backup_manager = None
        self._statistics_service = None
        self._view_count_service = None
        self._diary_content_service = None

        # 确保目录存在
        self._ensure_directory()

        # 初始化数据库
        self._init_database()

        # 初始化垃圾桶数据库
        self._init_trash_database()

        logger.info(f"EnhancedDatabaseManager 初始化完成，数据库路径: {os.path.abspath(self.db_path)}")

    def _ensure_directory(self):
        """确保数据库目录存在"""
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

    def _init_services(self):
        """初始化各服务实例"""
        if self._services_initialized:
            return
        StatisticsService, ViewCountService, DiaryContentService = _import_services_lazily()

        self._migration_backup_manager = MigrationBackupManager(self)
        self._statistics_service = StatisticsService(self)
        self._view_count_service = ViewCountService(self)
        self._diary_content_service = DiaryContentService(self)
        self._services_initialized = True

    def __getattr__(self, name):
        """延迟初始化服务属性"""
        if name == 'migration_backup_manager':
            self._init_services()
            return self._migration_backup_manager
        if name == 'statistics_service':
            self._init_services()
            return self._statistics_service
        if name == 'view_count_service':
            self._init_services()
            return self._view_count_service
        if name == 'diary_content_service':
            self._init_services()
            return self._diary_content_service
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

    # -------------------------------------------------------------------------
    # 数据库Schema初始化
    # -------------------------------------------------------------------------

    def _init_database(self):
        """初始化数据库表、索引和性能配置"""
        # 确保连接池已初始化（restore_database 等场景可能已关闭连接池）
        if self._write_conn is None:
            self._init_pool()

        conn = self._get_write_connection()
        cursor = conn.cursor()

        # 自检 FTS5 是否可用（Python 3.8 内置 sqlite3 多数发行版已含；缺则降级 LIKE-only）
        self._fts5_available = self._probe_fts5(cursor)
        if not self._fts5_available:
            logger.warning("当前 SQLite 构建未启用 FTS5，搜索将自动降级为 LIKE 模式")

        # ---- 日记主表 ----
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS diaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                content TEXT NOT NULL,
                view_count INTEGER DEFAULT 0,
                last_viewed_at TEXT,
                tokens TEXT
            )
        ''')

        # 为已有表添加 last_viewed_at 列（兼容旧数据库）
        try:
            cursor.execute('ALTER TABLE diaries ADD COLUMN last_viewed_at TEXT')
        except Exception:
            pass  # 列已存在

        # 为已有表添加 tokens 列（兼容旧数据库；多语种分词的预分词结果）
        try:
            cursor.execute('ALTER TABLE diaries ADD COLUMN tokens TEXT')
        except Exception:
            pass  # 列已存在

        # ---- 标签表 ----
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # ---- 日记-标签关联表 ----
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS diary_tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                diary_id INTEGER NOT NULL,
                tag_id INTEGER NOT NULL,
                FOREIGN KEY (diary_id) REFERENCES diaries(id) ON DELETE CASCADE,
                FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE,
                UNIQUE(diary_id, tag_id)
            )
        ''')

        # ---- 每日统计表 ----
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stat_date TEXT NOT NULL UNIQUE,
                yesterday_total_views INTEGER DEFAULT 0,
                all_time_max_single_views INTEGER DEFAULT 0,
                all_time_max_diary_id INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # ---- 查看日志表 ----
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS view_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                diary_id INTEGER NOT NULL,
                viewed_at TEXT NOT NULL,
                FOREIGN KEY (diary_id) REFERENCES diaries(id) ON DELETE CASCADE
            )
        ''')

        # ---- 应用配置表 ----
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS app_config (
                key TEXT PRIMARY KEY,
                value INTEGER DEFAULT 0,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 初始化历史最佳值为 0
        cursor.execute(
            'INSERT OR IGNORE INTO app_config (key, value) VALUES (?, 0)',
            ('all_time_max_daily_views',)
        )

        # ---- 索引 ----
        cursor.execute('DROP INDEX IF EXISTS idx_diaries_date')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_diaries_date ON diaries(date)')
        cursor.execute('DROP INDEX IF EXISTS idx_diaries_view_count')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_diaries_view_count ON diaries(view_count)')
        cursor.execute('DROP INDEX IF EXISTS idx_diaries_content')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_diaries_content ON diaries(content)')
        cursor.execute('DROP INDEX IF EXISTS idx_diaries_content_lower')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_diaries_content_lower ON diaries(LOWER(content))')
        cursor.execute('DROP INDEX IF EXISTS idx_diary_tags_diary_id')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_diary_tags_diary_id ON diary_tags(diary_id)')
        cursor.execute('DROP INDEX IF EXISTS idx_diary_tags_tag_id')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_diary_tags_tag_id ON diary_tags(tag_id)')
        cursor.execute('DROP INDEX IF EXISTS idx_view_log_viewed_at')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_view_log_viewed_at ON view_log(viewed_at)')
        cursor.execute('DROP INDEX IF EXISTS idx_view_log_diary_id')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_view_log_diary_id ON view_log(diary_id)')

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

        # ---- 性能优化PRAGMA ----
        cursor.execute('PRAGMA journal_mode=WAL')
        cursor.execute('PRAGMA synchronous=NORMAL')
        cursor.execute('PRAGMA cache_size=10000')
        cursor.execute('PRAGMA temp_store=memory')
        cursor.execute('PRAGMA mmap_size=30000000000')

        conn.commit()
        logger.info("数据库初始化完成")

    # -------------------------------------------------------------------------
    # FTS5 多语种搜索支持
    # -------------------------------------------------------------------------

    def _probe_fts5(self, cursor) -> bool:
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

    def _migrate_fts5_schema(self, cursor) -> None:
        """
        若 FTS5 仍是单列（content）布局，删掉重建为 3 列（content, tokens）。

        SQLite 不支持 ALTER VIRTUAL TABLE，因此直接 DROP 后依赖后续 CREATE
        （CREATE VIRTUAL TABLE IF NOT EXISTS 已经走过，这里走老路径清理）。
        """
        if not self._fts5_available:
            return
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
        for trig in ("diaries_fts_insert", "diaries_fts_update", "diaries_fts_delete"):
            cursor.execute(f"DROP TRIGGER IF EXISTS {trig}")
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

    def _backfill_tokens(self, cursor) -> None:
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

    def compute_tokens(self, content: str) -> str:
        """
        对外暴露：把内容算成 tokens 空格串（写库前用）。

        - 无 FTS5 时返回空串（旧 LIKE 行为）
        """
        if not content:
            return ''
        if not getattr(self, '_fts5_available', True):
            return ''
        from utils.text_tokenizer import tokenize
        return ' '.join(tokenize(content))

    # -------------------------------------------------------------------------
    # 公开API（代理到各服务）
    # -------------------------------------------------------------------------

    def get_all_diaries(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """获取所有日记（按日期倒序），带标签信息"""
        return self.diary_content_service.get_all_diaries_with_tags(limit)

    def get_diaries_by_date(self, date_str: str) -> List[Dict[str, Any]]:
        """根据日期获取日记（LIKE 查询）

        Args:
            date_str: 日期字符串，格式如 '2026-05-20'

        Returns:
            该日期的所有日记
        """
        return self.diary_content_service.get_diaries_by_date(date_str)

    def get_diaries_with_limit(self, limit: int) -> List[Dict[str, Any]]:
        """获取指定数量的日记（按日期倒序）"""
        return self.diary_content_service.get_diaries_with_limit(limit)

    # ---- 查看次数 ----

    def increment_view_count(self, diary_id: int) -> Optional[int]:
        """增加日记查看次数"""
        return self.view_count_service.increment_view_count(diary_id)

    def decrease_view_count(self, diary_id: int, penalty: int = 1) -> bool:
        """减少日记查看次数"""
        return self.view_count_service.decrease_view_count(diary_id, penalty)

    # ---- 统计 ----

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return self.statistics_service.get_statistics()

    def get_daily_stats(self) -> Dict[str, Any]:
        """获取每日统计信息"""
        return self.statistics_service.get_daily_stats()

    # ---- 迁移/备份 ----

    def migrate_from_json(self, json_file_path: str) -> int:
        """从JSON文件迁移数据"""
        return self.migration_backup_manager.migrate_from_json(json_file_path)

    def migrate_from_csv(self, csv_file_path: str) -> int:
        """从CSV文件迁移数据"""
        return self.migration_backup_manager.migrate_from_csv(csv_file_path)

    def export_to_json(self, json_file_path: str) -> bool:
        """导出数据到JSON文件"""
        return self.migration_backup_manager.export_to_json(json_file_path)

    def export_to_csv(self, csv_file_path: str) -> bool:
        """导出数据到CSV文件"""
        return self.migration_backup_manager.export_to_csv(csv_file_path)

    def backup_database(self, backup_path: str) -> bool:
        """备份整个数据库"""
        return self.migration_backup_manager.backup_database(backup_path)

    def restore_database(self, backup_path: str) -> bool:
        """从备份恢复数据库"""
        return self.migration_backup_manager.restore_database(backup_path)

    def validate_database_integrity(self) -> bool:
        """验证数据库完整性"""
        return self.migration_backup_manager.validate_database_integrity()

    # -------------------------------------------------------------------------
    # 生命周期
    # -------------------------------------------------------------------------

    def close(self):
        """关闭数据库连接池"""
        self._close_pool()
        self._close_trash_pool()
        logger.info("数据库连接池已关闭")


# =============================================================================
# 实例池模式（按路径缓存）
# =============================================================================

_enhanced_db_managers: Dict[str, EnhancedDatabaseManager] = {}


def get_enhanced_db_manager(db_path: str = None) -> EnhancedDatabaseManager:
    """获取增强版数据库管理器（按路径缓存实例）"""
    global _enhanced_db_managers

    if db_path is None:
        from config.config import get_db_path
        db_path = get_db_path()

    if db_path not in _enhanced_db_managers:
        _enhanced_db_managers[db_path] = EnhancedDatabaseManager(db_path)

    return _enhanced_db_managers[db_path]


def reset_enhanced_db_manager(db_path: str = None):
    """重置指定路径的实例（下次调用会重新创建）"""
    global _enhanced_db_managers

    if db_path is None:
        from config.config import get_db_path
        db_path = get_db_path()

    if db_path in _enhanced_db_managers:
        _enhanced_db_managers[db_path].close()
        del _enhanced_db_managers[db_path]
