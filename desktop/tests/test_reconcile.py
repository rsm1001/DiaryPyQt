"""首次映射只允许无歧义的一对一配对，且上传必须先检查下行变更。"""
import hashlib
import json

import pytest

from desktop.sync.reconcile import payload_digest, plan_mapping
from desktop.sync.service import DesktopSyncService, SyncConflict


def local(diary_id, content, tags=None):
    return {"id": diary_id, "date": "2026-09-26 10:00", "content": content,
            "tags": [{"name": name} for name in (tags or [])]}


def remote(diary_id, content, tags=None):
    return {"id": diary_id, "date": "2026-09-26", "content": content,
            "tags": tags or [], "version": 3,
            "content_hash": "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()}


class FakeClient:
    def __init__(self, diaries, pending=False):
        self.diaries = diaries
        self.pending = pending
        self.list_offsets = []
        self.pushed = []

    def list_diaries(self, offset, limit=100):
        self.list_offsets.append(offset)
        return {"items": self.diaries[offset:offset + limit]}

    def list_all_diaries(self):
        items = []
        while True:
            batch = self.list_diaries(len(items))["items"]
            items.extend(batch)
            if len(batch) < 100:
                return items
    def pull(self, cursor):
        if self.pending:
            return {"items": [{"change": {"entity_id": "elsewhere"}}], "next_cursor": cursor + 1}
        return {"items": [], "next_cursor": cursor}

    def push(self, operations):
        self.pushed.extend(operations)
        return {"items": []}


def test_exact_mapping_requires_matching_tags_and_unique_identity():
    plan = plan_mapping(
        [local(1, "正文", ["甲", "乙"]), local(2, "新日记")],
        [remote("server-1", "正文", ["乙", "甲"]), remote("server-2", "其他")],
    )
    assert plan.matches == {"1": {"remote_id": "server-1", "version": 3,
                                  "content_hash": remote("server-1", "正文")["content_hash"],
                                  "date": "2026-09-26",
                                  "payload_hash": payload_digest(local(1, "正文", ["甲", "乙"]))}}
    assert plan.local_only == ["2"]
    assert plan.remote_only == ["server-2"]
    assert not plan.complete


def test_duplicate_content_is_ambiguous_even_when_counts_equal():
    plan = plan_mapping([local(1, "一样"), local(2, "一样")],
                        [remote("a", "一样"), remote("b", "一样")])
    assert not plan.complete
    assert plan.ambiguous == ["1", "2"]
    assert not plan.matches


def test_first_mapping_is_atomic_and_does_not_skip_remote_history(tmp_path):
    client = FakeClient([remote("server-id", "正文", ["标签"])])
    state_path = tmp_path / "state.json"
    service = DesktopSyncService(client, state_path)
    plan = service.initialize_mapping([local(3, "正文", ["标签"])])
    assert plan.complete
    assert client.list_offsets == [0, 0]
    assert json.loads(state_path.read_text(encoding="utf-8")) == {
        "cursor": 0, "entries": plan.matches, "mapped": True,
    }
    assert client.pushed == []
    with pytest.raises(SyncConflict, match="已有同步状态"):
        service.initialize_mapping([local(3, "正文", ["标签"])])


def test_mismatch_does_not_write_mapping(tmp_path):
    client = FakeClient([remote("other", "不一样")])
    service = DesktopSyncService(client, tmp_path / "state.json")
    with pytest.raises(SyncConflict, match="人工核对"):
        service.initialize_mapping([local(1, "正文")])
    assert not service.state_path.exists()
    assert client.pushed == []


def test_existing_broken_state_never_resets_to_empty(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("{broken", encoding="utf-8")
    with pytest.raises(SyncConflict, match="状态损坏"):
        DesktopSyncService(FakeClient([]), path)
    assert path.read_text(encoding="utf-8") == "{broken"


def test_pending_downstream_change_blocks_upload_before_any_write(tmp_path):
    client = FakeClient([], pending=True)
    service = DesktopSyncService(client, tmp_path / "state.json")
    with pytest.raises(SyncConflict, match="未写入本地"):
        service.sync_once([local(1, "正文")])
    assert client.pushed == []
    assert service.state["cursor"] == 0
    assert not service.state_path.exists()

class ChangingClient(FakeClient):
    def __init__(self, diaries):
        super().__init__(diaries)
        self.calls = 0

    def list_diaries(self, offset, limit=100):
        self.calls += 1
        if self.calls == 2:
            return {"items": [remote("server-id", "被修改") ]}
        return super().list_diaries(offset, limit)


def test_changed_server_snapshot_blocks_mapping(tmp_path):
    client = ChangingClient([remote("server-id", "正文")])
    service = DesktopSyncService(client, tmp_path / "state.json")
    with pytest.raises(SyncConflict, match="发生变化"):
        service.initialize_mapping([local(1, "正文")])
    assert not service.state_path.exists()


def test_bad_remote_content_hash_cannot_be_mapped(tmp_path):
    broken = remote("server-id", "正文")
    broken["content_hash"] = "sha256:bad"
    service = DesktopSyncService(FakeClient([broken]), tmp_path / "state.json")
    with pytest.raises(ValueError, match="哈希异常"):
        service.initialize_mapping([local(1, "正文")])
    assert not service.state_path.exists()


def test_existing_server_blocks_unmapped_legacy_upload(tmp_path):
    client = FakeClient([remote("already-here", "正文")])
    service = DesktopSyncService(client, tmp_path / "state.json")
    with pytest.raises(SyncConflict, match="映射未经验证"):
        service.sync_once([local(1, "正文")])
    assert client.pushed == []


def test_snapshot_paginates_all_existing_remote_diaries(tmp_path):
    client = FakeClient([remote(str(i), f"内容-{i}") for i in range(205)])
    service = DesktopSyncService(client, tmp_path / "state.json")
    plan = service.plan_initial_mapping([local(i, f"内容-{i}") for i in range(205)])
    assert plan.complete
    assert len(plan.matches) == 205
    assert client.list_offsets == [0, 100, 200]
    assert not service.state_path.exists()


def test_duplicate_local_ids_are_not_silently_overwritten():
    with pytest.raises(ValueError, match="ID 重复"):
        plan_mapping([local(1, "甲"), local(1, "乙")],
                     [remote("a", "甲"), remote("b", "乙")])
