"""下行仅更新已映射日记，冲突时保持本地数据与游标。"""
import hashlib
import json

import pytest

from desktop.sync.local_repository import LocalDiaryRepository
from desktop.sync.reconcile import plan_mapping
from desktop.sync.service import DesktopSyncService, SyncConflict
from models.enhanced_database import EnhancedDatabaseManager


@pytest.fixture
def local_db(tmp_path):
    manager = EnhancedDatabaseManager(str(tmp_path / "diary.db"))
    yield manager
    manager.close()


def remote(diary, remote_id, version=1, content=None, tags=None, date=None):
    content = diary["content"] if content is None else content
    return {"id": remote_id, "date": date or diary["date"][:10], "content": content,
            "content_hash": "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest(),
            "tags": [t["name"] for t in diary.get("tags", [])] if tags is None else tags,
            "version": version, "deleted_at": None}


def change(cursor, data, action="upsert", version=None):
    return {"change": {"cursor": cursor, "entity_type": "diary",
                       "entity_id": data["id"], "action": action,
                       "version": data["version"] if version is None else version},
            "data": data}


class FakeClient:
    def __init__(self, pages):
        self.pages = pages
        self.cursors = []

    def pull(self, cursor):
        self.cursors.append(cursor)
        return self.pages.get(cursor, {"items": [], "next_cursor": cursor})


def setup_service(tmp_path, client, diaries, remotes):
    service = DesktopSyncService(client, tmp_path / "sync-state.json")
    plan = plan_mapping(diaries, remotes)
    assert plan.complete
    service.state = {"mapped": True, "cursor": 0, "entries": plan.matches}
    service._save_state()
    return service


def test_mapped_update_preserves_date_and_view_count(local_db, tmp_path):
    tag = local_db.add_tag("原标签")
    diary = local_db.add_diary_with_tags("原文", [tag["id"]])
    diary["tags"] = local_db.get_tags_by_diary_id(diary["id"])
    before = local_db.get_diary_by_id(diary["id"])
    incoming = remote(diary, "remote-1", version=2, content="服务器正文", tags=["新标签"])
    client = FakeClient({0: {"items": [change(1, incoming)], "next_cursor": 1}})
    service = setup_service(tmp_path, client, [diary], [remote(diary, "remote-1")])

    result = service.pull_once(LocalDiaryRepository(local_db.db_path))
    assert result == {"applied": 1, "pages": 1, "cursor": 1}
    current = local_db.get_diary_by_id(diary["id"])
    assert current["content"] == "服务器正文"
    assert current["date"] == before["date"]
    assert current["view_count"] == before["view_count"]
    assert [tag["name"] for tag in local_db.get_tags_by_diary_id(diary["id"])] == ["新标签"]
    assert service.state["entries"][str(diary["id"])]["version"] == 2
    assert json.loads(service.state_path.read_text(encoding="utf-8"))["cursor"] == 1
    assert client.cursors == [0, 1]


def test_initial_history_only_advances_cursor(local_db, tmp_path):
    diary = local_db.add_diary("原文")
    incoming = remote(diary, "remote-1")
    service = setup_service(tmp_path, FakeClient({0: {"items": [change(1, incoming)],
                                                    "next_cursor": 1}}),
                            [diary], [incoming])
    assert service.pull_once(LocalDiaryRepository(local_db.db_path)) == {
        "applied": 0, "pages": 1, "cursor": 1,
    }
    assert local_db.get_diary_by_id(diary["id"])["content"] == "原文"


def test_offline_edit_never_gets_overwritten(local_db, tmp_path):
    diary = local_db.add_diary("原文")
    incoming = remote(diary, "remote-1", version=2, content="服务器正文")
    service = setup_service(tmp_path, FakeClient({0: {"items": [change(1, incoming)],
                                                    "next_cursor": 1}}),
                            [diary], [remote(diary, "remote-1")])
    local_db.update_diary(diary["id"], "本地离线修改")
    with pytest.raises(SyncConflict, match="本地日记已变更"):
        service.pull_once(LocalDiaryRepository(local_db.db_path))
    assert local_db.get_diary_by_id(diary["id"])["content"] == "本地离线修改"
    assert service.state["cursor"] == 0


def test_page_prevalidation_rejects_new_and_delete(local_db, tmp_path):
    diary = local_db.add_diary("原文")
    initial = remote(diary, "remote-1")
    changed = remote(diary, "remote-1", version=2, content="待下行")
    created = remote(diary, "new-remote", content="远程新增")
    service = setup_service(tmp_path, FakeClient({0: {"items": [change(1, changed), change(2, created)],
                                                    "next_cursor": 2}}), [diary], [initial])
    with pytest.raises(SyncConflict, match="人工审核"):
        service.pull_once(LocalDiaryRepository(local_db.db_path))
    assert local_db.get_diary_by_id(diary["id"])["content"] == "原文"
    assert service.state["cursor"] == 0

    service.client = FakeClient({0: {"items": [change(1, changed, action="delete")], "next_cursor": 1}})
    with pytest.raises(SyncConflict, match="人工审核"):
        service.pull_once(LocalDiaryRepository(local_db.db_path))
    assert service.state["cursor"] == 0


