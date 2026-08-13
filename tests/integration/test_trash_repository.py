"""TrashRepository 门面与真实垃圾桶数据库集成测试。"""
from unittest.mock import MagicMock

import pytest

from models.repository.trash.repository import TrashRepository


@pytest.fixture
def repository_deps(mocker):
    pool = mocker.MagicMock(name="pool")
    schema = mocker.MagicMock(name="schema")
    search = mocker.MagicMock(name="search")
    capacity = mocker.MagicMock(name="capacity")
    two_pc = mocker.MagicMock(name="two_pc")
    two_pc.new_op_id.return_value = "op-1"
    return pool, schema, search, capacity, two_pc


@pytest.fixture
def repository(repository_deps):
    return TrashRepository(*repository_deps)


class TestTrashRepositoryFacade:
    def test_lifecycle_delegates_to_dependencies(self, repository, repository_deps):
        pool, schema, _, _, two_pc = repository_deps
        repository.init_schema()
        repository.close()
        assert repository.recover_pending_ops() == two_pc.recover_pending_ops.return_value
        schema.initialize.assert_called_once_with()
        pool.close.assert_called_once_with()
        two_pc.recover_pending_ops.assert_called_once_with()

    def test_get_all_count_and_lookup(self, repository, repository_deps):
        pool, _, _, _, _ = repository_deps
        pool.execute.side_effect = [
            [{"id": 1}],
            [{"id": 2}],
            {"count": 2},
            {"id": 3},
        ]
        assert repository.get_all() == [{"id": 1}]
        assert repository.get_all(limit=1) == [{"id": 2}]
        assert repository.count() == 2
        assert repository.get_by_id(3) == {"id": 3}
        assert pool.execute.call_count == 4
        assert pool.execute.call_args_list[1].args[1] == (1,)

    def test_search_empty_keyword_uses_list_and_non_empty_uses_search(self, repository, repository_deps, mocker):
        _, _, search, _, _ = repository_deps
        get_all = mocker.patch.object(repository, "get_all", return_value=[{"id": 1}])
        search.search.return_value = [{"id": 2}]
        assert repository.search("   ", limit=5) == [{"id": 1}]
        assert repository.search("关键词", limit=7) == [{"id": 2}]
        get_all.assert_called_once_with(5)
        search.search.assert_called_once_with("关键词", 7)

    def test_move_missing_diary_is_noop(self, repository, repository_deps):
        _, schema, _, capacity, two_pc = repository_deps
        main_db = MagicMock()
        main_db.get_diary_by_id.return_value = None
        assert repository.move_to_trash(main_db, 9) is None
        schema.compute_tokens.assert_not_called()
        two_pc.precommit.assert_not_called()
        capacity.enforce.assert_not_called()

    def test_move_runs_three_phases_and_capacity(self, repository, repository_deps):
        pool, schema, _, capacity, two_pc = repository_deps
        main_db = MagicMock()
        main_db.get_diary_by_id.return_value = {
            "id": 9, "date": "2026-08-13 10:00:00", "content": "内容",
            "view_count": 2, "last_viewed_at": None, "updated_at": "2026-08-13 10:00:00",
        }
        main_db.get_tags_by_diary_id.return_value = [{"id": 3, "name": "标签"}]
        schema.compute_tokens.return_value = "内容"
        pool.execute.return_value = {"id": 12}
        result = repository.move_to_trash(main_db, 9)
        assert result["trash_id"] == 12
        assert result["original_id"] == 9
        assert result["op_id"] == "op-1"
        assert [call.args[1] for call in two_pc.precommit.call_args_list] == ["move"]
        two_pc.apply_to_main.assert_called_once()
        two_pc.commit_to_trash.assert_called_once()
        capacity.enforce.assert_called_once()

    def test_move_failure_cleans_pending_and_reraises(self, repository, repository_deps):
        _, schema, _, _, two_pc = repository_deps
        main_db = MagicMock()
        main_db.get_diary_by_id.return_value = {"date": "d", "content": "c"}
        schema.compute_tokens.return_value = "c"
        two_pc.apply_to_main.side_effect = RuntimeError("crash")
        with pytest.raises(RuntimeError, match="crash"):
            repository.move_to_trash(main_db, 1, enforce_capacity=False)
        two_pc.cleanup_pending_op.assert_called_once_with("op-1")
        two_pc.commit_to_trash.assert_not_called()

    def test_restore_missing_trash_is_noop(self, repository, repository_deps):
        pool, _, _, _, two_pc = repository_deps
        pool.execute.return_value = None
        main_db = MagicMock()
        assert repository.restore_from_trash(main_db, 6) is None
        two_pc.precommit.assert_not_called()

    def test_restore_runs_three_phases_and_returns_new_diary(self, repository, repository_deps):
        pool, _, _, _, two_pc = repository_deps
        main_db = MagicMock()
        main_db.compute_tokens.return_value = "tokens"
        main_db._execute.return_value = {"id": 20}
        main_db.get_diary_by_id.return_value = {"id": 20, "content": "恢复"}
        pool.execute.side_effect = [
            {"id": 6, "original_id": 4, "date": "d", "content": "恢复", "view_count": 0},
            [],
        ]
        assert repository.restore_from_trash(main_db, 6) == {"id": 20, "content": "恢复"}
        two_pc.precommit.assert_called_once()
        two_pc.apply_to_main.assert_called_once()
        two_pc.commit_to_trash.assert_called_once()

    def test_delete_and_empty_return_expected_booleans_and_counts(self, repository, repository_deps):
        pool, _, _, _, _ = repository_deps
        pool.execute.side_effect = [1, 0, {"count": 3}, 3]
        assert repository.permanently_delete(1) is True
        assert repository.permanently_delete(2) is False
        assert repository.empty() == 3

    def test_payload_builders_keep_diary_and_tag_fields(self):
        move = TrashRepository._build_move_payload(
            {"date": "d", "content": "c", "view_count": 2},
            [{"id": 8, "name": "tag"}],
            "c",
        )
        restore = TrashRepository._build_restore_payload(
            {"date": "d", "content": "c", "view_count": 2},
            [{"name": "tag", "original_tag_id": 8}],
            "c",
        )
        assert move["tags"] == [{"name": "tag", "original_tag_id": 8}]
        assert restore["tags"] == [{"name": "tag", "original_tag_id": 8}]
        assert move["tokens"] == restore["tokens"] == "c"


class TestTrashRepositoryRealIntegration:
    def test_move_search_restore_and_permanent_delete(self, temp_db_path):
        from models.enhanced_database import EnhancedDatabaseManager

        db = EnhancedDatabaseManager(temp_db_path)
        try:
            diary = db.add_diary("垃圾桶集成测试内容")
            assert diary is not None
            tag = db.add_tag("集成标签")
            db.assign_tags_to_diary(diary["id"], [tag["id"]])

            moved = db.move_to_trash(diary["id"])
            assert moved is not None
            assert db.get_diary_by_id(diary["id"]) is None
            trash = db.get_trash_diary_by_id(moved["trash_id"])
            assert trash["content"] == "垃圾桶集成测试内容"
            assert db.search_trash_by_keyword("集成")

            restored = db.restore_from_trash(moved["trash_id"])
            assert restored is not None
            assert restored["content"] == "垃圾桶集成测试内容"
            assert db.get_trash_count() == 0
        finally:
            db.close()
