"""决策层的防护：脏数据、版本异常与日期变化一律停下等人工。"""
import pytest

from desktop.sync.service import SyncConflict
from desktop.tests.sync.harness import content_hash, make_mapped, rebuild_engine, remote_diary


def test_server_date_change_is_held_for_review(tmp_path, local_db):
    client, (service, engine) = make_mapped(tmp_path, local_db, ("正文",))
    diary = local_db.get_all_diaries()[0]
    record = client.edit_remote("remote-1", "服务器改过")
    moved = {**record, "date": "2026-01-01"}
    client.records["remote-1"] = moved
    client.changes[-1]["updated_at"] = moved["updated_at"]

    engine.sync_round()
    # 本地与服务器都不能被改，且必须留下可人工处理的记录
    assert local_db.get_diary_by_id(diary["id"])["content"] == "正文"
    assert client.records["remote-1"]["date"] == "2026-01-01"
    assert service.state["conflicts"][-1]["kind"] == "timestamp_ambiguous"
    assert client.pushed == []


def test_version_rollback_is_refused(tmp_path, local_db):
    client, (service, engine) = make_mapped(tmp_path, local_db, ("正文",))
    lowered = {**client.records["remote-1"], "content": "回退的正文",
               "content_hash": content_hash("回退的正文"), "version": 0}
    client.records["remote-1"] = lowered
    client._record("remote-1", "upsert", 0, lowered["updated_at"])
    with pytest.raises(SyncConflict):
        engine.sync_round()


def test_same_version_with_different_content_is_refused(tmp_path, local_db):
    client, (service, engine) = make_mapped(tmp_path, local_db, ("正文",))
    tampered = {**client.records["remote-1"], "content": "被篡改的正文",
                "content_hash": content_hash("被篡改的正文")}
    client.records["remote-1"] = tampered
    client._record("remote-1", "upsert", tampered["version"], tampered["updated_at"])
    with pytest.raises(SyncConflict):
        engine.sync_round()


def test_broken_cursor_is_refused():
    """游标必须严格递增，空页也不许推进。"""
    from desktop.sync.engine.planner import PlanConflict, validate_page

    item = {"change": {"cursor": 5, "entity_type": "diary", "entity_id": "remote-1",
                       "action": "delete", "version": 1}, "data": {}}
    with pytest.raises(PlanConflict, match="游标异常"):
        validate_page([item], 5, 5)      # 有变更却没推进
    with pytest.raises(PlanConflict, match="游标异常"):
        validate_page([], 1, 5)          # 空页却推进了游标
    with pytest.raises(PlanConflict, match="游标与变更不一致"):
        validate_page([{**item, "change": {**item["change"], "cursor": 3}}], 1, 5)


def test_unknown_sync_action_is_refused(tmp_path, local_db):
    client, (service, engine) = make_mapped(tmp_path, local_db, ("正文",))
    record = client.edit_remote("remote-1", "服务器改过")
    client.changes[-1]["action"] = "rename"
    with pytest.raises(SyncConflict):
        engine.sync_round()
    assert record["content"] == "服务器改过"


def test_receipt_recovery_rejects_unrelated_state(tmp_path, local_db, monkeypatch):
    client, (service, engine) = make_mapped(tmp_path, local_db, ("正文",))
    client.edit_remote("remote-1", "服务器改过")

    def boom():
        raise OSError("磁盘写入失败")

    monkeypatch.setattr(service, "_save_state", boom)
    with pytest.raises(OSError):
        engine.sync_round()
    monkeypatch.undo()

    # 磁盘状态被改成收据之外的第三种样子，恢复必须拒绝而不是猜
    import json

    tampered = json.loads((tmp_path / "sync-state.json").read_text(encoding="utf-8"))
    tampered["cursor"] = tampered["cursor"] + 5
    (tmp_path / "sync-state.json").write_text(json.dumps(tampered), encoding="utf-8")
    retry_service, retry = rebuild_engine(tmp_path, local_db, client)
    with pytest.raises(SyncConflict, match="SQLite 与同步状态不一致"):
        retry.sync_round()


def test_new_server_diary_with_unparsable_time_still_lands(tmp_path, local_db):
    client, (service, engine) = make_mapped(tmp_path, local_db, ("已有",))
    broken = remote_diary("remote-new", "2026-09-21", "服务器新写的")
    client.seed({**broken, "updated_at": "不是时间"})
    engine.sync_round()
    landed = [d for d in local_db.get_all_diaries_with_tags() if d["content"] == "服务器新写的"]
    assert len(landed) == 1
    # 时间不可解析时退回日期零点，不能挡住新日记落地
    assert landed[0]["date"] == "2026-09-21 00:00:00"
