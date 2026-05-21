"""
权重计算服务单元测试
测试 models/weight/calculation_service.py 中的 WeightCalculationService 类
"""
import random
from unittest.mock import patch, MagicMock

import pytest

from models.weight.calculation_service import (
    WeightCalculationService,
    DatabaseManagerInterface,
)
from models.calculations.weight_calculation_core import calculate_raw_weights


class TestWeightCalculationService:
    """测试 WeightCalculationService 权重计算服务"""

    @pytest.fixture
    def service(self):
        return WeightCalculationService()

    # =========================================================================
    # calculate_selection_weights 测试
    # =========================================================================

    def test_calculate_selection_weights_empty_list(self, service):
        """空列表应返回空列表"""
        result = service.calculate_selection_weights([], 'random')
        assert result == []

    def test_calculate_selection_weights_returns_tuples(self, service, sample_diaries, fixed_now):
        """返回值应为 (diary, weight) 元组列表"""
        result = service.calculate_selection_weights(sample_diaries, 'random')

        assert isinstance(result, list)
        assert all(isinstance(item, tuple) and len(item) == 2 for item in result)
        assert all(isinstance(item[0], dict) and isinstance(item[1], float) for item in result)

    def test_calculate_selection_weights_random_mode(self, service, diary_for_random_selection, fixed_now):
        """random模式返回的权重列表长度应与输入相同"""
        result = service.calculate_selection_weights(diary_for_random_selection, 'random')

        assert len(result) == len(diary_for_random_selection)
        # 验证每项都包含final_weight
        for diary, weight in result:
            assert weight >= 0

    def test_calculate_selection_weights_deletion_mode(self, service, diary_for_deletion_selection):
        """deletion模式返回的权重列表长度应与输入相同"""
        result = service.calculate_selection_weights(diary_for_deletion_selection, 'deletion')

        assert len(result) == len(diary_for_deletion_selection)
        for diary, weight in result:
            assert weight >= 0

    def test_calculate_selection_weights_preserves_diary_data(self, service, sample_diaries):
        """返回的diary应保留原始数据"""
        result = service.calculate_selection_weights(sample_diaries, 'random')

        for i, (diary, weight) in enumerate(result):
            assert diary['id'] == sample_diaries[i]['id']
            assert diary['content'] == sample_diaries[i]['content']

    # =========================================================================
    # select_by_weight 测试
    # =========================================================================

    def test_select_by_weight_empty_list(self, service):
        """空列表应返回None"""
        result = service.select_by_weight([])
        assert result is None

    def test_select_by_weight_single_item(self, service, sample_diary_base):
        """单元素列表应返回该元素"""
        weighted = [(sample_diary_base, 1.0)]
        result = service.select_by_weight(weighted)
        assert result == sample_diary_base

    def test_select_by_weight_returns_diary(self, service, sample_diaries):
        """应返回一个diary"""
        weighted = [(d, 1.0) for d in sample_diaries]
        result = service.select_by_weight(weighted)
        assert isinstance(result, dict)
        assert 'id' in result

    @patch('random.choices')
    def test_select_by_weight_uses_weights(self, mock_choices, service, sample_diaries):
        """验证使用加权随机选择"""
        # 设置mock使random.choices返回第一个元素
        mock_choices.return_value = [sample_diaries[0]]

        weighted = [(d, 1.0) for d in sample_diaries]
        result = service.select_by_weight(weighted)

        mock_choices.assert_called_once()
        # 验证传入的权重参数
        call_args = mock_choices.call_args
        assert call_args.kwargs['weights'] == [1.0] * len(sample_diaries)

    @patch('random.choices')
    @patch('random.choice')
    def test_select_by_weight_fallback_to_random_choice(self, mock_choice, mock_choices, service, sample_diaries):
        """当权重和为0时应退回到random.choice"""
        # 设置权重和为0的情况
        weighted = [(d, 0.0) for d in sample_diaries]
        mock_choice.return_value = sample_diaries[0]

        result = service.select_by_weight(weighted)

        mock_choice.assert_called_once()
        mock_choices.assert_not_called()

    # =========================================================================
    # get_weighted_random_diary_from_data 测试
    # =========================================================================

    def test_get_weighted_random_diary_empty(self, service):
        """空列表应返回None"""
        result = service.get_weighted_random_diary_from_data([])
        assert result is None

    @patch.object(WeightCalculationService, 'select_by_weight')
    def test_get_weighted_random_diary_calls_correct_sequence(self, mock_select, service, sample_diaries):
        """验证调用流程：calculate_selection_weights -> select_by_weight"""
        mock_select.return_value = sample_diaries[0]

        result = service.get_weighted_random_diary_from_data(sample_diaries)

        # 验证返回的是select_by_weight的结果
        assert result == sample_diaries[0]
        mock_select.assert_called_once()

    # =========================================================================
    # get_weighted_deletion_diary_from_data 测试
    # =========================================================================

    def test_get_weighted_deletion_diary_empty(self, service):
        """空列表应返回None"""
        result = service.get_weighted_deletion_diary_from_data([])
        assert result is None

    @patch.object(WeightCalculationService, 'select_by_weight')
    def test_get_weighted_deletion_diary_calls_correct_sequence(self, mock_select, service, sample_diaries):
        """验证删除模式调用流程"""
        mock_select.return_value = sample_diaries[0]

        result = service.get_weighted_deletion_diary_from_data(sample_diaries)

        assert result == sample_diaries[0]
        mock_select.assert_called_once()

    # =========================================================================
    # get_weighted_random_diary_with_db_interface 测试
    # =========================================================================

    def test_get_weighted_random_diary_with_db_interface_no_limit(self):
        """无limit参数时应调用get_all_diaries"""
        service = WeightCalculationService()
        mock_db = MagicMock(spec=DatabaseManagerInterface)
        mock_db.get_all_diaries.return_value = [
            {'id': 1, 'date': '2026-05-20 12:00:00', 'content': 'A', 'view_count': 5}
        ]

        result = service.get_weighted_random_diary_with_db_interface(mock_db, limit=None)

        mock_db.get_all_diaries.assert_called_once()
        mock_db.get_diaries_with_limit.assert_not_called()

    def test_get_weighted_random_diary_with_db_interface_with_limit(self):
        """有limit参数时应调用get_diaries_with_limit"""
        service = WeightCalculationService()
        mock_db = MagicMock(spec=DatabaseManagerInterface)
        mock_db.get_diaries_with_limit.return_value = [
            {'id': 1, 'date': '2026-05-20 12:00:00', 'content': 'A', 'view_count': 5}
        ]

        result = service.get_weighted_random_diary_with_db_interface(mock_db, limit=10)

        mock_db.get_diaries_with_limit.assert_called_once_with(10)
        mock_db.get_all_diaries.assert_not_called()

    def test_get_weighted_random_diary_with_db_interface_empty(self):
        """数据库返回空列表时应返回None"""
        service = WeightCalculationService()
        mock_db = MagicMock(spec=DatabaseManagerInterface)
        mock_db.get_all_diaries.return_value = []

        result = service.get_weighted_random_diary_with_db_interface(mock_db)

        assert result is None

    # =========================================================================
    # 权重分布测试
    # =========================================================================

    def test_weights_sum_to_positive(self, service, diary_for_random_selection):
        """权重和应为正数"""
        result = service.calculate_selection_weights(diary_for_random_selection, 'random')

        weights = [w for _, w in result]
        total = sum(weights)

        assert total > 0, "Sum of weights should be positive"

    def test_all_weights_positive(self, service, diary_for_random_selection):
        """所有权重应为正数"""
        result = service.calculate_selection_weights(diary_for_random_selection, 'random')

        for _, weight in result:
            assert weight >= 0, f"Weight {weight} should be non-negative"


class TestDatabaseManagerInterface:
    """测试 DatabaseManagerInterface 协议"""

    def test_interface_has_required_methods(self):
        """接口应定义必要的方法"""
        # Protocol不能直接实例化，但可以检查方法存在
        assert hasattr(DatabaseManagerInterface, 'get_all_diaries')
        assert hasattr(DatabaseManagerInterface, 'get_diaries_with_limit')
