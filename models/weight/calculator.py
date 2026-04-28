"""
权重计算器模块
用于处理日记选择中的复杂权重计算逻辑
"""
import random
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple
# 修正导入路径
from models.enhanced_database import EnhancedDatabaseManager
from .calculation_service import WeightCalculationService
from .normalization_strategies import NormalizationStrategyFactory


class WeightCalculator:
    """
    权重计算器
    负责处理日记选择中的复杂权重算法
    现在作为WeightCalculationService的适配器，保持向后兼容性
    """
    
    def __init__(self):
        """
        初始化权重计算器，使用WeightCalculationService
        """
        self.service = WeightCalculationService()
    
    @staticmethod
    def calculate_selection_weights(
        diaries: List[Dict[str, Any]], 
        selection_type: str = 'random'
    ) -> List[Tuple[Dict[str, Any], float]]:
        """
        计算日记的权重
        
        Args:
            diaries: 日记列表
            selection_type: 选择类型 ('random'用于随机选择, 'deletion'用于删除选择)
        
        Returns:
            包含(日记, 权重)元组的列表
        """
        return WeightCalculationService.calculate_selection_weights(diaries, selection_type)
    
    @staticmethod
    def select_by_weight(weighted_diaries: List[Tuple[Dict[str, Any], float]]) -> Optional[Dict[str, Any]]:
        """
        根据权重选择日记
        
        Args:
            weighted_diaries: 包含(日记, 权重)元组的列表
        
        Returns:
            选中的日记
        """
        return WeightCalculationService.select_by_weight(weighted_diaries)
    
    @classmethod
    def get_weighted_random_diary(
        cls, 
        db_manager: EnhancedDatabaseManager, 
        limit: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        获取加权随机日记
        
        Args:
            db_manager: 数据库管理器实例
            limit: 最多考虑的日记数量
        
        Returns:
            选中的日记
        """
        # 获取日记数据
        if limit is None:
            # 获取全部日记，按日期升序排列
            diaries = db_manager._execute(
                "SELECT * FROM diaries ORDER BY date ASC",
                fetch='all'
            )
        else:
            # 仅获取指定数量的日记
            diaries = db_manager._execute(
                "SELECT * FROM diaries ORDER BY date ASC LIMIT ?",
                (limit,),
                fetch='all'
            )
        
        if not diaries:
            return None
        
        calculator = cls()
        return calculator.service.get_weighted_random_diary_from_data(diaries)
    
    @classmethod
    def get_weighted_deletion_diary(
        cls, 
        db_manager: EnhancedDatabaseManager, 
        limit: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        获取适合删除的加权日记
        
        Args:
            db_manager: 数据库管理器实例
            limit: 最多考虑的日记数量
        
        Returns:
            选中的日记
        """
        # 获取日记数据
        if limit is None:
            # 获取全部日记，按日期升序排列
            diaries = db_manager._execute(
                "SELECT * FROM diaries ORDER BY date ASC",
                fetch='all'
            )
        else:
            # 仅获取指定数量的日记
            diaries = db_manager._execute(
                "SELECT * FROM diaries ORDER BY date ASC LIMIT ?",
                (limit,),
                fetch='all'
            )
        
        if not diaries:
            return None
        
        calculator = cls()
        return calculator.service.get_weighted_deletion_diary_from_data(diaries)