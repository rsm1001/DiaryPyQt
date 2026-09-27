"""
权重归一化策略单元测试
测试 models/weight/normalization_strategies.py 中的各个策略类
"""
import pytest

from models.weight.normalization_strategies import (
    NormalizationStrategy,
    RandomSelectionNormalization,
    DeletionSelectionNormalization,
    NormalizationStrategyFactory,
)
from models.calculations.weight_calculation_core import calculate_raw_weights


class TestNormalizationStrategyFactory:
    """测试 NormalizationStrategyFactory 工厂类"""

    def test_get_random_strategy(self):
        """获取random策略"""
        strategy = NormalizationStrategyFactory.get_strategy('random')
        assert isinstance(strategy, RandomSelectionNormalization)

    def test_get_deletion_strategy(self):
        """获取deletion策略"""
        strategy = NormalizationStrategyFactory.get_strategy('deletion')
        assert isinstance(strategy, DeletionSelectionNormalization)

    def test_unsupported_strategy_raises_error(self):
        """不支持的类型应抛出ValueError"""
        with pytest.raises(ValueError) as exc_info:
            NormalizationStrategyFactory.get_strategy('invalid')
        assert "Unsupported selection type" in str(exc_info.value)


class TestRandomSelectionNormalization:
    """测试 RandomSelectionNormalization 随机选择归一化策略"""

    @pytest.fixture
    def strategy(self):
        return RandomSelectionNormalization()

    # =========================================================================
    # 边界条件测试
    # =========================================================================

    def test_single_item_returns_half_weight(self, strategy, sample_diary_base, fixed_now):
        """单元素时，final_weight应为0.5"""
        diary = {**sample_diary_base, 'date': '2026-05-20 12:00:00', 'view_count': 10}
        raw_weights = calculate_raw_weights(diary, fixed_now, 'random')
        diary_details = [{'diary': diary, **raw_weights}]

        result = strategy.normalize(diary_details)

        assert len(result) == 1
        assert result[0]['final_weight'] == pytest.approx(0.5)
        assert result[0]['time_weight_norm'] == pytest.approx(0.5)
        assert result[0]['count_weight_norm'] == pytest.approx(0.5)

    def test_empty_list_returns_empty(self, strategy):
        """空列表应直接返回"""
        result = strategy.normalize([])
        assert result == []

    def test_two_items_basic_normalization(self, strategy, sample_diary_base, fixed_now):
        """两元素归一化测试"""
        diary1 = {**sample_diary_base, 'id': 1, 'date': '2026-05-20 12:00:00', 'view_count': 0}
        diary2 = {**sample_diary_base, 'id': 2, 'date': '2026-05-20 12:00:00', 'view_count': 10}

        raw1 = calculate_raw_weights(diary1, fixed_now, 'random')
        raw2 = calculate_raw_weights(diary2, fixed_now, 'random')

        diary_details = [
            {'diary': diary1, **raw1},
            {'diary': diary2, **raw2},
        ]

        result = strategy.normalize(diary_details)

        # 两元素分位数应为0和1
        for item in result:
            assert item['time_weight_norm'] in [0.0, 1.0]
            assert item['count_weight_norm'] in [0.0, 1.0]

    # =========================================================================
    # 不变量测试
    # =========================================================================

    def test_time_weight_norm_in_range(self, strategy, sample_diaries, fixed_now):
        """time_weight_norm应在[0,1]区间内"""
        diary_details = []
        for diary in sample_diaries:
            raw = calculate_raw_weights(diary, fixed_now, 'random')
            diary_details.append({'diary': diary, **raw})

        result = strategy.normalize(diary_details)

        for item in result:
            assert 0.0 <= item['time_weight_norm'] <= 1.0, \
                f"time_weight_norm={item['time_weight_norm']} out of range"

    def test_count_weight_norm_in_range(self, strategy, sample_diaries, fixed_now):
        """count_weight_norm应在[0,1]区间内"""
        diary_details = []
        for diary in sample_diaries:
            raw = calculate_raw_weights(diary, fixed_now, 'random')
            diary_details.append({'diary': diary, **raw})

        result = strategy.normalize(diary_details)

        for item in result:
            assert 0.0 <= item['count_weight_norm'] <= 1.0, \
                f"count_weight_norm={item['count_weight_norm']} out of range"

    def test_final_weight_in_expected_range(self, strategy, sample_diaries, fixed_now):
        """final_weight应在合理范围内 (alpha=0.3, beta=1.0, bonus=0.5)"""
        diary_details = []
        for diary in sample_diaries:
            raw = calculate_raw_weights(diary, fixed_now, 'random')
            diary_details.append({'diary': diary, **raw})

        result = strategy.normalize(diary_details)

        # min: 0, max: 0.3*1 + 1.0*1 + 0.5 = 1.8
        for item in result:
            assert 0.0 <= item['final_weight'] <= 1.8, \
                f"final_weight={item['final_weight']} out of expected range [0, 1.8]"

    def test_zero_view_diary_gets_extra_bonus(self, strategy, sample_diary_base, fixed_now):
        """零次查看日记应额外加权，避免长期沉底"""
        diaries = [
            {**sample_diary_base, 'id': 1, 'date': '2026-05-20 12:00:00', 'view_count': 0},
            {**sample_diary_base, 'id': 2, 'date': '2026-05-20 12:00:00', 'view_count': 1},
        ]
        diary_details = [
            {'diary': diary, **calculate_raw_weights(diary, fixed_now, 'random')}
            for diary in diaries
        ]

        result = strategy.normalize(diary_details)
        by_id = {item['diary']['id']: item for item in result}

        assert by_id[1]['final_weight'] > by_id[2]['final_weight']
        assert by_id[1]['final_weight'] == pytest.approx(
            by_id[1]['time_weight_norm'] * 0.3
            + by_id[1]['count_weight_norm']
            + 0.5
        )

    # =========================================================================
    # 单调性测试
    # =========================================================================

    def test_lower_use_count_higher_count_weight_norm(self, strategy, sample_diary_base, fixed_now):
        """使用次数越少，count_weight_norm应该越高"""
        diaries = [
            {**sample_diary_base, 'id': 1, 'date': '2026-05-20 12:00:00', 'view_count': 0},
            {**sample_diary_base, 'id': 2, 'date': '2026-05-20 12:00:00', 'view_count': 5},
            {**sample_diary_base, 'id': 3, 'date': '2026-05-20 12:00:00', 'view_count': 10},
        ]

        diary_details = []
        for d in diaries:
            raw = calculate_raw_weights(d, fixed_now, 'random')
            diary_details.append({'diary': d, **raw})

        result = strategy.normalize(diary_details)

        # 按use_count排序后，count_weight_norm应该递减
        sorted_by_count = sorted(result, key=lambda x: x['use_count'])
        for i in range(len(sorted_by_count) - 1):
            assert sorted_by_count[i]['count_weight_norm'] > sorted_by_count[i + 1]['count_weight_norm'], \
                f"Count weight norm should decrease with higher use_count"

    def test_more_days_ago_higher_time_weight_norm(self, strategy, sample_diary_base, fixed_now):
        """距今天数越多，time_weight_norm应该越高"""
        diaries = [
            {**sample_diary_base, 'id': 1, 'date': '2026-05-21 12:00:00', 'view_count': 0},   # 今天
            {**sample_diary_base, 'id': 2, 'date': '2026-05-20 12:00:00', 'view_count': 0},   # 1天前
            {**sample_diary_base, 'id': 3, 'date': '2026-05-15 12:00:00', 'view_count': 0},   # 6天前
        ]

        diary_details = []
        for d in diaries:
            raw = calculate_raw_weights(d, fixed_now, 'random')
            diary_details.append({'diary': d, **raw})

        result = strategy.normalize(diary_details)

        # 按days_ago排序后，time_weight_norm应该递增
        sorted_by_time = sorted(result, key=lambda x: x['days_ago'])
        for i in range(len(sorted_by_time) - 1):
            assert sorted_by_time[i]['time_weight_norm'] < sorted_by_time[i + 1]['time_weight_norm'], \
                f"Time weight norm should increase with more days_ago"

    # =========================================================================
    # 确定性和幂等性测试
    # =========================================================================

    def test_deterministic_result(self, strategy, sample_diaries, fixed_now):
        """相同输入应产生相同输出"""
        diary_details = []
        for diary in sample_diaries:
            raw = calculate_raw_weights(diary, fixed_now, 'random')
            diary_details.append({'diary': diary, **raw})

        result1 = strategy.normalize(diary_details.copy())
        result2 = strategy.normalize(diary_details.copy())

        assert result1 == result2


