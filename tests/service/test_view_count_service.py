"""
查看次数服务单元测试
测试 services/view_count_service.py 中的 ViewCountService 类
"""
from contextlib import contextmanager
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from services.view_count_service import ViewCountService


class TestViewCountService:
    """测试 ViewCountService 查看次数服务类"""

    @pytest.fixture
    def service(self, mock_db_manager):
        return ViewCountService(mock_db_manager)

    # =========================================================================
    # increment_view_count 测试
    # =========================================================================
    #
    # 新实现把 view_log / view_count / all_time_max 压到同一 _transaction 内
    # 因此 mock 的是 cursor.execute 的副作用，而不是 db_manager._execute

    @staticmethod
    def _make_mock_cursor(side_effects):
        """构造一个 mock cursor，cursor.execute 依次返回 side_effects 里的值"""
        cursor = MagicMock()
        cursor.fetchone = MagicMock(side_effect=side_effects)
        cursor.execute = MagicMock()
        return cursor

    def test_increment_view_count_returns_new_count(self, service, mock_db_manager):
        """返回值应为新的查看次数"""
        # fetchone 顺序: (1) UPDATE RETURNING, (2) SELECT COUNT today, (3) SELECT value max
        cursor = self._make_mock_cursor([
            {'view_count': 6},  # UPDATE ... RETURNING
            {'count': 5},       # SELECT COUNT(*) today
            {'value': 3},       # SELECT value FROM app_config
        ])

        @contextmanager
        def fake_transaction():
            yield cursor
        mock_db_manager._transaction = fake_transaction

        result = service.increment_view_count(1)
        assert result == 6

    def test_increment_view_count_updates_max_if_exceeded(self, service, mock_db_manager):
        """当日查看数超过历史最佳时应更新"""
        # 5 > 3 -> 触发 app_config 更新
        cursor = self._make_mock_cursor([
            {'view_count': 6},
            {'count': 10},
            {'value': 3},
        ])

        @contextmanager
        def fake_transaction():
            yield cursor
        mock_db_manager._transaction = fake_transaction

        service.increment_view_count(1)

        executed_sql = [str(c) for c in cursor.execute.call_args_list]
        assert any('app_config' in s for s in executed_sql), \
            f"应当执行 app_config 更新，实际调用：{executed_sql}"

    def test_increment_view_count_does_not_update_max_if_not_exceeded(self, service, mock_db_manager):
        """当日查看数未超过历史最佳时不应更新"""
        # 2 <= 3 -> 不应执行 INSERT OR REPLACE
        cursor = self._make_mock_cursor([
            {'view_count': 6},
            {'count': 2},
            {'value': 3},
        ])

        @contextmanager
        def fake_transaction():
            yield cursor
        mock_db_manager._transaction = fake_transaction

        service.increment_view_count(1)

        executed_sql = [str(c) for c in cursor.execute.call_args_list]
        assert not any('INSERT OR REPLACE' in s for s in executed_sql), \
            f"不应更新 app_config，实际调用：{executed_sql}"

    # =========================================================================
    # decrease_view_count 测试
    # =========================================================================

    def test_decrease_view_count_success(self, service, mock_db_manager):
        """成功减少查看次数应返回True"""
        mock_db_manager._execute.return_value = 1  # rowcount

        result = service.decrease_view_count(1, 1)

        assert result is True

    def test_decrease_view_count_failure(self, service, mock_db_manager):
        """无法减少查看次数应返回False"""
        mock_db_manager._execute.return_value = 0  # rowcount

        result = service.decrease_view_count(999, 1)  # 不存在的ID

        assert result is False

    def test_decrease_view_count_with_penalty(self, service, mock_db_manager):
        """应传入正确的penalty值"""
        mock_db_manager._execute.return_value = 1

        service.decrease_view_count(1, 5)

        call_args = mock_db_manager._execute.call_args
        assert 5 in call_args[0][1]  # penalty参数

    # =========================================================================
    # reset_view_count 测试
    # =========================================================================

    def test_reset_view_count_success(self, service, mock_db_manager):
        """成功重置应返回True"""
        mock_db_manager._execute.return_value = 1

        result = service.reset_view_count(1)

        assert result is True

    def test_reset_view_count_failure(self, service, mock_db_manager):
        """无法重置应返回False"""
        mock_db_manager._execute.return_value = 0

        result = service.reset_view_count(999)

        assert result is False

    # =========================================================================
    # batch_increment_view_counts 测试
    # =========================================================================

    def test_batch_increment_returns_rowcount(self, service, mock_db_manager):
        """返回值应为成功更新的记录数"""
        mock_db_manager._execute.return_value = 5

        result = service.batch_increment_view_counts([1, 2, 3, 4, 5])

        assert result == 5

    def test_batch_increment_empty_list(self, service, mock_db_manager):
        """空列表应返回0"""
        result = service.batch_increment_view_counts([])

        assert result == 0
        mock_db_manager._execute.assert_not_called()

    def test_batch_increment_builds_correct_query(self, service, mock_db_manager):
        """应构建正确的批量更新查询"""
        mock_db_manager._execute.return_value = 2

        service.batch_increment_view_counts([1, 2])

        call_args = mock_db_manager._execute.call_args
        query = call_args[0][0]
        params = call_args[0][1]

        assert 'UPDATE diaries SET view_count = view_count + 1 WHERE id IN' in query
        assert len(params) == 2

    # =========================================================================
    # get_total_view_count 测试
    # =========================================================================

    def test_get_total_view_count_returns_int(self, service, mock_db_manager):
        """返回值应为整数"""
        mock_db_manager._execute.return_value = {'total_views': 1000}

        result = service.get_total_view_count()

        assert isinstance(result, int)
        assert result == 1000

    def test_get_total_view_count_null_returns_zero(self, service, mock_db_manager):
        """数据库NULL值应返回0"""
        mock_db_manager._execute.return_value = {'total_views': None}

        result = service.get_total_view_count()

        assert result == 0

    # =========================================================================
    # get_highest_view_count 测试
    # =========================================================================

    def test_get_highest_view_count_returns_diary(self, service, mock_db_manager):
        """返回值应为日记字典"""
        mock_db_manager._execute.return_value = {
            'id': 1, 'view_count': 100, 'content': 'Test'
        }

        result = service.get_highest_view_count()

        assert isinstance(result, dict)
        assert result['view_count'] == 100

    def test_get_highest_view_count_none_when_empty(self, service, mock_db_manager):
        """空数据库应返回None"""
        mock_db_manager._execute.return_value = None

        result = service.get_highest_view_count()

        assert result is None

    # =========================================================================
    # get_lowest_view_count 测试
    # =========================================================================

    def test_get_lowest_view_count_returns_diary(self, service, mock_db_manager):
        """返回值应为日记字典"""
        mock_db_manager._execute.return_value = {
            'id': 1, 'view_count': 0, 'content': 'Test'
        }

        result = service.get_lowest_view_count()

        assert isinstance(result, dict)
        assert result['view_count'] == 0

    # =========================================================================
    # get_average_view_count 测试
    # =========================================================================

    def test_get_average_view_count_returns_float(self, service, mock_db_manager):
        """返回值应为浮点数"""
        mock_db_manager._execute.return_value = {'avg_views': 5.5}

        result = service.get_average_view_count()

        assert isinstance(result, float)
        assert result == 5.5

    def test_get_average_view_count_null_returns_zero(self, service, mock_db_manager):
        """NULL值应返回0.0"""
        mock_db_manager._execute.return_value = {'avg_views': None}

        result = service.get_average_view_count()

        assert result == 0.0

    # =========================================================================
    # get_diaries_by_view_range 测试
    # =========================================================================

    def test_get_diaries_by_view_range_returns_list(self, service, mock_db_manager):
        """返回值应为列表"""
        mock_db_manager._execute.return_value = [
            {'id': 1, 'view_count': 5},
            {'id': 2, 'view_count': 10},
        ]

        result = service.get_diaries_by_view_range(5, 10)

        assert isinstance(result, list)
        assert len(result) == 2

    def test_get_diaries_by_view_range_empty(self, service, mock_db_manager):
        """无结果应返回空列表"""
        mock_db_manager._execute.return_value = None

        result = service.get_diaries_by_view_range(100, 200)

        assert result == []

    # =========================================================================
    # cleanup_old_view_logs 测试
    # =========================================================================

    def test_cleanup_old_view_logs_returns_rowcount(self, service, mock_db_manager):
        """返回值应为删除的记录数"""
        mock_db_manager._execute.return_value = 10

        result = service.cleanup_old_view_logs()

        assert result == 10

    def test_cleanup_old_view_logs_zero_when_none(self, service, mock_db_manager):
        """rowcount为0时应返回0（cursor.rowcount返回0，不是None）"""
        mock_db_manager._execute.return_value = 0

        result = service.cleanup_old_view_logs()

        assert result == 0
