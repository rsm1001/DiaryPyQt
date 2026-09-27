"""
权重计算核心模块
用于处理日记选择中的基础权重计算逻辑，不依赖具体数据库实现
"""
import math
from datetime import datetime
from typing import Dict, Any

_DATETIME_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d")


def _parse_diary_datetime(value: Any) -> datetime:
    """解析日记时间，兼容旧导入数据的日期格式"""
    if isinstance(value, datetime):
        return value

    text = str(value or '').strip()
    for date_format in _DATETIME_FORMATS:
        try:
            return datetime.strptime(text, date_format)
        except ValueError:
            continue
    return datetime.fromisoformat(text)


def _get_random_reference_datetime(diary: Dict[str, Any]) -> datetime:
    """随机查看按上次查看时间计算冷却，零次查看按创建时间计算"""
    view_count = int(diary.get('view_count') or 0)
    last_viewed_at = diary.get('last_viewed_at')
    if view_count > 0 and last_viewed_at:
        try:
            return _parse_diary_datetime(last_viewed_at)
        except ValueError:
            pass
    return _parse_diary_datetime(diary['date'])


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
    if selection_type == 'random':
        date = _get_random_reference_datetime(diary)
    else:
        date = _parse_diary_datetime(diary['date'])

    days_ago = (now - date).days
    # 未来日期（days_ago < 0）按"今天"处理，避免 math.log 报 domain error
    days_ago_for_weight = max(0, days_ago)
    time_weight_raw = math.log(days_ago_for_weight + 1)

    if selection_type == 'deletion':
        # 删除模式：偏向时间久远且查看次数多的日记
        view_count = int(diary['view_count'])
        view_count_weight_raw = math.sqrt(view_count)

        return {
            'time_weight_raw': time_weight_raw,
            'view_count_weight_raw': view_count_weight_raw,
            'days_ago': days_ago,
            'view_count': view_count
        }
    else:  # random mode
        # 随机选择模式：使用次数越少，被选中概率越大
        use_count = int(diary['view_count'])
        # 使用更强的倒数函数，提高敏感度
        count_weight_raw = 1.0 / ((use_count + 1) ** 1.5)

        return {
            'time_weight_raw': time_weight_raw,
            'count_weight_raw': count_weight_raw,
            'days_ago': days_ago,
            'use_count': use_count
        }
