"""
pytest配置和共享fixtures
提供测试所需的公共mock对象、fixture和数据生成器
"""
import sys
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any
from unittest.mock import MagicMock

import pytest

# 将项目根目录添加到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(scope="session")
def qapp():
    """提供 Qt 应用实例，供需要 QWidget 的测试复用"""
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


# =============================================================================
# 日期时间相关 Fixtures
# =============================================================================

@pytest.fixture
def fixed_now():
    """固定当前时间，避免时间相关测试的不确定性"""
    return datetime(2026, 5, 21, 12, 0, 0)


@pytest.fixture
def sample_diary_base():
    """基础日记数据，不包含时间相关字段"""
    return {
        'id': 1,
        'content': '这是一篇测试日记',
        'view_count': 0,
    }


def make_diary(id: int, days_ago: int, view_count: int, date_format: str = "%Y-%m-%d %H:%M:%S") -> Dict[str, Any]:
    """
    创建测试用日记数据

    Args:
        id: 日记ID
        days_ago: 距今天数（0=今天）
        view_count: 查看次数
        date_format: 日期格式
    """
    diary_date = datetime.now() - timedelta(days=days_ago)
    return {
        'id': id,
        'date': diary_date.strftime(date_format),
        'content': f'日记内容 {id}',
        'view_count': view_count,
    }


@pytest.fixture
def sample_diaries() -> List[Dict[str, Any]]:
    """预设的测试日记列表，包含不同日期和查看次数

    注意：使用较大的days_ago值确保日期总是过去的时间
    """
    return [
        make_diary(1, days_ago=1, view_count=10),    # 1天前
        make_diary(2, days_ago=7, view_count=5),     # 7天前
        make_diary(3, days_ago=30, view_count=2),    # 30天前
        make_diary(4, days_ago=100, view_count=0),   # 100天前
        make_diary(5, days_ago=365, view_count=100), # 1年前
    ]


@pytest.fixture
def diary_single() -> Dict[str, Any]:
    """单篇日记（用于边界测试）"""
    return make_diary(1, days_ago=10, view_count=5)


@pytest.fixture
def diaries_same_date() -> List[Dict[str, Any]]:
    """多篇同日期日记（用于归一化边界测试）"""
    same_date = datetime(2026, 1, 1, 10, 0, 0).strftime("%Y-%m-%d %H:%M:%S")
    return [
        {'id': 1, 'date': same_date, 'content': 'A', 'view_count': 0},
        {'id': 2, 'date': same_date, 'content': 'B', 'view_count': 5},
        {'id': 3, 'date': same_date, 'content': 'C', 'view_count': 10},
    ]


@pytest.fixture
def diaries_same_view_count() -> List[Dict[str, Any]]:
    """多篇相同查看次数的日记"""
    return [
        make_diary(1, days_ago=1, view_count=5),
        make_diary(2, days_ago=7, view_count=5),
        make_diary(3, days_ago=30, view_count=5),
    ]


# =============================================================================
# Mock数据库管理器 Fixtures
# =============================================================================

@pytest.fixture
def mock_db_manager():
    """
    创建Mock数据库管理器，用于Service层测试
    实现_execute方法，返回可配置的预设值
    """
    mock = MagicMock()
    mock._execute = MagicMock()
    return mock


@pytest.fixture
def mock_db_manager_with_stats(mock_db_manager):
    """预配置了统计查询返回值的Mock数据库管理器"""
    mock_db_manager._execute.side_effect = [
        # get_statistics() 的第一次查询
        {'total': 10, 'total_views': 100, 'avg_views': 10.0, 'max_views': 50, 'min_views': 1},
        # get_statistics() 获取most_viewed
        {'id': 1, 'date': '2026-01-01', 'content': 'Most viewed', 'view_count': 50},
        # get_statistics() 获取least_viewed
        {'id': 2, 'date': '2026-05-01', 'content': 'Least viewed', 'view_count': 1},
    ]
    return mock_db_manager


@pytest.fixture
def mock_db_manager_empty(mock_db_manager):
    """预配置了空结果的Mock数据库管理器"""
    mock_db_manager._execute.return_value = None
    return mock_db_manager


# =============================================================================
# 权重计算相关 Fixtures
# =============================================================================

@pytest.fixture
def diary_for_random_selection() -> List[Dict[str, Any]]:
    """用于随机选择场景的测试数据"""
    return [
        make_diary(1, days_ago=1, view_count=100),   # 高使用次数
        make_diary(2, days_ago=7, view_count=10),    # 中等使用次数
        make_diary(3, days_ago=30, view_count=1),    # 低使用次数
        make_diary(4, days_ago=365, view_count=0),   # 零使用次数
    ]


@pytest.fixture
def diary_for_deletion_selection() -> List[Dict[str, Any]]:
    """用于删除选择场景的测试数据"""
    return [
        make_diary(1, days_ago=1, view_count=100),   # 近期高热度
        make_diary(2, days_ago=365, view_count=50),  # 久远高热度
        make_diary(3, days_ago=730, view_count=0),   # 久远零热度
    ]


# =============================================================================
# 数据库 Fixtures（集成测试用）
# =============================================================================

@pytest.fixture
def temp_db_path(tmp_path):
    """创建临时数据库文件路径"""
    return str(tmp_path / "test_diary.db")


@pytest.fixture
def initialized_temp_db(temp_db_path):
    """
    创建并初始化临时数据库，包含完整的表结构
    用于集成测试
    """
    import sqlite3
    from models.enhanced_database import EnhancedDatabaseManager

    # 创建临时数据库管理器
    db = EnhancedDatabaseManager(temp_db_path)

    yield db

    # 清理
    db.close()


# =============================================================================
# Hypothesis相关配置
# =============================================================================

def given_diary_details_strategy():
    """
    返回用于生成diary_details的Hypothesis策略
    用于Property-based testing
    """
    from hypothesis import given, strategies as st

    return st.lists(
        st.fixed_dictionaries({
            'diary': st.fixed_dictionaries({
                'id': st.integers(min_value=1, max_value=1000),
                'date': st.text(min_size=19, max_size=19),  # YYYY-MM-DD HH:MM:SS
                'content': st.text(min_size=0, max_size=1000),
                'view_count': st.integers(min_value=0, max_value=10000),
            }),
            'time_weight_raw': st.floats(min_value=0, max_value=10),
            'use_count': st.integers(min_value=0, max_value=10000),
        }),
        min_size=0,
        max_size=100
    )


def given_diary_details_deletion_strategy():
    """
    返回用于删除场景diary_details的Hypothesis策略
    """
    from hypothesis import given, strategies as st

    return st.lists(
        st.fixed_dictionaries({
            'diary': st.fixed_dictionaries({
                'id': st.integers(min_value=1, max_value=1000),
                'date': st.text(min_size=19, max_size=19),
                'content': st.text(min_size=0, max_size=1000),
                'view_count': st.integers(min_value=0, max_value=10000),
            }),
            'time_weight_raw': st.floats(min_value=0, max_value=10),
            'view_count': st.integers(min_value=0, max_value=10000),
        }),
        min_size=0,
        max_size=100
    )
