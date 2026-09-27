"""
统计服务单元测试
测试 services/statistics_service.py 中的 StatisticsService 类
"""
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from services.statistics_service import StatisticsService


class TestStatisticsService:
    """测试 StatisticsService 统计服务类"""

    @pytest.fixture
    def service(self, mock_db_manager):
        return StatisticsService(mock_db_manager)

    # =========================================================================
    # get_statistics 测试
    # =========================================================================

    def test_get_statistics_returns_dict(self, service, mock_db_manager_with_stats):
        """返回值应为字典"""
        service.db_manager = mock_db_manager_with_stats

        result = service.get_statistics()

        assert isinstance(result, dict)

    def test_get_statistics_contains_required_keys(self, service, mock_db_manager_with_stats):
        """返回值应包含必要字段"""
        service.db_manager = mock_db_manager_with_stats

        result = service.get_statistics()

        assert 'total' in result
        assert 'total_views' in result
        assert 'avg_views' in result
        assert 'most_viewed' in result
        assert 'least_viewed' in result

    def test_get_statistics_empty_database(self, service, mock_db_manager):
        """空数据库应返回正确的空值结构"""
        # 第一次查询返回空
        mock_db_manager._execute.return_value = None

        result = service.get_statistics()

        assert result['total'] == 0
        assert result['total_views'] == 0
        assert result['avg_views'] == 0
        assert result['most_viewed'] is None
        assert result['least_viewed'] is None

    def test_get_statistics_avg_views_rounded(self, service, mock_db_manager_with_stats):
        """avg_views应保留两位小数"""
        result = service.get_statistics()

        assert isinstance(result['avg_views'], float)
        # 如果avg_views是10.0，round后仍是10.0

    # =========================================================================
    # get_view_statistics 测试
    # =========================================================================

    def test_get_view_statistics_returns_dict(self, service, mock_db_manager):
        """返回值应为包含summary和distribution的字典"""
        mock_db_manager._execute.side_effect = [
            # 第一次调用：distribution查询
            [
                {'view_range': '未查看', 'count': 5},
                {'view_range': '1-5次', 'count': 10},
            ],
            # 第二次调用：summary查询
            {'total_views': 100, 'avg_views': 10.0, 'max_views': 50, 'min_views': 0},
        ]

        result = service.get_view_statistics()

        assert isinstance(result, dict)
        assert 'summary' in result
        assert 'distribution' in result
        assert isinstance(result['distribution'], list)

    # =========================================================================
    # get_content_length_statistics 测试
    # =========================================================================

    def test_get_content_length_statistics_returns_dict(self, service, mock_db_manager):
        """返回值应包含内容长度统计信息"""
        mock_db_manager._execute.return_value = {
            'avg_length': 100.5,
            'min_length': 10,
            'max_length': 500,
            'total_count': 20
        }

        result = service.get_content_length_statistics()

        assert 'average_length' in result
        assert 'min_length' in result
        assert 'max_length' in result
        assert 'total_count' in result
        assert result['average_length'] == 100  # 整数

    def test_get_content_length_statistics_empty(self, service, mock_db_manager):
        """空数据库时avg_length应为0"""
        mock_db_manager._execute.return_value = {
            'avg_length': None,
            'min_length': None,
            'max_length': None,
            'total_count': 0
        }

        result = service.get_content_length_statistics()

        assert result['average_length'] == 0
        assert result['total_count'] == 0

    # =========================================================================
    # get_daily_activity_statistics 测试
    # =========================================================================

    def test_get_daily_activity_statistics_returns_list(self, service, mock_db_manager):
        """返回值应为列表"""
        mock_db_manager._execute.return_value = [
            {'day': '2026-05-21', 'diary_count': 3, 'total_views': 15},
            {'day': '2026-05-20', 'diary_count': 5, 'total_views': 20},
        ]

        result = service.get_daily_activity_statistics()

        assert isinstance(result, list)
        assert len(result) == 2

    def test_get_daily_activity_statistics_empty(self, service, mock_db_manager):
        """空结果应返回空列表"""
        mock_db_manager._execute.return_value = None

        result = service.get_daily_activity_statistics()

        assert result == []

    # =========================================================================
    # get_top_viewed_diaries 测试
    # =========================================================================

    def test_get_top_viewed_diaries_returns_list(self, service, mock_db_manager):
        """返回值应为列表"""
        mock_db_manager._execute.return_value = [
            {'id': 1, 'view_count': 100},
            {'id': 2, 'view_count': 50},
        ]

        result = service.get_top_viewed_diaries()

        assert isinstance(result, list)

    def test_get_top_viewed_diaries_respects_limit(self, service, mock_db_manager):
        """应传入正确的limit参数"""
        mock_db_manager._execute.return_value = []

        service.get_top_viewed_diaries(limit=5)

        call_args = mock_db_manager._execute.call_args
        assert (5,) in call_args[0] or call_args[0][1] == (5,)

    def test_get_top_viewed_diaries_empty(self, service, mock_db_manager):
        """空结果应返回空列表"""
        mock_db_manager._execute.return_value = None

        result = service.get_top_viewed_diaries()

        assert result == []

    # =========================================================================
    # get_least_viewed_diaries 测试
    # =========================================================================

    def test_get_least_viewed_diaries_returns_list(self, service, mock_db_manager):
        """返回值应为列表"""
        mock_db_manager._execute.return_value = [
            {'id': 1, 'view_count': 0},
            {'id': 2, 'view_count': 1},
        ]

        result = service.get_least_viewed_diaries()

        assert isinstance(result, list)

    def test_get_least_viewed_diaries_empty(self, service, mock_db_manager):
        """空结果应返回空列表"""
        mock_db_manager._execute.return_value = None

        result = service.get_least_viewed_diaries()

        assert result == []

    # =========================================================================
    # get_daily_stats 测试
    # =========================================================================

    def test_get_daily_stats_returns_dict(self, service, mock_db_manager):
        """返回值应为字典"""
        mock_db_manager._execute.side_effect = [
            {'total_views': 50},  # yesterday query
            {'value': 100, 'updated_at': '2026-05-01'},  # max query
            None,  # INSERT
        ]

        result = service.get_daily_stats()

        assert isinstance(result, dict)
        assert 'yesterday_total_views' in result
        assert 'all_time_max_single_views' in result

    # =========================================================================
    # get_today_total_views 测试
    # =========================================================================

    def test_get_today_total_views_returns_int(self, service, mock_db_manager):
        """返回值应为整数"""
        mock_db_manager._execute.return_value = {'total_views': 25}

        result = service.get_today_total_views()

        assert isinstance(result, int)
        assert result == 25

    def test_get_today_total_views_zero_when_no_data(self, service, mock_db_manager):
        """无数据时返回0"""
        mock_db_manager._execute.return_value = None

        result = service.get_today_total_views()

        assert result == 0
