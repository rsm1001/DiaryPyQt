"""冲突裁决、删除与服务器编辑的胜负、回收站换 ID 与崩溃恢复。"""
from datetime import datetime, timedelta, timezone

import pytest

from desktop.tests.sync.harness import make_mapped, rebuild_engine, utc


def test_conflict_remote_newer_overwrites_and_keeps_local_copy(tmp_path, local_db):
    client, (service, engine) = make_mapped(tmp_path, local_db, ("原文",))
    diary = local_db.get_all_diaries()[0]
    local_db.update_diary_with_tags(diary["id"], "本地改的", [])
    client.edit_remote("remote-1", "服务器改的",
                       updated_at=utc(datetime.now(timezone.utc) + timedelta(hours=1)))
    engine.sync_round()
    assert local_db.get_diary_by_id(diary["id"])["content"] == "服务器改的"
    assert service.state["conflicts"][-1]["local_payload"]["content"] == "本地改的"


def test_conflict_local_newer_keeps_local_and_pushes(tmp_path, local_db):
    client, (service, engine) = make_mapped(tmp_path, local_db, ("原文",))
    diary = local_db.get_all_diaries()[0]
    local_db.update_diary_with_tags(diary["id"], "本地改的", [])
    client.edit_remote("remote-1", "服务器改的",
                       updated_at=utc(datetime.now(timezone.utc) - timedelta(hours=2)))
    engine.sync_round()
    assert local_db.get_diary_by_id(diary["id"])["content"] == "本地改的"
    assert client.records["remote-1"]["content"] == "本地改的"


def test_unparsable_timestamp_blocks_overwrite(tmp_path, local_db):
    client, (service, engine) = make_mapped(tmp_path, local_db, ("原文",))
    diary = local_db.get_all_diaries()[0]
    local_db.update_diary_with_tags(diary["id"], "本地改的", [])
    broken = client.edit_remote("remote-1", "服务器改的")
    client.records["remote-1"] = {**broken, "updated_at": "不是时间"}
    client.changes[-1]["updated_at"] = "不是时间"
    engine.sync_round()
    assert local_db.get_diary_by_id(diary["id"])["content"] == "本地改的"
    assert service.state["conflicts"][-1]["kind"] == "timestamp_ambiguous"


def test_push_conflict_retries_when_local_is_newer(tmp_path, local_db):
    client, (service, engine) = make_mapped(tmp_path, local_db, ("原文",))
    diary = local_db.get_all_diaries()[0]
    local_db.update_diary_with_tags(diary["id"], "本地改的", [])
    server_version = {**client.records["remote-1"], "version": 9,
                      "updated_at": utc(datetime.now(timezone.utc) - timedelta(hours=3))}
    client.records["remote-1"] = server_version
    client.forced_conflict["remote-1"] = server_version
    engine.sync_round()
    assert client.records["remote-1"]["content"] == "本地改的"


def test_push_conflict_when_server_newer_keeps_server(tmp_path, local_db):
    from desktop.tests.sync.harness import content_hash

    client, (service, engine) = make_mapped(tmp_path, local_db, ("原文",))
    diary = local_db.get_all_diaries()[0]
    local_db.update_diary_with_tags(diary["id"], "本地改的", [])
    newer = {**client.records["remote-1"], "content": "服务器改的", "version": 9,
             "content_hash": content_hash("服务器改的"),
             "updated_at": utc(datetime.now(timezone.utc) + timedelta(hours=3))}
    client.records["remote-1"] = newer
    client.forced_conflict["remote-1"] = newer
    engine.sync_round()
    assert client.records["remote-1"]["content"] == "服务器改的"
    assert service.state["conflicts"][-1]["kind"] == "push_rejected"


def test_restored_trash_rekeys_instead_of_duplicating(tmp_path, local_db):
    client, (service, engine) = make_mapped(tmp_path, local_db, ("要恢复的",))
    diary = local_db.get_all_diaries()[0]
    local_db.move_to_trash(diary["id"])
    local_db.restore_from_trash(local_db.get_all_trash_diaries()[0]["id"])
    restored = local_db.get_all_diaries()[0]
    assert restored["id"] != diary["id"]

    engine.sync_round()
    assert str(restored["id"]) in service.state["entries"]
    assert str(diary["id"]) not in service.state["entries"]
    assert client.records["remote-1"]["deleted_at"] is None
    # 服务器不能多出一篇重复日记
    assert len(client.records) == 1
    assert client.pushed == []


def test_server_edit_after_local_delete_resurrects_local(tmp_path, local_db):
    client, (service, engine) = make_mapped(tmp_path, local_db, ("原文",))
    diary = local_db.get_all_diaries()[0]
    local_db.move_to_trash(diary["id"])
    client.edit_remote("remote-1", "服务器在删除后又改的",
                       updated_at=utc(datetime.now(timezone.utc) + timedelta(hours=2)))
    engine.sync_round()
    resurrected = local_db.get_diary_by_id(diary["id"])
    assert resurrected is not None
    assert resurrected["content"] == "服务器在删除后又改的"
    assert client.records["remote-1"]["deleted_at"] is None


def test_local_delete_after_server_edit_propagates(tmp_path, local_db):
    client, (service, engine) = make_mapped(tmp_path, local_db, ("原文",))
    diary = local_db.get_all_diaries()[0]
    client.edit_remote("remote-1", "服务器较早的修改",
                       updated_at=utc(datetime.now(timezone.utc) - timedelta(hours=2)))
    local_db.move_to_trash(diary["id"])
    engine.sync_round()
    assert client.records["remote-1"]["deleted_at"] is not None
    assert local_db.get_diary_by_id(diary["id"]) is None


def test_delete_without_trash_record_falls_back_to_delete(tmp_path, local_db):
    client, (service, engine) = make_mapped(tmp_path, local_db, ("原文",))
    diary = local_db.get_all_diaries()[0]
    local_db.move_to_trash(diary["id"])
    local_db.permanently_delete_trash(local_db.get_all_trash_diaries()[0]["id"])
    client.edit_remote("remote-1", "服务器修改",
                       updated_at=utc(datetime.now(timezone.utc) + timedelta(hours=2)))
    engine.sync_round()
    # 回收站记录已被清掉，取不到删除时间，按"删除优先"处理
    assert client.records["remote-1"]["deleted_at"] is not None


def test_crash_after_downlink_recovers_without_duplicate_write(tmp_path, local_db, monkeypatch):
    client, (service, engine) = make_mapped(tmp_path, local_db, ("正文",))
    diary = local_db.get_all_diaries()[0]
    client.edit_remote("remote-1", "服务器改过")

    def boom():
        raise OSError("磁盘写入失败")

    monkeypatch.setattr(service, "_save_state", boom)
    with pytest.raises(OSError):
        engine.sync_round()
    monkeypatch.undo()

    # 重建服务：应从 SQLite 收据补写游标，且本地内容已经落地
    retry_service, retry = rebuild_engine(tmp_path, local_db, client)
    retry.sync_round()
    assert local_db.get_diary_by_id(diary["id"])["content"] == "服务器改过"
    assert retry_service.state["cursor"] == client.cursor
    assert len(local_db.get_all_diaries()) == 1
