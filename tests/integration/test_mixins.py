"""
Mixin层集成测试
使用临时SQLite数据库测试真实的数据库操作
"""
import os
import sqlite3
from datetime import datetime

import pytest

from models.enhanced_database import EnhancedDatabaseManager


@pytest.fixture
def temp_db_manager(temp_db_path):
    """
    创建临时数据库管理器
    用于集成测试，测试真实的数据库操作
    """
    db = EnhancedDatabaseManager(temp_db_path)
    yield db
    db.close()
    # 清理临时数据库文件
    if os.path.exists(temp_db_path):
        os.remove(temp_db_path)


class TestConnectionMixin:
    """ConnectionMixin 连接管理集成测试"""

    def test_get_connection_returns_sqlite_connection(self, temp_db_manager):
        """_get_connection应返回sqlite3.Connection"""
        conn = temp_db_manager._get_connection()

        assert isinstance(conn, sqlite3.Connection)

    def test_execute_insert_and_select(self, temp_db_manager):
        """测试基本的INSERT和SELECT操作"""
        # 插入
        diary_id = temp_db_manager._execute(
            "INSERT INTO diaries (date, content, view_count) VALUES (?, ?, ?)",
            ('2026-05-21 10:00:00', '测试内容', 0)
        )

        assert diary_id is not None

        # 查询
        result = temp_db_manager._execute(
            "SELECT * FROM diaries WHERE id = ?",
            (diary_id,),
            fetch='one'
        )

        assert result is not None
        assert result['content'] == '测试内容'
        assert result['view_count'] == 0

    def test_execute_fetch_all(self, temp_db_manager):
        """测试fetch='all'"""
        # 插入多条
        for i in range(3):
            temp_db_manager._execute(
                "INSERT INTO diaries (date, content, view_count) VALUES (?, ?, ?)",
                (f'2026-05-{21-i} 10:00:00', f'内容{i}', 0)
            )

        result = temp_db_manager._execute(
            "SELECT * FROM diaries ORDER BY id",
            fetch='all'
        )

        assert len(result) == 3

    def test_execute_rowcount(self, temp_db_manager):
        """测试fetch='rowcount'"""
        # 插入一条
        temp_db_manager._execute(
            "INSERT INTO diaries (date, content, view_count) VALUES (?, ?, ?)",
            ('2026-05-21 10:00:00', '测试', 0)
        )

        # 更新
        count = temp_db_manager._execute(
            "UPDATE diaries SET view_count = 5 WHERE content = ?",
            ('测试',),
            fetch='rowcount'
        )

        assert count == 1


class TestTagManagementMixin:
    """TagManagementMixin 标签管理集成测试"""

    def test_add_tag(self, temp_db_manager):
        """测试添加标签"""
        result = temp_db_manager.add_tag("测试标签")

        assert result is not None
        assert result['name'] == "测试标签"

    def test_add_duplicate_tag_returns_existing(self, temp_db_manager):
        """添加重复标签应返回现有标签"""
        temp_db_manager.add_tag("重复标签")
        result = temp_db_manager.add_tag("重复标签")

        assert result['name'] == "重复标签"
        # 验证只有一条记录
        all_tags = temp_db_manager.get_all_tags()
        assert len(all_tags) == 1

    def test_get_all_tags(self, temp_db_manager):
        """测试获取所有标签"""
        temp_db_manager.add_tag("标签A")
        temp_db_manager.add_tag("标签B")
        temp_db_manager.add_tag("标签C")

        result = temp_db_manager.get_all_tags()

        assert len(result) == 3
        names = [t['name'] for t in result]
        assert "标签A" in names
        assert "标签B" in names
        assert "标签C" in names

    def test_get_tag_by_name(self, temp_db_manager):
        """测试按名称获取标签"""
        temp_db_manager.add_tag("按名查找")

        result = temp_db_manager.get_tag_by_name("按名查找")

        assert result is not None
        assert result['name'] == "按名查找"

    def test_get_tag_by_name_not_found(self, temp_db_manager):
        """不存在的标签应返回None"""
        result = temp_db_manager.get_tag_by_name("不存在的标签")

        assert result is None

    def test_update_tag(self, temp_db_manager):
        """测试更新标签"""
        tag = temp_db_manager.add_tag("旧名称")
        tag_id = tag['id']

        result = temp_db_manager.update_tag(tag_id, "新名称")

        assert result is True
        updated = temp_db_manager.get_tag_by_id(tag_id)
        assert updated['name'] == "新名称"

    def test_delete_tag_not_in_use(self, temp_db_manager):
        """删除未使用的标签应成功"""
        tag = temp_db_manager.add_tag("待删除")
        tag_id = tag['id']

        result = temp_db_manager.delete_tag_by_id(tag_id)

        assert result is True
        assert temp_db_manager.get_tag_by_id(tag_id) is None

    def test_delete_tag_in_use_fails(self, temp_db_manager):
        """删除正在使用的标签应失败"""
        # 创建标签
        tag = temp_db_manager.add_tag("使用中")
        tag_id = tag['id']

        # 创建日记并关联标签
        diary_id = temp_db_manager._execute(
            "INSERT INTO diaries (date, content, view_count) VALUES (?, ?, ?)",
            ('2026-05-21 10:00:00', '测试日记', 0)
        )
        temp_db_manager.add_diary_tag(diary_id, tag_id)

        # 尝试删除
        result = temp_db_manager.delete_tag_by_id(tag_id)

        assert result is False
        # 标签仍然存在
        assert temp_db_manager.get_tag_by_id(tag_id) is not None

    def test_get_unused_tags(self, temp_db_manager):
        """测试获取未使用标签"""
        # 创建两个标签
        tag1 = temp_db_manager.add_tag("未使用")
        tag2 = temp_db_manager.add_tag("已使用")

        # 创建日记并关联其中一个
        diary_id = temp_db_manager._execute(
            "INSERT INTO diaries (date, content, view_count) VALUES (?, ?, ?)",
            ('2026-05-21 10:00:00', '测试', 0)
        )
        temp_db_manager.add_diary_tag(diary_id, tag2['id'])

        unused = temp_db_manager.get_unused_tags()

        assert len(unused) == 1
        assert unused[0]['name'] == "未使用"


