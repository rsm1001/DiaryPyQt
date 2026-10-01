"""自动双向同步的常规路径：首轮无操作、回声抑制、上下行与删除传播。"""
from desktop.tests.sync.harness import make_mapped, seed_local


def test_first_round_is_noop_for_existing_mapping(tmp_path, local_db):
    client, (service, engine) = make_mapped(tmp_path, local_db, ("甲", "乙"))
    before = dict(service.state["entries"])
    result = engine.sync_round()
    assert result.get("pushed", 0) == 0
    assert client.pushed == []
    assert service.state["entries"] == before
    assert service.state["cursor"] == client.cursor


def test_echo_of_own_push_is_suppressed(tmp_path, local_db):
    client, (service, engine) = make_mapped(tmp_path, local_db, ("正文",))
    diary = local_db.get_all_diaries()[0]
    local_db.update_diary_with_tags(diary["id"], "改过的正文", [])
    engine.sync_round()
    assert len(client.pushed) == 1
    remote_id = client.pushed[0][0]["entity_id"]

    # 下一轮即使服务器把这条又当成变更返回，也不该再写本地
    client._record(remote_id, "upsert", client.records[remote_id]["version"],
                   client.records[remote_id]["updated_at"])
    result = engine.sync_round()
    assert result.get("updated", 0) == 0
    assert local_db.get_diary_by_id(diary["id"])["content"] == "改过的正文"


def test_local_create_is_pushed(tmp_path, local_db):
    client, (service, engine) = make_mapped(tmp_path, local_db, ("已有",))
    new = seed_local(local_db, "新写的日记", ("新标签",))
    engine.sync_round()
    created = [op for batch in client.pushed for op in batch if op["base_version"] is None]
    assert len(created) == 1
    assert created[0]["data"]["content"] == "新写的日记"
    assert str(new["id"]) in service.state["entries"]


def test_local_edit_is_pushed_with_base_version(tmp_path, local_db):
    client, (service, engine) = make_mapped(tmp_path, local_db, ("正文",))
    diary = local_db.get_all_diaries()[0]
    key = str(diary["id"])
    base = service.state["entries"][key]["version"]
    tag_id = local_db.add_tag("标签")["id"]
    assert local_db.update_diary_with_tags(diary["id"], "本地改过", [tag_id])
    engine.sync_round()
    update = [op for batch in client.pushed for op in batch if op["base_version"] is not None][0]
    assert update["base_version"] == base
    assert client.records[service.state["entries"][key]["remote_id"]]["content"] == "本地改过"


def test_local_delete_pushes_delete_and_converges(tmp_path, local_db):
    client, (service, engine) = make_mapped(tmp_path, local_db, ("要删的",))
    diary = local_db.get_all_diaries()[0]
    key = str(diary["id"])
    remote_id = service.state["entries"][key]["remote_id"]
    local_db.move_to_trash(diary["id"])

    engine.sync_round()
    assert client.records[remote_id]["deleted_at"] is not None
    assert key not in service.state["entries"]

    # 第二轮不应再产生任何操作
    client.pushed.clear()
    engine.sync_round()
    assert client.pushed == []


def test_server_create_lands_as_new_local_diary(tmp_path, local_db):
    from desktop.tests.sync.harness import remote_diary

    client, (service, engine) = make_mapped(tmp_path, local_db, ("已有",))
    record = client.seed(remote_diary("remote-new", "2026-09-21", "服务器新写的", ("标签A",)))
    engine.sync_round()
    landed = [d for d in local_db.get_all_diaries_with_tags() if d["content"] == "服务器新写的"]
    assert len(landed) == 1
    assert landed[0]["date"][:10] == record["date"]
    assert [tag["name"] for tag in landed[0]["tags"]] == ["标签A"]
    assert str(landed[0]["id"]) in service.state["entries"]


def test_server_edit_applies_when_local_untouched(tmp_path, local_db):
    client, (service, engine) = make_mapped(tmp_path, local_db, ("正文",))
    diary = local_db.get_all_diaries()[0]
    client.edit_remote("remote-1", "服务器改过")
    engine.sync_round()
    assert local_db.get_diary_by_id(diary["id"])["content"] == "服务器改过"


def test_server_delete_moves_local_to_trash(tmp_path, local_db):
    client, (service, engine) = make_mapped(tmp_path, local_db, ("会被删",))
    diary = local_db.get_all_diaries()[0]
    key = str(diary["id"])
    client.delete_remote("remote-1")
    engine.sync_round()
    assert local_db.get_diary_by_id(diary["id"]) is None
    assert local_db.get_trash_count() == 1
    assert key not in service.state["entries"]


def test_downlink_and_uplink_in_same_round_stay_consistent(tmp_path, local_db):
    client, (service, engine) = make_mapped(tmp_path, local_db, ("甲", "乙"))
    by_remote = {entry["remote_id"]: int(key)
                 for key, entry in service.state["entries"].items()}
    local_db.update_diary_with_tags(by_remote["remote-2"], "本地改的乙", [])
    client.edit_remote("remote-1", "服务器改的甲")

    result = engine.sync_round()
    assert result["updated"] == 1
    assert result["pushed"] == 1
    assert local_db.get_diary_by_id(by_remote["remote-1"])["content"] == "服务器改的甲"
    assert client.records["remote-2"]["content"] == "本地改的乙"

    # 下行会替换整个状态对象，推送回执必须落在最新映射上，否则第二轮会重复上传
    entries = service.state["entries"]
    for remote_id, local_id in by_remote.items():
        assert entries[str(local_id)]["version"] == client.records[remote_id]["version"]
    client.pushed.clear()
    engine.sync_round()
    assert client.pushed == []


def test_timing_normalizes_local_naive_and_utc_server_time():
    from datetime import datetime, timezone

    from desktop.sync.engine.timing import parse_desktop_time, pick_newer, to_local_string

    # 用同一转换生成桌面本地时间，避免测试依赖运行机器的时区
    local_text = to_local_string("2026-09-29T12:00:00Z")
    assert parse_desktop_time(local_text) == datetime(2026, 9, 29, 12, tzinfo=timezone.utc)
    assert pick_newer(local_text, "2026-09-29T11:59:00Z", 0) == "local"
    assert pick_newer(local_text, "2026-09-29T12:01:00Z", 0) == "remote"
    assert pick_newer(local_text, "2026-09-29T12:00:30Z", 120) == "tie"
    assert pick_newer("不是时间", "2026-09-29T12:00:00Z", 120) == "unknown"
    assert pick_newer(local_text, None, 120) == "unknown"
