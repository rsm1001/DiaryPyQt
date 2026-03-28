"""
查看次数服务模块 - 负责处理日记查看次数的相关功能
"""

from typing import Dict, Any, Optional, List
import sqlite3
import logging

logger = logging.getLogger(__name__)


class ViewCountService:
    """查看次数服务类，负责处理日记查看次数的相关功能"""
    
    def __init__(self, db_manager):
        """
        初始化查看次数服务
        
        Args:
            db_manager: 数据库管理器实例
        """
        self.db_manager = db_manager
    
    def increment_view_count(self, diary_id: int) -> Optional[int]:
        """
        增加日记查看次数
        
        Args:
            diary_id: 日记ID
        
        Returns:
            新的查看次数或None
        """
        # 使用RETURNING子句获取更新后的值（SQLite 3.35.0+）
        try:
            result = self.db_manager._execute(
                "UPDATE diaries SET view_count = view_count + 1 WHERE id = ? RETURNING view_count",
                (diary_id,),
                fetch='one'
            )
            if result:
                logger.debug(f"增加查看次数，ID: {diary_id}, 新次数: {result['view_count']}")
                return result['view_count']
        except sqlite3.Error:
            # 如果RETURNING不支持，使用传统方式
            self.db_manager._execute(
                "UPDATE diaries SET view_count = view_count + 1 WHERE id = ?",
                (diary_id,)
            )
            result = self.db_manager._execute(
                "SELECT view_count FROM diaries WHERE id = ?",
                (diary_id,),
                fetch='one'
            )
            return result['view_count'] if result else None
        return None
    
    def decrease_view_count(self, diary_id: int, penalty: int = 1) -> bool:
        """
        减少日记查看次数
        
        Args:
            diary_id: 日记ID
            penalty: 减少的数量
        
        Returns:
            是否操作成功
        """
        rowcount = self.db_manager._execute(
            "UPDATE diaries SET view_count = MAX(0, view_count - ?) WHERE id = ?",
            (penalty, diary_id),
            fetch='rowcount'
        )
        
        if rowcount > 0:
            logger.info(f"减少查看次数，ID: {diary_id}, 减少: {penalty}")
            return True
        return False
    
    def reset_view_count(self, diary_id: int) -> bool:
        """
        重置日记查看次数为0
        
        Args:
            diary_id: 日记ID
        
        Returns:
            是否重置成功
        """
        rowcount = self.db_manager._execute(
            "UPDATE diaries SET view_count = 0 WHERE id = ?",
            (diary_id,),
            fetch='rowcount'
        )
        
        if rowcount > 0:
            logger.info(f"重置查看次数，ID: {diary_id}")
            return True
        return False
    
    def batch_increment_view_counts(self, diary_ids: List[int]) -> int:
        """
        批量增加多篇日记的查看次数
        
        Args:
            diary_ids: 日记ID列表
        
        Returns:
            成功更新的记录数
        """
        if not diary_ids:
            return 0
            
        placeholders = ','.join(['?' for _ in diary_ids])
        query = f"UPDATE diaries SET view_count = view_count + 1 WHERE id IN ({placeholders})"
        
        rowcount = self.db_manager._execute(
            query,
            tuple(diary_ids),
            fetch='rowcount'
        )
        
        logger.info(f"批量增加查看次数，影响记录数: {rowcount}")
        return rowcount
    
    def get_total_view_count(self) -> int:
        """
        获取所有日记的总查看次数
        
        Returns:
            总查看次数
        """
        result = self.db_manager._execute(
            "SELECT SUM(view_count) as total_views FROM diaries",
            fetch='one'
        )
        
        return result['total_views'] if result and result['total_views'] else 0
    
    def get_highest_view_count(self) -> Optional[Dict[str, Any]]:
        """
        获取查看次数最高的日记
        
        Returns:
            查看次数最高的日记或None
        """
        return self.db_manager._execute(
            "SELECT * FROM diaries ORDER BY view_count DESC LIMIT 1",
            fetch='one'
        )
    
    def get_lowest_view_count(self) -> Optional[Dict[str, Any]]:
        """
        获取查看次数最低的日记
        
        Returns:
            查看次数最低的日记或None
        """
        return self.db_manager._execute(
            "SELECT * FROM diaries ORDER BY view_count ASC LIMIT 1",
            fetch='one'
        )
    
    def get_average_view_count(self) -> float:
        """
        获取平均查看次数
        
        Returns:
            平均查看次数
        """
        result = self.db_manager._execute(
            "SELECT AVG(view_count) as avg_views FROM diaries",
            fetch='one'
        )
        
        return result['avg_views'] if result and result['avg_views'] else 0.0
    
    def get_diaries_by_view_range(self, min_views: int, max_views: int) -> List[Dict[str, Any]]:
        """
        获取指定查看次数范围内的日记
        
        Args:
            min_views: 最小查看次数
            max_views: 最大查看次数
        
        Returns:
            符合条件的日记列表
        """
        return self.db_manager._execute(
            "SELECT * FROM diaries WHERE view_count >= ? AND view_count <= ? ORDER BY view_count DESC",
            (min_views, max_views),
            fetch='all'
        ) or []