def test_batch_is_atomic_when_second_local_diary_dirty(local_db, tmp_path):
    first = local_db.add_diary("甲")
    second = local_db.add_diary("乙")
    first_update = remote(first, "r1", version=2, content="甲远程")
    second_update = remote(second, "r2", version=2, content="乙远程")
    service = setup_service(tmp_path, FakeClient({0: {"items": [change(1, first_update),
                                                             change(2, second_update)], "next_cursor": 2}}),
                            [first, second], [remote(first, "r1"), remote(second, "r2")])
    local_db.update_diary(second["id"], "乙离线")
    with pytest.raises(SyncConflict, match="本地日记已变更"):
        service.pull_once(LocalDiaryRepository(local_db.db_path))
    assert local_db.get_diary_by_id(first["id"])["content"] == "甲"
    assert local_db.get_diary_by_id(second["id"])["content"] == "乙离线"
    assert service.state["cursor"] == 0


def test_changed_date_is_blocked(local_db, tmp_path):
    diary = local_db.add_diary("原文")
    incoming = remote(diary, "remote-1", version=2, date="2020-01-01")
    service = setup_service(tmp_path, FakeClient({0: {"items": [change(1, incoming)], "next_cursor": 1}}),
                            [diary], [remote(diary, "remote-1")])
    with pytest.raises(SyncConflict, match="人工审核"):
        service.pull_once(LocalDiaryRepository(local_db.db_path))
    assert service.state["cursor"] == 0


def test_failed_state_save_fails_closed_after_db_commit(local_db, tmp_path, monkeypatch):
    diary = local_db.add_diary("原文")
    incoming = remote(diary, "remote-1", version=2, content="服务器正文")
    client = FakeClient({0: {"items": [change(1, incoming)], "next_cursor": 1}})
    service = setup_service(tmp_path, client, [diary], [remote(diary, "remote-1")])

    def save_failure():
        raise OSError("测试中断")

    monkeypatch.setattr(service, "_save_state", save_failure)
    with pytest.raises(SyncConflict, match="下次下行会尝试"):
        service.pull_once(LocalDiaryRepository(local_db.db_path))
    assert local_db.get_diary_by_id(diary["id"])["content"] == "服务器正文"
    assert service.state["cursor"] == 0
    assert json.loads(service.state_path.read_text(encoding="utf-8"))["cursor"] == 0
    retry = DesktopSyncService(client, service.state_path)
    assert retry.pull_once(LocalDiaryRepository(local_db.db_path)) == {
        "applied": 0, "pages": 0, "cursor": 1,
    }
    assert retry.state["entries"][str(diary["id"])]["version"] == 2
    assert json.loads(service.state_path.read_text(encoding="utf-8"))["cursor"] == 1
    assert client.cursors == [0, 1]


def test_same_version_different_content_cannot_be_applied(local_db, tmp_path):
    diary = local_db.add_diary("原文")
    incoming = remote(diary, "remote-1", content="同版本修改")
    service = setup_service(tmp_path, FakeClient({0: {"items": [change(1, incoming)],
                                                    "next_cursor": 1}}),
                            [diary], [remote(diary, "remote-1")])
    with pytest.raises(SyncConflict, match="人工审核"):
        service.pull_once(LocalDiaryRepository(local_db.db_path))
    assert local_db.get_diary_by_id(diary["id"])["content"] == "原文"
    assert service.state["cursor"] == 0


def test_repeated_old_events_with_latest_data_update_only_once(local_db, tmp_path):
    diary = local_db.add_diary("原文")
    incoming = remote(diary, "remote-1", version=3, content="最终内容")
    page = {"items": [change(1, incoming, version=1), change(2, incoming, version=3)],
            "next_cursor": 2}
    service = setup_service(tmp_path, FakeClient({0: page}),
                            [diary], [remote(diary, "remote-1")])
    assert service.pull_once(LocalDiaryRepository(local_db.db_path)) == {
        "applied": 1, "pages": 1, "cursor": 2,
    }
    assert local_db.get_diary_by_id(diary["id"])["content"] == "最终内容"


