"""
权重计算器模块
用于处理日记选择中的复杂权重计算逻辑
"""
import random
import math
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple
# 修正导入路径
from .enhanced_database import EnhancedDatabaseManager
from .weight_calculation_core import calculate_raw_weights


class WeightCalculator:
    """
    权重计算器
    负责处理日记选择中的复杂权重算法
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
        diary_details = WeightCalculator._normalize_weights(diary_details, selection_type)
        
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
        
        # 使用权重计算器计算权重
        weighted_diaries = cls.calculate_selection_weights(diaries, 'random')
        
        # 根据权重选择日记
        selected_diary = cls.select_by_weight(weighted_diaries)
        
        return selected_diary
    
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
        
        # 使用权重计算器计算权重
        weighted_diaries = cls.calculate_selection_weights(diaries, 'deletion')
        
        # 根据权重选择日记
        selected_diary = cls.select_by_weight(weighted_diaries)
        
        return selected_diary
    
    @staticmethod
    def select_by_weight(weighted_diaries: List[tuple]) -> Optional[Dict[str, Any]]:
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
        
        # 使用权重计算器计算权重
        weighted_diaries = cls.calculate_selection_weights(diaries, 'random')
        
        # 根据权重选择日记
        selected_diary = cls.select_by_weight(weighted_diaries)
        
        return selected_diary
    
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
        
        # 使用权重计算器计算权重
        weighted_diaries = cls.calculate_selection_weights(diaries, 'deletion')
        
        # 根据权重选择日记
        selected_diary = cls.select_by_weight(weighted_diaries)
        
        return selected_diary