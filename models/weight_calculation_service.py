"""
权重计算服务模块
将权重计算逻辑从数据库操作中分离，提高模块独立性和可测试性
"""
import random
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple, Protocol

from .weight_calculation_core import calculate_raw_weights
from .strategies.weight.normalization_strategies import NormalizationStrategyFactory


class DatabaseManagerInterface(Protocol):
    """
    数据库管理器接口，定义数据库操作协议
    """
    def get_all_diaries(self) -> List[Dict[str, Any]]:
        ...
    
    def get_diaries_with_limit(self, limit: int) -> List[Dict[str, Any]]:
        ...


class WeightCalculationService:
    """
    权重计算服务
    专门负责处理日记选择中的权重计算逻辑，不依赖具体的数据库实现
    """
    
    @staticmethod
    def _normalize_weights(diary_details: List[Dict], selection_type: str) -> List[Dict]:
        """
        归一化权重值
        
        Args:
            diary_details: 包含日记和原始权重信息的列表
            selection_type: 选择类型 ('random' 或 'deletion')
        
        Returns:
            包含归一化权重的更新后的列表
        """
        strategy = NormalizationStrategyFactory.get_strategy(selection_type)
        return strategy.normalize(diary_details)
    
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
        if not diaries:
            return []
            
        # 计算当前日期，用于计算时间权重
        now = datetime.now()
        
        # 计算各项的原始权重
        diary_details = []  # 存储日记和其原始权重，便于分析
        for diary in diaries:
            raw_weights = calculate_raw_weights(diary, now, selection_type)
            diary_detail = {'diary': diary}
            diary_detail.update(raw_weights)
            diary_details.append(diary_detail)
        
        # 归一化权重
        diary_details = WeightCalculationService._normalize_weights(diary_details, selection_type)
        
        # 返回带权重的日记列表
        return [(item['diary'], item['final_weight']) for item in diary_details]
    
    @staticmethod
    def select_by_weight(weighted_diaries: List[Tuple[Dict[str, Any], float]]) -> Optional[Dict[str, Any]]:
        """
        根据权重选择日记
        
        Args:
            weighted_diaries: 包含(日记, 权重)元组的列表
        
        Returns:
            选中的日记
        """
        if not weighted_diaries:
            return None
            
        diaries = [wd[0] for wd in weighted_diaries]
        weights = [wd[1] for wd in weighted_diaries]
        
        # 按权重进行加权随机选择
        if weights and sum(weights) > 0:
            # 根据权重随机选择一个
            selected_diary = random.choices(diaries, weights=weights, k=1)[0]
            return selected_diary
        else:
            # 如果权重有问题，退回到随机选择
            return random.choice(diaries) if diaries else None

    def get_weighted_random_diary_from_data(
        self, 
        diaries: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        从给定的日记数据中获取加权随机日记
        
        Args:
            diaries: 日记数据列表
        
        Returns:
            选中的日记
        """
        if not diaries:
            return None
        
        # 使用权重计算器计算权重
        weighted_diaries = self.calculate_selection_weights(diaries, 'random')
        
        # 根据权重选择日记
        selected_diary = self.select_by_weight(weighted_diaries)
        
        return selected_diary

    def get_weighted_deletion_diary_from_data(
        self, 
        diaries: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        从给定的日记数据中获取适合删除的加权日记
        
        Args:
            diaries: 日记数据列表
        
        Returns:
            选中的日记
        """
        if not diaries:
            return None
        
        # 使用权重计算器计算权重
        weighted_diaries = self.calculate_selection_weights(diaries, 'deletion')
        
        # 根据权重选择日记
        selected_diary = self.select_by_weight(weighted_diaries)
        
        return selected_diary
    
    def get_weighted_random_diary_with_db_interface(
        self, 
        db_interface: DatabaseManagerInterface, 
        limit: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        使用数据库接口获取加权随机日记
        
        Args:
            db_interface: 数据库接口实现
            limit: 最多考虑的日记数量
        
        Returns:
            选中的日记
        """
        diaries = db_interface.get_all_diaries() if limit is None else db_interface.get_diaries_with_limit(limit)
        
        if not diaries:
            return None
        
        return self.get_weighted_random_diary_from_data(diaries)
    
    def get_weighted_deletion_diary_with_db_interface(
        self, 
        db_interface: DatabaseManagerInterface, 
        limit: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        使用数据库接口获取适合删除的加权日记
        
        Args:
            db_interface: 数据库接口实现
            limit: 最多考虑的日记数量
        
        Returns:
            选中的日记
        """
        diaries = db_interface.get_all_diaries() if limit is None else db_interface.get_diaries_with_limit(limit)
        
        if not diaries:
            return None
        
        return self.get_weighted_deletion_diary_from_data(diaries)