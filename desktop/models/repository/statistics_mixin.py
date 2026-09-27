"""
统计功能模块 - 从DatabaseManager中解耦出来的统计功能
"""
import logging
from typing import List, Dict, Optional, Any
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class StatisticsMixin:
    """统计混入类，提供数据统计功能"""
    
    @abstractmethod
    def _execute(self, query: str, params: tuple = (), fetch: Optional[str] = None) -> Optional[Any]:
        """执行SQL查询的抽象方法"""
        pass
    
    @abstractmethod
    def get_all_diaries(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """获取所有日记的抽象方法"""
        pass
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取统计信息
        
        Returns:
            统计信息字典
        """
        # 基础统计
        stats = self._execute(
            """
            SELECT 
                COUNT(*) as total,
                COALESCE(SUM(view_count), 0) as total_views,
                COALESCE(AVG(view_count), 0) as avg_views,
                MAX(view_count) as max_views,
                MIN(view_count) as min_views
            FROM diaries
            """,
            fetch='one'
        )
        
        if not stats or stats['total'] == 0:
            return {
                'total': 0,
                'total_views': 0,
                'total_views': 0,
                'avg_views': 0,
                'most_viewed': None,
                'least_viewed': None
            }
        
        # 获取查看次数最多和最少的日记
        most_viewed = self._execute(
            "SELECT * FROM diaries WHERE view_count = ? ORDER BY date ASC LIMIT 1",
            (stats['max_views'],),
            fetch='one'
        )
        
        least_viewed = self._execute(
            "SELECT * FROM diaries WHERE view_count = ? ORDER BY date ASC LIMIT 1",
            (stats['min_views'],),
            fetch='one'
        )
        
        return {
            'total': stats['total'],
            'total_views': stats['total_views'],
            'avg_views': round(stats['avg_views'], 2),
            'most_viewed': most_viewed,
            'least_viewed': least_viewed
        }
    
    def get_basic_statistics(self) -> Dict[str, int]:
        """
        获取基础统计数据
        
        Returns:
            基础统计数据字典
        """
        stats = self._execute(
            """
            SELECT 
                COUNT(*) as total,
                COALESCE(SUM(view_count), 0) as total_views,
                COALESCE(AVG(view_count), 0) as avg_views,
                MAX(view_count) as max_views,
                MIN(view_count) as min_views
            FROM diaries
            """,
            fetch='one'
        )
        
        if not stats:
            return {
                'total': 0,
                'total_views': 0,
                'avg_views': 0,
                'max_views': 0,
                'min_views': 0
            }
        
        return {
            'total': stats['total'],
            'total_views': int(stats['total_views']),
            'avg_views': round(stats['avg_views']),
            'max_views': stats['max_views'] or 0,
            'min_views': stats['min_views'] or 0
        }