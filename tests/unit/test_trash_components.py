"""垃圾桶连接、容量、搜索和 handler 边界测试。"""
import sqlite3
from unittest.mock import MagicMock

import pytest

from models.repository.trash.capacity import TrashCapacityManager
from models.repository.trash.connection import TrashConnectionPool
from models.repository.trash.schema import TrashSchemaInitializer
from models.repository.trash.search import TrashSearchService
from models.repository.trash.transactions.handlers import (
    MoveToTrashHandler,
    RestoreFromTrashHandler,
    TrashOperationHandlerFactory,
)


def make_pool(tmp_path):
    pool = TrashConnectionPool(str(tmp_path / "diary.db"))
    TrashSchemaInitializer(pool).initialize()
    return pool


class TestTrashConnectionPool:
    def test_path_pragmas_fetch_modes_and_close(self, tmp_path):
        pool = make_pool(tmp_path)
        try:
            assert pool.db_path.endswith("trash_diary.db")
            assert pool.execute("INSERT INTO trash_diaries (date, deleted_at, content) VALUES (?, ?, ?)",
                                ("d", "t", "内容")) == 1
            assert pool.execute("SELECT * FROM trash_diaries", fetch="one")["content"] == "内容"
            assert pool.execute("SELECT * FROM trash_diaries", fetch="all")
            assert pool.execute("UPDATE trash_diaries SET content = ?", ("更新",), fetch="rowcount") == 1
            assert pool.execute("SELECT * FROM trash_diaries WHERE id = 99", fetch="one") is None
            assert pool.connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        finally:
            pool.close()
            pool.close()
        with pytest.raises(RuntimeError, match="已关闭"):
            _ = pool.connection
        with pytest.raises(RuntimeError, match="已关闭"):
            with pool.transaction():
                pass

    def test_transaction_rolls_back_sql_error(self, tmp_path):
        pool = make_pool(tmp_path)
        try:
            with pytest.raises(sqlite3.IntegrityError):
                with pool.transaction() as cursor:
                    cursor.execute("INSERT INTO trash_diaries (date, deleted_at, content) VALUES (?, ?, ?)",
                                   ("d", "t", "保留不了"))
                    cursor.execute("INSERT INTO trash_diaries (date, deleted_at, content) VALUES (?, ?, ?)",
                                   (None, "t", "失败"))
            assert pool.execute("SELECT COUNT(*) AS count FROM trash_diaries", fetch="one")["count"] == 0
        finally:
            pool.close()


class TestTrashCapacityAndSearch:
    def test_capacity_evicts_oldest_and_noops_under_limit(self, tmp_path):
        pool = make_pool(tmp_path)
        try:
            for deleted_at in ("2026-01-01", "2026-02-01", "2026-03-01"):
                pool.execute("INSERT INTO trash_diaries (date, deleted_at, content) VALUES (?, ?, ?)",
                             (deleted_at, deleted_at, deleted_at))
            manager = TrashCapacityManager(pool)
            assert manager.enforce(5) == 0
            assert manager.enforce(2) == 1
            rows = pool.execute("SELECT content FROM trash_diaries ORDER BY deleted_at", fetch="all")
            assert [row["content"] for row in rows] == ["2026-02-01", "2026-03-01"]
        finally:
            pool.close()

    def test_search_uses_like_fallback_and_empty_match(self, tmp_path, mocker):
        pool = make_pool(tmp_path)
        try:
            pool.execute("INSERT INTO trash_diaries (date, deleted_at, content, tokens) VALUES (?, ?, ?, ?)",
                         ("d", "t", "中文搜索", "中文 搜索"))
            schema = TrashSchemaInitializer(pool)
            schema.initialize()
            service = TrashSearchService(pool, schema)
            mocker.patch.object(schema, "_fts5_available", False)
            assert service.search("中文")
            assert service.search("\x00") == []
            mocker.patch.object(pool, "execute", side_effect=sqlite3.Error("fts fail"))
            assert service._search_by_fts5("中文", 10) == []
        finally:
            pool.close()


class TestTrashHandlers:
    def test_move_handler_deletes_main_and_copies_tags(self):
        main = MagicMock(db_path="relative/main.db")
        cursor = MagicMock(lastrowid=7)
        handler = MoveToTrashHandler(main, lambda: "now")
        handler.apply_to_main(cursor, 3, None, {})
        handler.apply_to_trash(cursor, 3, None, {
            "date": "d", "content": "c", "tags": [{"name": "标签", "original_tag_id": 2}]
        })
        assert cursor.execute.call_count == 3
        assert "DELETE FROM diaries" in cursor.execute.call_args_list[0].args[0]

    def test_restore_handler_resolves_existing_or_new_tags(self):
        main = MagicMock()
        main.get_tag_by_id.side_effect = [None]
        main.get_tag_by_name.return_value = None
        main.add_tag.return_value = {"id": 8}
        cursor = MagicMock(lastrowid=12)
        handler = RestoreFromTrashHandler(main)
        handler.apply_to_main(cursor, None, 4, {
            "date": "d", "content": "c", "tags": [{"name": "新标签", "original_tag_id": 2}]
        })
        handler.apply_to_trash(cursor, None, 4, {})
        assert main.add_tag.called
        assert any("diary_tags" in call.args[0] for call in cursor.execute.call_args_list)
        assert any("DELETE FROM trash_diaries" in call.args[0] for call in cursor.execute.call_args_list)

    def test_factory_rejects_unknown_operation(self):
        factory = TrashOperationHandlerFactory(MagicMock())
        assert factory.create("move") is not None
        assert factory.create("restore") is not None
        with pytest.raises(ValueError, match="未知 op_type"):
            factory.create("invalid")
