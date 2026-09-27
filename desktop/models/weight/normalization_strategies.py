"""
权重归一化策略模块
定义不同场景下的权重归一化策略，实现策略模式
"""
from typing import List, Dict, Any
from abc import ABC, abstractmethod


class NormalizationStrategy(ABC):
    """
    权重归一化策略抽象基类
    """
    
    @abstractmethod
    def normalize(self, diary_details: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        归一化权重值
        
        Args:
            diary_details: 包含日记和原始权重信息的列表
        
        Returns:
            包含归一化权重的更新后的列表
        """
        pass


class RandomSelectionNormalization(NormalizationStrategy):
    """
    随机选择模式的权重归一化策略
    """
    
    def normalize(self, diary_details: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        随机选择模式的归一化逻辑
        偏向于选择使用次数少的日记
        
        Args:
            diary_details: 包含日记和原始权重信息的列表
        
        Returns:
            包含归一化权重的更新后的列表
        """
        n = len(diary_details)
        if n <= 1:
            for item in diary_details:
                item['time_weight_norm'] = 0.5
                item['count_weight_norm'] = 0.5
                item['final_weight'] = 0.5
            return diary_details

        # 按时间权重排序，分配分位数
        sorted_by_time = sorted(diary_details, key=lambda x: x['time_weight_raw'])
        for i, item in enumerate(sorted_by_time):
            # 分位数值在[0,1]区间
            item['time_weight_norm'] = i / (n - 1)

        # 按次数权重排序，分配分位数 - 次数少的获得更高的分位数
        sorted_by_count = sorted(diary_details, key=lambda x: x['use_count'])  # 按使用次数升序排列
        for i, item in enumerate(sorted_by_count):
            # 次数少的获得更高的分位数，使用 (n-1-i)/(n-1) 实现倒序
            item['count_weight_norm'] = (n - 1 - i) / (n - 1)

        max_views = max(item['use_count'] for item in diary_details)

        # 计算最终权重
        for item in diary_details:
            # 零次查看是新内容入口，优先级高于普通冷却和低次数倾斜。
            zero_view_bonus = 0.5 if item['use_count'] == 0 and max_views > 0 else 0.0
            alpha = 0.3  # 时间权重系数
            beta = 1.0   # 次数权重系数 (beta > alpha，突出次数权重重要性)

            final_weight = (
                alpha * item['time_weight_norm']
                + beta * item['count_weight_norm']
                + zero_view_bonus
            )
            item['final_weight'] = final_weight

        return diary_details


class DeletionSelectionNormalization(NormalizationStrategy):
    """
    删除选择模式的权重归一化策略
    """
    
    def normalize(self, diary_details: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        删除选择模式的归一化逻辑
        偏向于删除时间久远且查看次数多的日记
        
        Args:
            diary_details: 包含日记和原始权重信息的列表
        
        Returns:
            包含归一化权重的更新后的列表
        """
        n = len(diary_details)
        if n <= 1:
            for item in diary_details:
                item['time_weight_norm'] = 0.5
                item['view_count_weight_norm'] = 0.5
                item['final_weight'] = 0.5
            return diary_details

        # 按时间权重排序，分配分位数
        sorted_by_time = sorted(diary_details, key=lambda x: x['time_weight_raw'])
        for i, item in enumerate(sorted_by_time):
            # 分位数值在[0,1]区间 - 时间越久远，权重越高
            item['time_weight_norm'] = i / (n - 1)

        # 按查看次数权重排序，分配分位数
        sorted_by_view_count = sorted(diary_details, key=lambda x: x['view_count'])  # 按查看次数升序排列
        for i, item in enumerate(sorted_by_view_count):
            # 查看次数多的获得更高的分位数
            item['view_count_weight_norm'] = i / (n - 1)

        # 计算最终权重
        for item in diary_details:
            # 权重加权求和（时间权重和查看次数权重，偏向删除久远且热门的日记）
            alpha = 0.6  # 时间权重系数（略高，因为久远是更重要的删除因素）
            beta = 0.4   # 查看次数权重系数

            final_weight = alpha * item['time_weight_norm'] + beta * item['view_count_weight_norm']
            item['final_weight'] = final_weight

        return diary_details


class NormalizationStrategyFactory:
    """
    权重归一化策略工厂类
    根据选择类型返回对应的归一化策略
    """
    
    @staticmethod
    def get_strategy(selection_type: str) -> NormalizationStrategy:
        """
        根据选择类型获取相应的归一化策略
        
        Args:
            selection_type: 选择类型 ('random' 或 'deletion')
        
        Returns:
            对应的归一化策略实例
        """
        if selection_type == 'random':
            return RandomSelectionNormalization()
        elif selection_type == 'deletion':
            return DeletionSelectionNormalization()
        else:
            raise ValueError(f"Unsupported selection type: {selection_type}")