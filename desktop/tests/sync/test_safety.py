"""自动同步的安全闸门：预演、批量阈值与拒绝脏数据。"""
import pytest

from desktop.sync.service import DesktopSyncService, SyncConflict
from desktop.tests.sync.harness import (BackupSpy, FakeClient, content_hash, make_engine,
                                        make_mapped, seed_local)


def test_plan_only_writes_nothing(tmp_path, local_db):
    client, (service, engine) = make_mapped(tmp_path, local_db, ("正文",))
    new = seed_local(local_db, "新增未上传")
    state_before = (tmp_path / "sync-state.json").read_text(encoding="utf-8")
    result = engine.sync_round(plan_only=True)
    assert result["plan_only"] is True
    assert result["planned_push"] == 1
    assert client.pushed == []
    assert (tmp_path / "sync-state.json").read_text(encoding="utf-8") == state_before
    assert str(new["id"]) not in service.state["entries"]


def test_mass_create_stops_before_uploading(tmp_path, local_db):
    client, (service, engine) = make_mapped(tmp_path, local_db, ("正文",))
    for index in range(4):
        seed_local(local_db, f"批量新增 {index}")
    engine.max_auto_push = 2
    with pytest.raises(SyncConflict, match="超过自动同步上限"):
        engine.sync_round()
    assert client.pushed == []


def test_unmapped_state_is_refused(tmp_path, local_db):
    client = FakeClient()
    seed_local(local_db, "正文")
    service = DesktopSyncService(client, tmp_path / "sync-state.json")
    engine = make_engine(service, local_db)
    with pytest.raises(SyncConflict, match="尚未建立一对一映射"):
        engine.sync_round()


def test_corrupt_mapping_is_refused(tmp_path, local_db):
    client, (service, engine) = make_mapped(tmp_path, local_db, ("甲", "乙"))
    for entry in service.state["entries"].values():
        entry["remote_id"] = "同一个服务器 ID"
    service.save_state()
    with pytest.raises(SyncConflict, match="映射重复"):
        make_engine(service, local_db).sync_round()


def test_remote_content_hash_mismatch_is_rejected(tmp_path, local_db):
    client, (service, engine) = make_mapped(tmp_path, local_db, ("正文",))
    diary = local_db.get_all_diaries()[0]
    record = client.edit_remote("remote-1", "服务器改过")
    client.records["remote-1"] = {**record, "content_hash": content_hash("别的正文")}
    with pytest.raises(SyncConflict, match="正文哈希不一致"):
        engine.sync_round()
    assert local_db.get_diary_by_id(diary["id"])["content"] == "正文"


def test_mismatched_local_database_cannot_wipe_server(tmp_path, local_db):
    """本地库与映射对不上时会把整库都当成"已删除"，闸门必须拦住。"""
    contents = tuple(f"第 {index} 篇" for index in range(25))
    client, (service, engine) = make_mapped(tmp_path, local_db, contents)
    for diary in local_db.get_all_diaries():
        local_db.move_to_trash(diary["id"])

    with pytest.raises(SyncConflict, match="待删除服务器日记"):
        engine.sync_round()
    assert client.pushed == []
    assert all(record["deleted_at"] is None for record in client.records.values())


def test_backup_runs_once_before_first_write(tmp_path, local_db):
    client, (service, engine) = make_mapped(tmp_path, local_db, ("正文",))
    spy = BackupSpy()
    engine.backup = spy
    seed_local(local_db, "新增待上传")

    engine.sync_round()
    assert spy.calls == 1
    assert service.state["backup_done"] is True
    # 已经备份过就不该每次同步都再备一份
    seed_local(local_db, "又一篇待上传")
    engine.sync_round()
    assert spy.calls == 1


def test_missing_backup_configuration_blocks_writes(tmp_path, local_db):
    client, (service, engine) = make_mapped(tmp_path, local_db, ("正文",))
    engine.backup = None
    seed_local(local_db, "新增待上传")
    with pytest.raises(SyncConflict, match="未配置同步前备份"):
        engine.sync_round()
    assert client.pushed == []


def test_backup_failure_blocks_writes(tmp_path, local_db):
    client, (service, engine) = make_mapped(tmp_path, local_db, ("正文",))

    def broken_backup():
        raise OSError("磁盘空间不足")

    engine.backup = broken_backup
    seed_local(local_db, "新增待上传")
    with pytest.raises(OSError):
        engine.sync_round()
    assert client.pushed == []
    assert service.state.get("backup_done") is None