class TestDeletionSelectionNormalization:
    """测试 DeletionSelectionNormalization 删除选择归一化策略"""

    @pytest.fixture
    def strategy(self):
        return DeletionSelectionNormalization()

    # =========================================================================
    # 边界条件测试
    # =========================================================================

    def test_single_item_returns_half_weight(self, strategy, sample_diary_base, fixed_now):
        """单元素时，final_weight应为0.5"""
        diary = {**sample_diary_base, 'date': '2026-05-20 12:00:00', 'view_count': 10}
        raw_weights = calculate_raw_weights(diary, fixed_now, 'deletion')
        diary_details = [{'diary': diary, **raw_weights}]

        result = strategy.normalize(diary_details)

        assert len(result) == 1
        assert result[0]['final_weight'] == pytest.approx(0.5)
        assert result[0]['time_weight_norm'] == pytest.approx(0.5)
        assert result[0]['view_count_weight_norm'] == pytest.approx(0.5)

    def test_empty_list_returns_empty(self, strategy):
        """空列表应直接返回"""
        result = strategy.normalize([])
        assert result == []

    # =========================================================================
    # 不变量测试
    # =========================================================================

    def test_time_weight_norm_in_range(self, strategy, diary_for_deletion_selection, fixed_now):
        """time_weight_norm应在[0,1]区间内"""
        diary_details = []
        for diary in diary_for_deletion_selection:
            raw = calculate_raw_weights(diary, fixed_now, 'deletion')
            diary_details.append({'diary': diary, **raw})

        result = strategy.normalize(diary_details)

        for item in result:
            assert 0.0 <= item['time_weight_norm'] <= 1.0

    def test_view_count_weight_norm_in_range(self, strategy, diary_for_deletion_selection, fixed_now):
        """view_count_weight_norm应在[0,1]区间内"""
        diary_details = []
        for diary in diary_for_deletion_selection:
            raw = calculate_raw_weights(diary, fixed_now, 'deletion')
            diary_details.append({'diary': diary, **raw})

        result = strategy.normalize(diary_details)

        for item in result:
            assert 0.0 <= item['view_count_weight_norm'] <= 1.0

    def test_final_weight_in_expected_range(self, strategy, diary_for_deletion_selection, fixed_now):
        """final_weight应在合理范围内 (alpha=0.6, beta=0.4)"""
        diary_details = []
        for diary in diary_for_deletion_selection:
            raw = calculate_raw_weights(diary, fixed_now, 'deletion')
            diary_details.append({'diary': diary, **raw})

        result = strategy.normalize(diary_details)

        # min: 0.6*0 + 0.4*0 = 0, max: 0.6*1 + 0.4*1 = 1.0
        for item in result:
            assert 0.0 <= item['final_weight'] <= 1.0

    # =========================================================================
    # 单调性测试
    # =========================================================================

    def test_higher_view_count_higher_weight_norm(self, strategy, sample_diary_base, fixed_now):
        """查看次数越高，view_count_weight_norm应该越高（偏向删除热门）"""
        diaries = [
            {**sample_diary_base, 'id': 1, 'date': '2026-05-20 12:00:00', 'view_count': 0},
            {**sample_diary_base, 'id': 2, 'date': '2026-05-20 12:00:00', 'view_count': 50},
            {**sample_diary_base, 'id': 3, 'date': '2026-05-20 12:00:00', 'view_count': 100},
        ]

        diary_details = []
        for d in diaries:
            raw = calculate_raw_weights(d, fixed_now, 'deletion')
            diary_details.append({'diary': d, **raw})

        result = strategy.normalize(diary_details)

        # 按view_count排序后，view_count_weight_norm应该递增
        sorted_by_views = sorted(result, key=lambda x: x['view_count'])
        for i in range(len(sorted_by_views) - 1):
            assert sorted_by_views[i]['view_count_weight_norm'] < sorted_by_views[i + 1]['view_count_weight_norm']

    def test_more_days_ago_higher_time_weight_norm(self, strategy, sample_diary_base, fixed_now):
        """距今天数越多，time_weight_norm应该越高（偏向删除久远）"""
        diaries = [
            {**sample_diary_base, 'id': 1, 'date': '2026-05-21 12:00:00', 'view_count': 50},  # 今天
            {**sample_diary_base, 'id': 2, 'date': '2026-05-01 12:00:00', 'view_count': 50},  # 20天前
            {**sample_diary_base, 'id': 3, 'date': '2025-01-01 12:00:00', 'view_count': 50},  # 很久以前
        ]

        diary_details = []
        for d in diaries:
            raw = calculate_raw_weights(d, fixed_now, 'deletion')
            diary_details.append({'diary': d, **raw})

        result = strategy.normalize(diary_details)

        # 按days_ago排序后，time_weight_norm应该递增
        sorted_by_time = sorted(result, key=lambda x: x['days_ago'])
        for i in range(len(sorted_by_time) - 1):
            assert sorted_by_time[i]['time_weight_norm'] < sorted_by_time[i + 1]['time_weight_norm']

    # =========================================================================
    # 确定性和幂等性测试
    # =========================================================================

    def test_deterministic_result(self, strategy, diary_for_deletion_selection, fixed_now):
        """相同输入应产生相同输出"""
        diary_details = []
        for diary in diary_for_deletion_selection:
            raw = calculate_raw_weights(diary, fixed_now, 'deletion')
            diary_details.append({'diary': diary, **raw})

        result1 = strategy.normalize(diary_details.copy())
        result2 = strategy.normalize(diary_details.copy())

        assert result1 == result2
