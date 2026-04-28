"""
日记选择服务模块
将日记选择逻辑从数据库操作中分离，提高模块独立性和可测试性
"""
import random
from datetime import datetime
from typing import List, Dict, Optional, Any
from .calculation_service import WeightCalculationService


class DiarySelectionService:
    """
    日记选择服务
    专门负责处理日记的随机选择、删除选择等逻辑，不依赖具体的数据库实现
    """

    def __init__(self):
        """初始化服务"""
        self.weight_calculation_service = WeightCalculationService()

    def get_weighted_random_diary(self, diaries: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        从给定的日记数据中获取加权随机日记（查看次数越少，被选中概率越大）

        Args:
            diaries: 日记数据列表

        Returns:
            选中的日记
        """
        if not diaries:
            return None

        return self.weight_calculation_service.get_weighted_random_diary_from_data(diaries)

    def get_weighted_deletion_diary(self, diaries: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        从给定的日记数据中获取适合删除的加权日记（时间久远且查看次数多，被选中概率越大）

        Args:
            diaries: 日记数据列表

        Returns:
            选中的日记
        """
        if not diaries:
            return None

        return self.weight_calculation_service.get_weighted_deletion_diary_from_data(diaries)

    def get_random_diary(self, diaries: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        从给定的日记数据中随机选择一篇日记

        Args:
            diaries: 日记数据列表

        Returns:
            选中的日记
        """
        if not diaries:
            return None

        return random.choice(diaries)

    def get_oldest_diary(self, diaries: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        获取最久远的日记

        Args:
            diaries: 日记数据列表

        Returns:
            最久远的日记
        """
        if not diaries:
            return None

        # 按日期排序，取最早的
        sorted_diaries = sorted(diaries, key=lambda x: x['date'])
        return sorted_diaries[0] if sorted_diaries else None

    def get_most_viewed_diary(self, diaries: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        获取查看次数最多的日记

        Args:
            diaries: 日记数据列表

        Returns:
            查看次数最多的日记
        """
        if not diaries:
            return None

        # 按查看次数降序排序，取第一个
        sorted_diaries = sorted(diaries, key=lambda x: x['view_count'], reverse=True)
        return sorted_diaries[0] if sorted_diaries else None

    def get_least_viewed_diary(self, diaries: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        获取查看次数最少的日记

        Args:
            diaries: 日记数据列表

        Returns:
            查看次数最少的日记
        """
        if not diaries:
            return None

        # 按查看次数升序排序，取第一个
        sorted_diaries = sorted(diaries, key=lambda x: x['view_count'])
        return sorted_diaries[0] if sorted_diaries else None