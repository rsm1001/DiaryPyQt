"""Verify desktop-to-server sync respects the server's batch limit."""
import hashlib

import pytest

from desktop.sync.service import DesktopSyncService, SyncConflict


class FakeClient:
    def __init__(self):
        self.batch_sizes = []

    def push(self, operations):
        self.batch_sizes.append(len(operations))
        return {"items": [{"entity_id": op["entity_id"], "status": "accepted",
                          "data": {"content_hash": "sha256:" + hashlib.sha256(op["data"]["content"].encode("utf-8")).hexdigest(), "version": 1}}
                         for op in operations]}

    def list_diaries(self, offset, limit=100):
        return {"items": []}

    def list_all_diaries(self):
        return []

    def pull(self, cursor):
        return {"items": [], "next_cursor": cursor}


def test_sync_chunks_and_persists_each_batch(tmp_path):
    diaries = [{"id": i, "date": "2026-09-26", "content": f"Entry {i}",
                "tags": ["learning"]} for i in range(205)]
    client = FakeClient()
    service = DesktopSyncService(client, tmp_path / "state.json")
    result = service.sync_once(diaries)
    assert client.batch_sizes == [100, 100, 5]
    assert len(result["pushed"]) == 205
    assert len(service.state["entries"]) == 205
    assert service.build_push_operations(diaries) == []
    assert (tmp_path / "state.json").exists()



def test_upload_uses_tag_names_and_tracks_date_and_tag_changes(tmp_path):
    diary = {"id": 1, "date": "2026-09-26 10:00", "content": "正文",
             "tags": [{"id": 4, "name": "标签"}]}
    client = FakeClient()
    service = DesktopSyncService(client, tmp_path / "state.json")
    service.sync_once([diary])
    assert client.batch_sizes == [1]
    assert service.build_push_operations([diary]) == []

    diary["tags"] = [{"id": 5, "name": "新标签"}]
    operations = service.build_push_operations([diary])
    assert operations[0]["data"]["tags"] == ["新标签"]
    service.sync_once([diary])
    assert service.build_push_operations([diary]) == []

    diary["date"] = "2026-09-27 09:00"
    operations = service.build_push_operations([diary])
    assert operations[0]["data"]["date"] == "2026-09-27"


def test_remote_edit_after_push_does_not_advance_cursor(tmp_path):
    class ConcurrentEditClient(FakeClient):
        def __init__(self):
            super().__init__()
            self.pull_count = 0
            self.last_operation = None

        def push(self, operations):
            self.last_operation = operations[0]
            return super().push(operations)

        def pull(self, cursor):
            self.pull_count += 1
            if self.pull_count == 1:
                return {"items": [], "next_cursor": cursor}
            op = self.last_operation
            changed = {**op["data"], "id": op["entity_id"], "version": 2,
                       "content_hash": "sha256:" + hashlib.sha256("其他设备修改".encode("utf-8")).hexdigest()}
            return {"items": [{"change": {"entity_id": op["entity_id"], "action": "upsert"},
                               "data": changed}], "next_cursor": 1}

    client = ConcurrentEditClient()
    service = DesktopSyncService(client, tmp_path / "state.json")
    with pytest.raises(SyncConflict, match="其他设备"):
        service.sync_once([{"id": 1, "date": "2026-09-26", "content": "正文", "tags": []}])
    assert service.state["cursor"] == 0


def test_mapped_legacy_upload_is_disabled(tmp_path):
    client = FakeClient()
    service = DesktopSyncService(client, tmp_path / "state.json")
    service.state["mapped"] = True
    with pytest.raises(SyncConflict, match="尚未开放安全上传"):
        service.sync_once([{"id": 1, "date": "2026-09-26", "content": "正文", "tags": []}])
    assert client.batch_sizes == []
