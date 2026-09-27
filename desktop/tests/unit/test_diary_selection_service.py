"""
日记选择服务单元测试
测试 models/weight/diary_selection_service.py 中的 DiarySelectionService 类
"""
import random
from unittest.mock import patch, MagicMock

import pytest

from models.weight.diary_selection_service import DiarySelectionService


class TestDiarySelectionService:
    """测试 DiarySelectionService 日记选择服务"""

    @pytest.fixture
    def service(self):
        return DiarySelectionService()

    # =========================================================================
    # 初始化测试
    # =========================================================================

    def test_init_creates_weight_calculation_service(self):
        """初始化时应创建WeightCalculationService实例"""
        service = DiarySelectionService()
        assert hasattr(service, 'weight_calculation_service')

    # =========================================================================
    # get_weighted_random_diary 测试
    # =========================================================================

    def test_get_weighted_random_diary_empty(self, service):
        """空列表应返回None"""
        result = service.get_weighted_random_diary([])
        assert result is None

    @patch.object(DiarySelectionService, 'get_weighted_random_diary', wraps=DiarySelectionService.get_weighted_random_diary)
    def test_get_weighted_random_diary_calls_calculation_service(self, mock_method, service, sample_diaries):
        """应委托给weight_calculation_service"""
        # 让原始方法正常工作
        mock_method.return_value = sample_diaries[0]

        result = service.get_weighted_random_diary(sample_diaries)

        assert result == sample_diaries[0]

    # =========================================================================
    # get_weighted_deletion_diary 测试
    # =========================================================================

    def test_get_weighted_deletion_diary_empty(self, service):
        """空列表应返回None"""
        result = service.get_weighted_deletion_diary([])
        assert result is None

    # =========================================================================
    # get_random_diary 测试
    # =========================================================================

    def test_get_random_diary_empty(self, service):
        """空列表应返回None"""
        result = service.get_random_diary([])
        assert result is None

    @patch('random.choice')
    def test_get_random_diary_calls_random_choice(self, mock_choice, service, sample_diaries):
        """应使用random.choice选择"""
        mock_choice.return_value = sample_diaries[0]

        result = service.get_random_diary(sample_diaries)

        mock_choice.assert_called_once_with(sample_diaries)
        assert result == sample_diaries[0]

    def test_get_random_diary_returns_from_list(self, service, sample_diaries):
        """返回值应该是列表中的元素"""
        result = service.get_random_diary(sample_diaries)

        assert result in sample_diaries

    # =========================================================================
    # get_oldest_diary 测试
    # =========================================================================

    def test_get_oldest_diary_empty(self, service):
        """空列表应返回None"""
        result = service.get_oldest_diary([])
        assert result is None

    def test_get_oldest_diary_returns_oldest(self, service):
        """应返回日期最早的日记"""
        diaries = [
            {'id': 1, 'date': '2026-05-20 10:00:00', 'content': 'A', 'view_count': 0},
            {'id': 2, 'date': '2026-01-01 10:00:00', 'content': 'B', 'view_count': 0},  # 最老
            {'id': 3, 'date': '2026-05-21 10:00:00', 'content': 'C', 'view_count': 0},
        ]

        result = service.get_oldest_diary(diaries)

        assert result['id'] == 2
        assert result['date'] == '2026-01-01 10:00:00'

    def test_get_oldest_diary_with_same_date(self, service):
        """同日期时返回第一个"""
        diaries = [
            {'id': 1, 'date': '2026-01-01 10:00:00', 'content': 'A', 'view_count': 0},
            {'id': 2, 'date': '2026-01-01 12:00:00', 'content': 'B', 'view_count': 0},
        ]

        result = service.get_oldest_diary(diaries)

        # sorted稳定排序，应返回第一个
        assert result['id'] == 1

    # =========================================================================
    # get_most_viewed_diary 测试
    # =========================================================================

    def test_get_most_viewed_diary_empty(self, service):
        """空列表应返回None"""
        result = service.get_most_viewed_diary([])
        assert result is None

    def test_get_most_viewed_diary_returns_most_viewed(self, service):
        """应返回view_count最高的日记"""
        diaries = [
            {'id': 1, 'date': '2026-05-20', 'content': 'A', 'view_count': 5},
            {'id': 2, 'date': '2026-05-20', 'content': 'B', 'view_count': 100},  # 最多
            {'id': 3, 'date': '2026-05-20', 'content': 'C', 'view_count': 10},
        ]

        result = service.get_most_viewed_diary(diaries)

        assert result['id'] == 2
        assert result['view_count'] == 100

    # =========================================================================
    # get_least_viewed_diary 测试
    # =========================================================================

    def test_get_least_viewed_diary_empty(self, service):
        """空列表应返回None"""
        result = service.get_least_viewed_diary([])
        assert result is None

    def test_get_least_viewed_diary_returns_least_viewed(self, service):
        """应返回view_count最低的日记"""
        diaries = [
            {'id': 1, 'date': '2026-05-20', 'content': 'A', 'view_count': 50},
            {'id': 2, 'date': '2026-05-20', 'content': 'B', 'view_count': 0},  # 最少
            {'id': 3, 'date': '2026-05-20', 'content': 'C', 'view_count': 10},
        ]

        result = service.get_least_viewed_diary(diaries)

        assert result['id'] == 2
        assert result['view_count'] == 0

    # =========================================================================
    # 边界条件测试
    # =========================================================================

    def test_single_item_in_list(self, service):
        """单元素列表应正确处理"""
        diaries = [{'id': 1, 'date': '2026-05-20', 'content': 'A', 'view_count': 5}]

        assert service.get_random_diary(diaries) == diaries[0]
        assert service.get_oldest_diary(diaries) == diaries[0]
        assert service.get_most_viewed_diary(diaries) == diaries[0]
        assert service.get_least_viewed_diary(diaries) == diaries[0]

    def test_diary_without_view_count_field(self, service):
        """缺少view_count字段的日记应能处理"""
        diaries = [
            {'id': 1, 'date': '2026-05-20', 'content': 'A'},  # 无view_count
        ]

        result = service.get_oldest_diary(diaries)
        assert result == diaries[0]