def test_receipt_recovery_requires_unchanged_local_record(local_db, tmp_path, monkeypatch):
    diary = local_db.add_diary("原文")
    incoming = remote(diary, "remote-1", version=2, content="服务器正文")
    client = FakeClient({0: {"items": [change(1, incoming)], "next_cursor": 1}})
    service = setup_service(tmp_path, client, [diary], [remote(diary, "remote-1")])

    def save_failure():
        raise OSError("模拟写入失败")

    monkeypatch.setattr(service, "_save_state", save_failure)
    with pytest.raises(SyncConflict, match="下次下行会尝试"):
        service.pull_once(LocalDiaryRepository(local_db.db_path))
    local_db.update_diary(diary["id"], "恢复前离线更改")
    retry = DesktopSyncService(client, service.state_path)
    with pytest.raises(SyncConflict, match="恢复前发生变化"):
        retry.pull_once(LocalDiaryRepository(local_db.db_path))
    assert retry.state["cursor"] == 0
    assert json.loads(service.state_path.read_text(encoding="utf-8"))["cursor"] == 0
    assert client.cursors == [0]


def test_two_pages_recover_only_unfinished_receipt(local_db, tmp_path, monkeypatch):
    diary = local_db.add_diary("原文")
    first = remote(diary, "remote-1", version=2, content="第一次更改")
    second = remote(diary, "remote-1", version=3, content="第二次更改")
    client = FakeClient({
        0: {"items": [change(1, first)], "next_cursor": 1},
        1: {"items": [change(2, second)], "next_cursor": 2},
    })
    service = setup_service(tmp_path, client, [diary], [remote(diary, "remote-1")])
    original_save = service._save_state
    attempts = 0

    def fail_second_save():
        nonlocal attempts
        attempts += 1
        if attempts == 2:
            raise OSError("模拟第二页写入中断")
        original_save()

    monkeypatch.setattr(service, "_save_state", fail_second_save)
    with pytest.raises(SyncConflict, match="下次下行会尝试"):
        service.pull_once(LocalDiaryRepository(local_db.db_path))
    assert local_db.get_diary_by_id(diary["id"])["content"] == "第二次更改"
    assert json.loads(service.state_path.read_text(encoding="utf-8"))["cursor"] == 1
    retry = DesktopSyncService(client, service.state_path)
    assert retry.pull_once(LocalDiaryRepository(local_db.db_path)) == {
        "applied": 0, "pages": 0, "cursor": 2,
    }
    assert client.cursors == [0, 1, 2]


def test_receipt_recovery_rejects_unrelated_sync_state(local_db, tmp_path):
    diary = local_db.add_diary("原文")
    incoming = remote(diary, "remote-1", version=2, content="服务器正文")
    client = FakeClient({0: {"items": [change(1, incoming)], "next_cursor": 1}})
    service = setup_service(tmp_path, client, [diary], [remote(diary, "remote-1")])
    service.pull_once(LocalDiaryRepository(local_db.db_path))
    different = dict(service.state)
    different["cursor"] = 3
    service.state_path.write_text(json.dumps(different), encoding="utf-8")
    retry = DesktopSyncService(client, service.state_path)
    with pytest.raises(SyncConflict, match="SQLite 与同步状态不一致"):
        retry.pull_once(LocalDiaryRepository(local_db.db_path))
    assert client.cursors == [0, 1]


def test_receipt_recovery_rejects_corrupted_target(local_db, tmp_path, monkeypatch):
    diary = local_db.add_diary("原文")
    incoming = remote(diary, "remote-1", version=2, content="服务器正文")
    client = FakeClient({0: {"items": [change(1, incoming)], "next_cursor": 1}})
    service = setup_service(tmp_path, client, [diary], [remote(diary, "remote-1")])

    def save_failure():
        raise OSError("模拟写入失败")

    monkeypatch.setattr(service, "_save_state", save_failure)
    with pytest.raises(SyncConflict, match="下次下行会尝试"):
        service.pull_once(LocalDiaryRepository(local_db.db_path))
    import sqlite3
    with sqlite3.connect(local_db.db_path) as conn:
        conn.execute("UPDATE desktop_sync_receipt SET targets = ? WHERE id = ?",
                     (json.dumps({str(diary["id"]): "sha256:bad"}), 1))
    retry = DesktopSyncService(client, service.state_path)
    with pytest.raises(SyncConflict, match="恢复记录损坏"):
        retry.pull_once(LocalDiaryRepository(local_db.db_path))
    assert retry.state["cursor"] == 0
    assert client.cursors == [0]


def test_external_state_change_is_detected_before_network_read(local_db, tmp_path):
    diary = local_db.add_diary("原文")
    client = FakeClient({})
    service = setup_service(tmp_path, client, [diary], [remote(diary, "remote-1")])
    new_state = json.loads(service.state_path.read_text(encoding="utf-8"))
    new_state["cursor"] = 99
    service.state_path.write_text(json.dumps(new_state), encoding="utf-8")
    with pytest.raises(SyncConflict, match="其他进程修改"):
        service.pull_once(LocalDiaryRepository(local_db.db_path))
    assert client.cursors == []