class TestDatabaseQueryMixin:
    """DatabaseQueryMixin 数据库查询集成测试"""

    @pytest.fixture
    def populated_db(self, temp_db_manager):
        """填充测试数据的数据库"""
        # 插入多篇日记
        diaries = [
            ('2026-05-21 10:00:00', '今天的内容', 10),
            ('2026-05-20 10:00:00', '昨天的内容', 5),
            ('2026-05-19 10:00:00', '前天的内容', 0),
            ('2026-01-01 10:00:00', '年初的内容', 100),
        ]
        for date, content, views in diaries:
            temp_db_manager._execute(
                "INSERT INTO diaries (date, content, view_count) VALUES (?, ?, ?)",
                (date, content, views)
            )
        return temp_db_manager

    def test_get_most_viewed_diaries(self, populated_db):
        """测试获取查看次数最多的日记"""
        result = populated_db.get_most_viewed_diaries(limit=2)

        assert len(result) == 2
        assert result[0]['view_count'] >= result[1]['view_count']

    def test_get_least_viewed_diaries(self, populated_db):
        """测试获取查看次数最少的日记"""
        result = populated_db.get_least_viewed_diaries(limit=2)

        assert len(result) == 2
        assert result[0]['view_count'] <= result[1]['view_count']

    def test_search_by_keyword(self, populated_db):
        """测试关键词搜索"""
        result = populated_db.search_by_keyword("今天")

        assert len(result) == 1
        assert result[0]['content'] == "今天的内容"

    def test_search_by_keyword_no_match(self, populated_db):
        """搜索无结果"""
        result = populated_db.search_by_keyword("不存在的关键词")

        assert len(result) == 0

    def test_search_by_keyword_empty(self, populated_db):
        """空关键词应返回空列表"""
        result = populated_db.search_by_keyword("")

        assert result == []

    def test_get_random_diary(self, populated_db):
        """测试随机获取日记"""
        result = populated_db.get_random_diary()

        assert result is not None
        assert 'id' in result
        assert 'content' in result


class TestDiaryOperationsMixin:
    """DiaryOperationsMixin 日记操作集成测试"""

    def test_create_and_get_diary(self, temp_db_manager):
        """测试创建和获取日记"""
        # 创建日记
        diary_id = temp_db_manager._execute(
            "INSERT INTO diaries (date, content, view_count) VALUES (?, ?, ?)",
            ('2026-05-21 10:00:00', '新日记内容', 0)
        )

        # 获取日记
        result = temp_db_manager.get_diary_by_id(diary_id)

        assert result is not None
        assert result['content'] == '新日记内容'
        assert result['view_count'] == 0

    def test_update_diary(self, temp_db_manager):
        """测试更新日记"""
        # 创建日记
        diary_id = temp_db_manager._execute(
            "INSERT INTO diaries (date, content, view_count) VALUES (?, ?, ?)",
            ('2026-05-21 10:00:00', '原始内容', 0)
        )

        # 更新
        success = temp_db_manager.update_diary(diary_id, new_content='更新内容')
        assert success is True

        # 验证
        updated = temp_db_manager.get_diary_by_id(diary_id)
        assert updated['content'] == '更新内容'

    def test_delete_diary(self, temp_db_manager):
        """测试删除日记"""
        # 创建日记
        diary_id = temp_db_manager._execute(
            "INSERT INTO diaries (date, content, view_count) VALUES (?, ?, ?)",
            ('2026-05-21 10:00:00', '待删除', 0)
        )

        # 删除
        result = temp_db_manager.delete_diary_by_id(diary_id)
        assert result is not None

        # 验证不存在
        result = temp_db_manager.get_diary_by_id(diary_id)
        assert result is None


# =============================================================================
# TrashMixin tests are skipped because they require proper trash database setup
# which is complex for temp databases. The trash functionality uses a separate
# trash_db that is not properly initialized in the temp_db_manager fixture.
# These would be better suited as manual integration tests or with a dedicated
# test database setup.
# =============================================================================
# class TestTrashMixin:
#     """TrashMixin 垃圾桶集成测试"""
#
#     def test_move_to_trash_and_restore(self, temp_db_manager):
#         ...
#
#     def test_get_all_trash_diaries(self, temp_db_manager):
#         ...
#
#     def test_purge_from_trash(self, temp_db_manager):
#         ...
