"""
权重计算器模块
用于处理日记选择中的复杂权重计算逻辑
"""
import random
import math
from datetime import datetime
from typing import List, Dict, Optional, Any
# 修正导入路径
from .enhanced_database import EnhancedDatabaseManager


class WeightCalculator:
    """
    权重计算器
    负责处理日记选择中的复杂权重算法
    """
    
    @staticmethod
    def calculate_selection_weights(
        diaries: List[Dict[str, Any]], 
        selection_type: str = 'random'
    ) -> List[tuple]:
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
        
        # 计算各项的原始权重，但不立即归一化
        diary_details = []  # 存储日记和其原始权重，便于分析
        for diary in diaries:
            # 解析日期
            date = datetime.strptime(diary['date'], "%Y-%m-%d %H:%M:%S")
            
            # 计算距离今天的天数
            days_ago = (now - date).days
            
            if selection_type == 'deletion':
                # 删除模式：偏向时间久远且查看次数多的日记
                # 原始时间权重：距离现在的天数（越久远，值越大）
                time_weight_raw = math.log(days_ago + 1)  # 加1避免log(0)
                
                # 原始查看次数权重：查看次数越多，越适合删除
                view_count = diary['view_count']
                # 使用平方根函数平滑差异，查看次数越多权重越大
                view_count_weight_raw = math.sqrt(view_count)
                
                diary_details.append({
                    'diary': diary,
                    'time_weight_raw': time_weight_raw,
                    'view_count_weight_raw': view_count_weight_raw,
                    'days_ago': days_ago,
                    'view_count': view_count
                })
            else:  # random mode
                # 随机选择模式：使用次数越少，被选中概率越大
                # 原始时间权重：距离现在的天数（越久远，值越大）
                time_weight_raw = math.log(days_ago + 1)  # 加1避免log(0)
                
                # 原始次数权重：使用次数越少，权重越大
                use_count = diary['view_count']
                # 使用更强的倒数函数，提高敏感度
                count_weight_raw = 1.0 / ((use_count + 1) ** 1.5)  # 使用1.5次幂，提高敏感度
                
                diary_details.append({
                    'diary': diary,
                    'time_weight_raw': time_weight_raw,
                    'count_weight_raw': count_weight_raw,
                    'days_ago': days_ago,
                    'use_count': use_count
                })
        
        # 使用分位数归一化而不是最小-最大归一化
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
        
        # 返回带权重的日记列表
        return [(item['diary'], item['final_weight']) for item in diary_details]
    
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