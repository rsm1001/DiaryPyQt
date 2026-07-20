"""
权重计算核心模块单元测试
测试 models/calculations/weight_calculation_core.py 中的 calculate_raw_weights 函数
"""
import math
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from models.calculations.weight_calculation_core import calculate_raw_weights


class TestCalculateRawWeights:
    """测试 calculate_raw_weights 函数"""

    # =========================================================================
    # 基础功能测试
    # =========================================================================

    def test_basic_structure_random_mode(self, sample_diary_base, fixed_now):
        """验证random模式返回的结构包含所有必要字段"""
        diary = {**sample_diary_base, 'date': '2026-05-20 12:00:00'}

        result = calculate_raw_weights(diary, fixed_now, 'random')

        assert 'time_weight_raw' in result
        assert 'count_weight_raw' in result
        assert 'days_ago' in result
        assert 'use_count' in result
        assert 'view_count_weight_raw' not in result  # random模式不应有此字段

    def test_basic_structure_deletion_mode(self, sample_diary_base, fixed_now):
        """验证deletion模式返回的结构包含所有必要字段"""
        diary = {**sample_diary_base, 'date': '2026-05-20 12:00:00'}

        result = calculate_raw_weights(diary, fixed_now, 'deletion')

        assert 'time_weight_raw' in result
        assert 'view_count_weight_raw' in result
        assert 'days_ago' in result
        assert 'view_count' in result
        assert 'count_weight_raw' not in result  # deletion模式不应有此字段

    # =========================================================================
    # 时间权重测试
    # =========================================================================

    def test_time_weight_today(self, sample_diary_base):
        """今天: days_ago=0, time_weight_raw = log(0+1) = log(1) = 0"""
        now = datetime(2026, 5, 21, 12, 0, 0)
        diary = {**sample_diary_base, 'date': '2026-05-21 12:00:00'}

        result = calculate_raw_weights(diary, now, 'random')

        assert result['days_ago'] == 0
        assert result['time_weight_raw'] == pytest.approx(math.log(1))  # = 0

    def test_time_weight_one_day_ago(self, sample_diary_base):
        """1天前: days_ago=1, time_weight_raw = log(1+1) = log(2) ≈ 0.693"""
        now = datetime(2026, 5, 21, 12, 0, 0)
        diary = {**sample_diary_base, 'date': '2026-05-20 12:00:00'}

        result = calculate_raw_weights(diary, now, 'random')

        assert result['days_ago'] == 1
        assert result['time_weight_raw'] == pytest.approx(math.log(2))  # ≈ 0.693

    def test_random_time_weight_uses_last_viewed_at_when_viewed(self, sample_diary_base):
        """已查看日记按 last_viewed_at 计算冷却，不按创建时间"""
        now = datetime(2026, 5, 21, 12, 0, 0)
        diary = {
            **sample_diary_base,
            'date': '2020-01-01 12:00:00',
            'last_viewed_at': '2026-05-20 12:00:00',
            'view_count': 3,
        }

        result = calculate_raw_weights(diary, now, 'random')

        assert result['days_ago'] == 1
        assert result['time_weight_raw'] == pytest.approx(math.log(2))

    def test_random_time_weight_zero_views_uses_created_at(self, sample_diary_base):
        """零次查看日记按创建时间计算，忽略异常 last_viewed_at"""
        now = datetime(2026, 5, 21, 12, 0, 0)
        diary = {
            **sample_diary_base,
            'date': '2026-05-11 12:00:00',
            'last_viewed_at': '2026-05-20 12:00:00',
            'view_count': 0,
        }

        result = calculate_raw_weights(diary, now, 'random')

        assert result['days_ago'] == 10
        assert result['time_weight_raw'] == pytest.approx(math.log(11))

    def test_random_time_weight_fallbacks_to_created_at_without_last_viewed(self, sample_diary_base):
        """旧数据已查看但无 last_viewed_at 时回退创建时间"""
        now = datetime(2026, 5, 21, 12, 0, 0)
        diary = {
            **sample_diary_base,
            'date': '2026-05-18 12:00:00',
            'view_count': 2,
        }

        result = calculate_raw_weights(diary, now, 'random')

        assert result['days_ago'] == 3
        assert result['time_weight_raw'] == pytest.approx(math.log(4))

    def test_deletion_time_weight_still_uses_created_at(self, sample_diary_base):
        """删除模式仍按创建时间判断久远程度"""
        now = datetime(2026, 5, 21, 12, 0, 0)
        diary = {
            **sample_diary_base,
            'date': '2026-05-11 12:00:00',
            'last_viewed_at': '2026-05-20 12:00:00',
            'view_count': 3,
        }

        result = calculate_raw_weights(diary, now, 'deletion')

        assert result['days_ago'] == 10
        assert result['time_weight_raw'] == pytest.approx(math.log(11))

    def test_time_weight_one_year_ago(self, sample_diary_base):
        """1年前: days_ago=365, time_weight_raw = log(365+1) = log(366) ≈ 5.9"""
        now = datetime(2026, 5, 21, 12, 0, 0)
        diary = {**sample_diary_base, 'date': '2025-05-21 12:00:00'}

        result = calculate_raw_weights(diary, now, 'random')

        assert result['days_ago'] == 365
        assert result['time_weight_raw'] == pytest.approx(math.log(366))  # ≈ 5.9

    def test_time_weight_is_monotonic(self, sample_diary_base, fixed_now):
        """时间越久远，time_weight_raw越大（对数函数的单调性）"""
        diaries = []
        for days in [0, 1, 7, 30, 365]:
            diary_date = fixed_now - timedelta(days=days)
            diary = {**sample_diary_base, 'date': diary_date.strftime("%Y-%m-%d %H:%M:%S")}
            diaries.append(diary)

        weights = [calculate_raw_weights(d, fixed_now, 'random')['time_weight_raw'] for d in diaries]

        # 验证单调递增
        for i in range(len(weights) - 1):
            assert weights[i] < weights[i + 1], f"Weight at index {i} should be less than weight at index {i+1}"

    # =========================================================================
    # Random模式 - 次数权重测试 (count_weight_raw)
    # =========================================================================

    def test_count_weight_zero_views(self, sample_diary_base, fixed_now):
        """view_count=0: count_weight_raw = 1 / ((0+1) ** 1.5) = 1"""
        diary = {**sample_diary_base, 'date': '2026-05-20 12:00:00', 'view_count': 0}

        result = calculate_raw_weights(diary, fixed_now, 'random')

        expected = 1.0 / ((0 + 1) ** 1.5)
        assert result['use_count'] == 0
        assert result['count_weight_raw'] == pytest.approx(expected)  # = 1

    def test_count_weight_one_view(self, sample_diary_base, fixed_now):
        """view_count=1: count_weight_raw = 1 / ((1+1) ** 1.5) = 1 / (2^1.5) ≈ 0.354"""
        diary = {**sample_diary_base, 'date': '2026-05-20 12:00:00', 'view_count': 1}

        result = calculate_raw_weights(diary, fixed_now, 'random')

        expected = 1.0 / ((1 + 1) ** 1.5)
        assert result['use_count'] == 1
        assert result['count_weight_raw'] == pytest.approx(expected)  # ≈ 0.354

    def test_count_weight_ten_views(self, sample_diary_base, fixed_now):
        """view_count=10: count_weight_raw = 1 / ((10+1) ** 1.5) ≈ 0.027"""
        diary = {**sample_diary_base, 'date': '2026-05-20 12:00:00', 'view_count': 10}

        result = calculate_raw_weights(diary, fixed_now, 'random')

        expected = 1.0 / ((10 + 1) ** 1.5)
        assert result['use_count'] == 10
        assert result['count_weight_raw'] == pytest.approx(expected)  # ≈ 0.027

    def test_count_weight_is_decreasing(self, sample_diary_base, fixed_now):
        """使用次数越多，count_weight_raw越小（倒数衰减特性）"""
        diaries = []
        for views in [0, 1, 5, 10, 100]:
            diary = {**sample_diary_base, 'date': '2026-05-20 12:00:00', 'view_count': views}
            diaries.append(diary)

        weights = [calculate_raw_weights(d, fixed_now, 'random')['count_weight_raw'] for d in diaries]

        # 验证单调递减
        for i in range(len(weights) - 1):
            assert weights[i] > weights[i + 1], f"Weight at view_count={i} should be greater than weight at view_count={i+10}"

    # =========================================================================
    # Deletion模式 - 查看次数权重测试 (view_count_weight_raw)
    # =========================================================================

    def test_view_count_weight_zero(self, sample_diary_base, fixed_now):
        """view_count=0: view_count_weight_raw = sqrt(0) = 0"""
        diary = {**sample_diary_base, 'date': '2026-05-20 12:00:00', 'view_count': 0}

        result = calculate_raw_weights(diary, fixed_now, 'deletion')

        assert result['view_count'] == 0
        assert result['view_count_weight_raw'] == pytest.approx(0.0)

    def test_view_count_weight_hundred(self, sample_diary_base, fixed_now):
        """view_count=100: view_count_weight_raw = sqrt(100) = 10"""
        diary = {**sample_diary_base, 'date': '2026-05-20 12:00:00', 'view_count': 100}

        result = calculate_raw_weights(diary, fixed_now, 'deletion')

        assert result['view_count'] == 100
        assert result['view_count_weight_raw'] == pytest.approx(10.0)

    def test_view_count_weight_is_increasing(self, sample_diary_base, fixed_now):
        """查看次数越多，view_count_weight_raw越大（平方根增长特性）"""
        diaries = []
        for views in [0, 1, 4, 9, 100]:
            diary = {**sample_diary_base, 'date': '2026-05-20 12:00:00', 'view_count': views}
            diaries.append(diary)

        weights = [calculate_raw_weights(d, fixed_now, 'deletion')['view_count_weight_raw'] for d in diaries]

        # 验证单调递增
        for i in range(len(weights) - 1):
            assert weights[i] < weights[i + 1], f"Weight at view_count={i} should be less than weight at view_count={i+1}"

    # =========================================================================
    # 边界条件测试
    # =========================================================================

    def test_future_date_handling(self, sample_diary_base, fixed_now):
        """未来日期应被安全处理：days_ago clamp 到 0，time_weight_raw = log(1) = 0"""
        future_date = fixed_now + timedelta(days=7)
        diary = {**sample_diary_base, 'date': future_date.strftime("%Y-%m-%d %H:%M:%S")}

        result = calculate_raw_weights(diary, fixed_now, 'random')

        # 不再抛 ValueError；未来日期的 time 权重等同于"今天"
        assert result['days_ago'] == -7
        assert result['time_weight_raw'] == 0

    def test_very_old_date(self, sample_diary_base, fixed_now):
        """极老日期（10年前）仍能正常计算"""
        old_date = fixed_now - timedelta(days=3650)
        diary = {**sample_diary_base, 'date': old_date.strftime("%Y-%m-%d %H:%M:%S")}

        result = calculate_raw_weights(diary, fixed_now, 'random')

        assert result['days_ago'] == 3650
        assert result['time_weight_raw'] > 0

    def test_very_high_view_count(self, sample_diary_base, fixed_now):
        """极高查看次数（100000+）仍能正常计算"""
        diary = {**sample_diary_base, 'date': '2026-05-20 12:00:00', 'view_count': 100000}

        result = calculate_raw_weights(diary, fixed_now, 'random')

        assert result['use_count'] == 100000
        assert result['count_weight_raw'] > 0  # 仍然是正数

    def test_both_selection_types_produce_different_results(self, sample_diary_base, fixed_now):
        """同一篇日记在random和deletion模式下应产生不同的权重"""
        diary = {**sample_diary_base, 'date': '2026-05-20 12:00:00', 'view_count': 50}

        result_random = calculate_raw_weights(diary, fixed_now, 'random')
        result_deletion = calculate_raw_weights(diary, fixed_now, 'deletion')

        # 次数权重字段名不同
        assert 'count_weight_raw' in result_random
        assert 'view_count_weight_raw' in result_deletion

        # 值不同：random用倒数，deletion用平方根
        assert result_random['count_weight_raw'] != result_deletion['view_count_weight_raw']
