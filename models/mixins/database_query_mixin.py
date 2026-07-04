"""
数据库查询模块 - 将EnhancedDatabaseManager中的查询功能独立出来
"""

import logging
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)

class DatabaseQueryMixin:
    """数据库查询混入类，提供各种高级查询功能"""
    
    def get_all_diaries(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        获取所有日记（按日期倒序）
        
        Args:
            limit: 限制数量
        
        Returns:
            日记列表
        """
        # 此方法在EnhancedDatabaseManager中已有实现，此处仅为保持方法结构
        # 实际实现由EnhancedDatabaseManager提供
        pass
    
    def get_most_viewed_diaries(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        获取查看次数最多的日记

        Args:
            limit: 限制数量

        Returns:
            日记列表
        """
        return self._execute(
            "SELECT * FROM diaries ORDER BY view_count DESC, date ASC LIMIT ?",
            (limit,),
            fetch='all'
        ) or []

    def get_least_viewed_diaries(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        获取查看次数最少的日记

        Args:
            limit: 限制数量

        Returns:
            日记列表
        """
        return self._execute(
            "SELECT * FROM diaries ORDER BY view_count ASC, date DESC LIMIT ?",
            (limit,),
            fetch='all'
        ) or []

    def get_oldest_in_most_viewed(self, limit: int = 20) -> Optional[Dict[str, Any]]:
        """
        获取查看次数最多的日记中最久远的

        Args:
            limit: 查看次数最多的前N篇

        Returns:
            日记字典或None
        """
        return self._execute(
            """
            SELECT * FROM diaries 
            WHERE id IN (
                SELECT id FROM diaries 
                ORDER BY view_count DESC, date ASC 
                LIMIT ?
            )
            ORDER BY date ASC 
            LIMIT 1
            """,
            (limit,),
            fetch='one'
        )

    def get_random_diary(self, limit: int = None, tag_ids: List[int] = None) -> Optional[Dict[str, Any]]:
        """
        随机获取一篇日记（基于权重概率选择，使用次数越少，被选中概率越大）
        使用改进的归一化方法，对全部日记进行计算（除非指定limit）

        Args:
            limit: 最多考虑的日记数量，None表示使用全部日记
            tag_ids: 标签ID列表，非空时仅从匹配这些标签的日记中选取

        Returns:
            日记字典或None
        """
        from ..weight.diary_selection_service import DiarySelectionService

        # 使用日记选择服务获取加权随机日记
        service = DiarySelectionService()

        # 根据是否有标签筛选选择数据源
        if tag_ids:
            # 多对多任意匹配：日记拥有任一所选标签即进入候选池
            placeholders = ','.join('?' * len(tag_ids))
            query = f"""
                SELECT DISTINCT d.* FROM diaries d
                INNER JOIN diary_tags dt ON d.id = dt.diary_id
                WHERE dt.tag_id IN ({placeholders})
                ORDER BY d.date DESC
                """
            params = tuple(tag_ids)
            candidate_rows = self._execute(query, params, fetch='all') or []
            if limit is not None and len(candidate_rows) > limit:
                # 按日期倒序后取前limit条（与原逻辑一致：取最新的）
                candidate_rows = candidate_rows[:limit]
            diaries = [dict(row) for row in candidate_rows]
        else:
            diaries = self.get_all_diaries() if limit is None else self.get_diaries_with_limit(limit)
            diaries = [dict(d) for d in diaries]

        if not diaries:
            return None

        return service.get_weighted_random_diary(diaries)

    def get_diary_for_deletion(self, limit: int = None) -> Optional[Dict[str, Any]]:
        """
        获取一篇适合删除的日记（时间久远且查看次数多，被选中概率越大）
        使用与随机查看相反的权重策略

        Args:
            limit: 最多考虑的日记数量，None表示使用全部日记

        Returns:
            日记字典或None
        """
        from ..weight.diary_selection_service import DiarySelectionService
        
        # 使用日记选择服务获取加权删除日记
        service = DiarySelectionService()
        diaries = self.get_all_diaries() if limit is None else self.get_diaries_with_limit(limit)
        
        if not diaries:
            return None

        # 将SQL查询结果转换为字典格式的日记对象
        diary_dicts = [dict(diary) for diary in diaries]
        return service.get_weighted_deletion_diary(diary_dicts)

    def search_by_keyword(self, keyword: str, limit: int = 18) -> List[Dict[str, Any]]:
        """
        根据关键词搜索日记（多语种分词 + FTS5 + LIKE 兜底）

        - 自动按脚本分词：CJK / 日 / 韩按字符 unigram；拉丁按词
        - 拼 FTS5 MATCH 表达式，跨脚本 AND / 段内短语
        - FTS5 无结果或抛错时回退到 LIKE OR（应用层拼多 token）
        - FTS5 在当前 SQLite 构建未启用时直接走 LIKE

        Args:
            keyword: 搜索关键词
            limit: 限制数量

        Returns:
            日记列表
        """
        if not keyword or not keyword.strip():
            return []

        from utils.text_tokenizer import build_fts_match, like_or_pattern

        fts_keyword = keyword.strip()
        match_expr, tokens = build_fts_match(fts_keyword)
        if not match_expr:
            return []

        # FTS5 不可用时直接走 LIKE
        if not getattr(self, '_fts5_available', True):
            return self._like_or_fallback(fts_keyword, tokens, limit)

        # 优先 FTS5
        try:
            results = self._execute(
                """
                SELECT d.* FROM diaries d
                INNER JOIN diaries_fts fts ON d.id = fts.rowid
                WHERE diaries_fts MATCH ?
                ORDER BY d.view_count DESC, d.date DESC
                LIMIT ?
                """,
                (match_expr, limit),
                fetch='all'
            ) or []
        except Exception as exc:
            logger.warning("FTS5 MATCH 失败，回退 LIKE: %s", exc)
            results = []

        # FTS5 无结果时 LIKE 兜底
        if not results:
            results = self._like_or_fallback(fts_keyword, tokens, limit)
        return results

    def _like_or_fallback(self, raw_keyword: str, tokens, limit: int) -> List[Dict[str, Any]]:
        """LIKE OR 兜底：每 token 一条 LIKE，多 token 用 OR 串联"""
        from utils.text_tokenizer import like_or_pattern

        patterns = like_or_pattern(raw_keyword)
        if not patterns:
            return []
        conds = ' OR '.join('LOWER(content) LIKE LOWER(?)' for _ in patterns)
        query = (
            f"SELECT * FROM diaries WHERE {conds} "
            f"ORDER BY view_count DESC, date DESC LIMIT ?"
        )
        params = tuple(patterns) + (limit,)
        return self._execute(query, params, fetch='all') or []

    def get_tags_for_diaries(self, diary_ids: List[int]) -> Dict[int, List[Dict[str, Any]]]:
        """
        批量获取多篇日记的标签（避免 N+1 查询）

        Args:
            diary_ids: 日记ID列表

        Returns:
            dict，key 为 diary_id，value 为该日记的标签列表
        """
        if not diary_ids:
            return {}

        placeholders = ','.join('?' * len(diary_ids))
        rows = self._execute(
            f"""
            SELECT t.*, dt.diary_id
            FROM tags t
            INNER JOIN diary_tags dt ON t.id = dt.tag_id
            WHERE dt.diary_id IN ({placeholders})
            ORDER BY dt.diary_id, t.name ASC
            """,
            diary_ids,
            fetch='all'
        ) or []

        result: Dict[int, List[Dict[str, Any]]] = {did: [] for did in diary_ids}
        for row in rows:
            did = row['diary_id']
            tag = {k: v for k, v in row.items() if k != 'diary_id'}
            result[did].append(tag)

        return result