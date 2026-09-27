"""
垃圾桶搜索服务

负责在垃圾桶中按关键词搜索日记：
- FTS5 多语种 MATCH（优先）
- LIKE OR 兜底（FTS5 不可用 / MATCH 失败时）
"""
import logging
from typing import Any, Dict, List

from .connection import TrashConnectionPool
from .schema import TrashSchemaInitializer

logger = logging.getLogger(__name__)


class TrashSearchService:
    """垃圾桶搜索服务（FTS5 优先 + LIKE 兜底）

    注意：本服务假定 keyword 非空且非纯空白。
    关键词为空时由上层 Repository 直接走列表接口。
    """

    def __init__(
        self,
        connection_pool: TrashConnectionPool,
        schema: TrashSchemaInitializer,
    ):
        self._pool = connection_pool
        self._schema = schema

    def search(self, keyword: str, limit: int = 100) -> List[Dict[str, Any]]:
        """在垃圾桶中搜索日记

        Args:
            keyword: 搜索关键词（非空）
            limit: 限制数量

        Returns:
            匹配的垃圾桶日记列表
        """
        from utils.text_tokenizer import build_fts_match, like_or_pattern

        fts_keyword = keyword.strip()
        match_expr, _ = build_fts_match(fts_keyword)
        if not match_expr:
            return []

        if self._schema.fts5_available:
            fts_results = self._search_by_fts5(match_expr, limit)
            if fts_results:
                return fts_results
            logger.debug("垃圾桶 FTS5 MATCH 无结果，尝试 LIKE 兜底")

        return self._search_by_like(fts_keyword, limit)

    # ------------------------------------------------------------------
    # 内部：FTS5 / LIKE
    # ------------------------------------------------------------------

    def _search_by_fts5(self, match_expr: str, limit: int) -> List[Dict[str, Any]]:
        try:
            results = self._pool.execute(
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
                fetch='all',
            ) or []
            return results
        except Exception as exc:
            logger.warning("垃圾桶 FTS5 MATCH 失败，回退 LIKE: %s", exc)
            return []

    def _search_by_like(self, fts_keyword: str, limit: int) -> List[Dict[str, Any]]:
        from utils.text_tokenizer import like_or_pattern

        patterns = like_or_pattern(fts_keyword)
        if not patterns:
            return []
        conds = ' OR '.join('td.content LIKE ?' for _ in patterns)
        params = tuple(patterns) + (limit,)
        return self._pool.execute(
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
            fetch='all',
        ) or []
