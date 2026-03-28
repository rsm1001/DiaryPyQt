"""
权重计算核心模块
用于处理日记选择中的基础权重计算逻辑，不依赖具体数据库实现
"""
import math
from datetime import datetime
from typing import Dict, Any


def calculate_raw_weights(diary: Dict[str, Any], now: datetime, selection_type: str) -> Dict[str, float]:
    """
    计算单个日记的原始权重
    
    Args:
        diary: 日记字典
        now: 当前时间
        selection_type: 选择类型 ('random' 或 'deletion')
    
    Returns:
        包含各种原始权重的字典
    """
    # 解析日期
    date = datetime.strptime(diary['date'], "%Y-%m-%d %H:%M:%S")
    
    # 计算距离今天的天数
    days_ago = (now - date).days
    time_weight_raw = math.log(days_ago + 1)  # 加1避免log(0)
    
    if selection_type == 'deletion':
        # 删除模式：偏向时间久远且查看次数多的日记
        view_count = diary['view_count']
        view_count_weight_raw = math.sqrt(view_count)
        
        return {
            'time_weight_raw': time_weight_raw,
            'view_count_weight_raw': view_count_weight_raw,
            'days_ago': days_ago,
            'view_count': view_count
        }
    else:  # random mode
        # 随机选择模式：使用次数越少，被选中概率越大
        use_count = diary['view_count']
        # 使用更强的倒数函数，提高敏感度
        count_weight_raw = 1.0 / ((use_count + 1) ** 1.5)  # 使用1.5次幂，提高敏感度
        
        return {
            'time_weight_raw': time_weight_raw,
            'count_weight_raw': count_weight_raw,
            'days_ago': days_ago,
            'use_count': use_count
        }