"""
统计服务模块 - 负责处理日记系统的各种统计功能
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import sqlite3
import logging

logger = logging.getLogger(__name__)


class StatisticsService:
    """统计服务类，负责处理日记系统的各种统计功能"""
    
    def __init__(self, db_manager):
        """
        初始化统计服务
        
        Args:
            db_manager: 数据库管理器实例
        """
        self.db_manager = db_manager
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取统计信息
        
        Returns:
            统计信息字典
        """
        # 基础统计
        stats = self.db_manager._execute(
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
                'avg_views': 0,
                'most_viewed': None,
                'least_viewed': None
            }
        
        # 获取查看次数最多和最少的日记
        most_viewed = self.db_manager._execute(
            "SELECT * FROM diaries WHERE view_count = ? ORDER BY date ASC LIMIT 1",
            (stats['max_views'],),
            fetch='one'
        )
        
        least_viewed = self.db_manager._execute(
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
    
    def get_view_statistics(self) -> Dict[str, Any]:
        """
        获取详细的查看次数统计
        
        Returns:
            查看次数统计信息
        """
        # 获取查看次数分布
        view_distribution = self.db_manager._execute(
            """
            SELECT 
                CASE 
                    WHEN view_count = 0 THEN '未查看'
                    WHEN view_count BETWEEN 1 AND 5 THEN '1-5次'
                    WHEN view_count BETWEEN 6 AND 10 THEN '6-10次'
                    WHEN view_count BETWEEN 11 AND 20 THEN '11-20次'
                    WHEN view_count > 20 THEN '20次以上'
                END as view_range,
                COUNT(*) as count
            FROM diaries
            GROUP BY view_range
            ORDER BY 
                CASE view_range
                    WHEN '未查看' THEN 1
                    WHEN '1-5次' THEN 2
                    WHEN '6-10次' THEN 3
                    WHEN '11-20次' THEN 4
                    WHEN '20次以上' THEN 5
                END
            """,
            fetch='all'
        )
        
        # 获取总查看次数和平均查看次数
        summary_stats = self.db_manager._execute(
            """
            SELECT 
                SUM(view_count) as total_views,
                AVG(view_count) as avg_views,
                MAX(view_count) as max_views,
                MIN(view_count) as min_views
            FROM diaries
            """,
            fetch='one'
        )
        
        return {
            'summary': summary_stats,
            'distribution': view_distribution
        }
    
    def get_content_length_statistics(self) -> Dict[str, Any]:
        """
        获取内容长度统计
        
        Returns:
            内容长度统计信息
        """
        length_stats = self.db_manager._execute(
            """
            SELECT 
                AVG(LENGTH(content)) as avg_length,
                MIN(LENGTH(content)) as min_length,
                MAX(LENGTH(content)) as max_length,
                COUNT(*) as total_count
            FROM diaries
            """,
            fetch='one'
        )
        
        return {
            'average_length': int(length_stats['avg_length']) if length_stats['avg_length'] else 0,
            'min_length': length_stats['min_length'] or 0,
            'max_length': length_stats['max_length'] or 0,
            'total_count': length_stats['total_count']
        }
    
    def get_daily_activity_statistics(self) -> List[Dict[str, Any]]:
        """
        获取每日活动统计
        
        Returns:
            每日活动统计数据列表
        """
        daily_stats = self.db_manager._execute(
            """
            SELECT 
                date(d.date) as day,
                COUNT(*) as diary_count,
                SUM(view_count) as total_views
            FROM diaries d
            GROUP BY date(d.date)
            ORDER BY day DESC
            LIMIT 30  -- 最近30天的数据
            """,
            fetch='all'
        )
        
        return daily_stats or []
    
    def get_top_viewed_diaries(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取查看次数最多的日记
        
        Args:
            limit: 返回数量限制
        
        Returns:
            排名前列的日记列表
        """
        top_diaries = self.db_manager._execute(
            """
            SELECT * 
            FROM diaries 
            WHERE view_count > 0
            ORDER BY view_count DESC, date DESC
            LIMIT ?
            """,
            (limit,),
            fetch='all'
        )
        
        return top_diaries or []
    
    def get_least_viewed_diaries(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取查看次数最少的日记
        
        Args:
            limit: 返回数量限制
        
        Returns:
            查看次数最少的日记列表
        """
        least_diaries = self.db_manager._execute(
            """
            SELECT * 
            FROM diaries 
            ORDER BY view_count ASC, date DESC
            LIMIT ?
            """,
            (limit,),
            fetch='all'
        )
        
        return least_diaries or []
    
    def get_daily_stats(self) -> Dict[str, Any]:
        """
        获取每日统计信息（昨日查看总数 + 历史最佳单日查看数）
        
        Returns:
            每日统计信息字典
        """
        today = datetime.now().strftime('%Y-%m-%d')
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        # 1. 计算昨日查看总数 - 查询 view_log 表获取昨天实际的查看次数
        yesterday_result = self.db_manager._execute(
            """
            SELECT COUNT(*) as total_views
            FROM view_log
            WHERE date(viewed_at) = ?
            """,
            (yesterday,),
            fetch='one'
        )
        yesterday_total = yesterday_result['total_views'] if yesterday_result else 0
        
        # 2. 获取历史最佳单日查看数 - 从 app_config 表读取
        max_result = self.db_manager._execute(
            "SELECT value, updated_at FROM app_config WHERE key = 'all_time_max_daily_views'",
            fetch='one'
        )
        all_time_max_daily_views = max_result['value'] if max_result else 0
        
        # 3. 更新 daily_stats 表（用于兼容其他可能依赖此表的逻辑）
        self.db_manager._execute(
            """
            INSERT OR REPLACE INTO daily_stats (stat_date, yesterday_total_views, all_time_max_single_views, all_time_max_diary_id)
            VALUES (?, ?, ?, ?)
            """,
            (today, yesterday_total, all_time_max_daily_views, None)
        )
        
        logger.info(f"生成每日统计: 日期={today}, 昨日查看={yesterday_total}, 历史最佳单日={all_time_max_daily_views}")
        
        return {
            'yesterday_total_views': yesterday_total,
            'all_time_max_single_views': all_time_max_daily_views,
            'all_time_max_date': max_result['updated_at'] if max_result else None
        }
    
    def get_today_total_views(self) -> int:
        """
        获取今日查看次数（实时查询，统计今天所有查看动作数）
        
        Returns:
            今日查看次数
        """
        today = datetime.now().strftime('%Y-%m-%d')
        result = self.db_manager._execute(
            """
            SELECT COUNT(*) as total_views
            FROM view_log
            WHERE date(viewed_at) = ?
            """,
            (today,),
            fetch='one'
        )
        return result['total_views'] if result else 0