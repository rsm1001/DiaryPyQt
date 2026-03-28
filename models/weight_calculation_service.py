"""
权重计算服务模块
将权重计算逻辑从数据库操作中分离，提高模块独立性和可测试性
"""
import random
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple, Protocol

from .weight_calculation_core import calculate_raw_weights


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
        n = len(diary_details)
        
        if selection_type == 'deletion':
            # 按时间权重排序，分配分位数
            sorted_by_time = sorted(diary_details, key=lambda x: x['time_weight_raw'])
            for i, item in enumerate(sorted_by_time):
                # 分位数值在[0,1]区间 - 时间越久远，权重越高
                item['time_weight_norm'] = i / (n - 1) if n > 1 else 0.5
            
            # 按查看次数权重排序，分配分位数
            sorted_by_view_count = sorted(diary_details, key=lambda x: x['view_count'])  # 按查看次数升序排列
            for i, item in enumerate(sorted_by_view_count):
                # 查看次数多的获得更高的分位数
                item['view_count_weight_norm'] = i / (n - 1) if n > 1 else 0.5
            
            # 计算最终权重
            for item in diary_details:
                # 权重加权求和（时间权重和查看次数权重，偏向删除久远且热门的日记）
                alpha = 0.6  # 时间权重系数（略高，因为久远是更重要的删除因素）
                beta = 0.4   # 查看次数权重系数
                
                final_weight = alpha * item['time_weight_norm'] + beta * item['view_count_weight_norm']
                item['final_weight'] = final_weight
        else:  # random mode
            # 按时间权重排序，分配分位数
            sorted_by_time = sorted(diary_details, key=lambda x: x['time_weight_raw'])
            for i, item in enumerate(sorted_by_time):
                # 分位数值在[0,1]区间
                item['time_weight_norm'] = i / (n - 1) if n > 1 else 0.5
            
            # 按次数权重排序，分配分位数 - 次数少的获得更高的分位数
            sorted_by_count = sorted(diary_details, key=lambda x: x['use_count'])  # 按使用次数升序排列
            for i, item in enumerate(sorted_by_count):
                # 次数少的获得更高的分位数，使用 (n-1-i)/(n-1) 实现倒序
                item['count_weight_norm'] = (n - 1 - i) / (n - 1) if n > 1 else 0.5
            
            # 计算最终权重
            for item in diary_details:
                # 权重加权求和（给次数权重更高的系数，突出使用次数少的重要性）
                alpha = 0.2  # 时间权重系数
                beta = 1.0   # 次数权重系数 (beta > alpha，突出次数权重重要性)
                
                final_weight = alpha * item['time_weight_norm'] + beta * item['count_weight_norm']
                item['final_weight'] = final_weight
        
        return diary_details
    
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