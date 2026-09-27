"""电脑历史查看统计首次上传及后续双端增量的隔离测试。"""
import hashlib
import json
import sqlite3
from copy import deepcopy
from datetime import datetime, timezone

import pytest

from desktop.sync.client import DiaryServerClient, RemoteApiError
from desktop.sync.reconcile import plan_mapping
from desktop.sync.service import DesktopSyncService, SyncConflict
from desktop.sync.view_repository import LocalViewRepository
from models.enhanced_database import EnhancedDatabaseManager


def remote(diary, remote_id, count, viewed_at):
    return {"id": remote_id, "date": diary["date"][:10], "content": diary["content"],
            "content_hash": "sha256:" + hashlib.sha256(diary["content"].encode()).hexdigest(),
            "tags": [], "version": 1, "deleted_at": None,
            "view_count": count, "last_viewed_at": viewed_at}


class ViewClient:
    def __init__(self, diaries):
        self.diaries = diaries
        self.baselines = {}
        self.baseline_requests = 0
        self.events = set()
        self.sent = []
        self.snapshots = 0
        self.old_server = False
        self.lose_baseline_reply = False
        self.lose_event_reply = False

    def list_all_diaries(self):
        self.snapshots += 1
        return deepcopy(self.diaries)

    def require_idempotent_views(self):
        if self.old_server:
            raise RemoteApiError("legacy server")

    def _diary(self, remote_id):
        return next(item for item in self.diaries if item["id"] == remote_id)

    def _advance(self, record, count, viewed_at):
        record["view_count"] += count
        if viewed_at:
            parsed = datetime.fromisoformat(viewed_at.replace("Z", "+00:00"))
            older = record["last_viewed_at"]
            if older is None or parsed > datetime.fromisoformat(older.replace("Z", "+00:00")):
                record["last_viewed_at"] = parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    def import_view_baseline(self, remote_id, source_id, view_count, last_viewed_at):
        self.baseline_requests += 1
        payload = (remote_id, view_count, last_viewed_at)
        if source_id in self.baselines:
            if self.baselines[source_id] != payload:
                raise RemoteApiError("baseline conflict", 409)
        else:
            self.baselines[source_id] = payload
            self._advance(self._diary(remote_id), view_count, last_viewed_at)
        if self.lose_baseline_reply:
            self.lose_baseline_reply = False
            raise ConnectionError("baseline reply lost")
        return deepcopy(self._diary(remote_id))

    def record_view(self, remote_id, event_id, viewed_at):
        self.sent.append(event_id)
        if event_id not in self.events:
            self.events.add(event_id)
            self._advance(self._diary(remote_id), 1, viewed_at)
        if self.lose_event_reply:
            self.lose_event_reply = False
            raise ConnectionError("event reply lost")
        return deepcopy(self._diary(remote_id))


@pytest.fixture
def case(tmp_path):
    manager = EnhancedDatabaseManager(str(tmp_path / "desktop.db"))
    one, two = manager.add_diary("first"), manager.add_diary("second")
    with sqlite3.connect(manager.db_path) as connection:
        connection.execute("UPDATE diaries SET view_count = ?, last_viewed_at = ? WHERE id = ?",
                           (12, "2026-09-27 15:00:00", one["id"]))
        connection.execute("UPDATE diaries SET view_count = ?, last_viewed_at = ? WHERE id = ?",
                           (3, "2026-09-27 08:00:00", two["id"]))
    client = ViewClient([remote(one, "remote-1", 2, "2026-09-27T09:00:00Z"),
                         remote(two, "remote-2", 0, None)])
    service = DesktopSyncService(client, tmp_path / "sync-state.json")
    service.state = {"mapped": True, "cursor": 7,
                     "entries": plan_mapping([one, two], client.diaries).matches}
    service._save_state()
    yield manager, service, client, one, two
    manager.close()


def test_computer_history_goes_to_server_once_then_new_remote_views_arrive(case):
    manager, service, client, one, two = case
    repo = LocalViewRepository(manager.db_path)
    assert service.sync_views(repo) == {"matched": 2, "changed": 1, "added": 2,
                                       "baseline_count": 15}
    assert [entry["view_count"] for entry in client.diaries] == [14, 3]
    assert manager.get_diary_by_id(one["id"])["view_count"] == 14
    assert manager.get_diary_by_id(two["id"])["view_count"] == 3
    assert manager.get_diary_by_id(one["id"])["last_viewed_at"] == "2026-09-27 17:00:00"
    repeated = service.sync_views(repo)
    assert repeated["added"] == 0
    assert repeated["baseline_count"] == 0
    assert client.baseline_requests == 2
    assert len(client.baselines) == 2
    assert [entry["view_count"] for entry in client.diaries] == [14, 3]
    client.record_view("remote-1", "mobile-event", "2026-09-27T10:00:00Z")
    assert service.sync_views(repo)["added"] == 1
    assert manager.get_diary_by_id(one["id"])["view_count"] == 15
    assert json.loads(service.state_path.read_text(encoding="utf-8"))["cursor"] == 7


def test_lost_baseline_reply_is_retryable_without_duplicate_upload(case):
    manager, service, client, one, _ = case
    repo = LocalViewRepository(manager.db_path)
    client.lose_baseline_reply = True
    with pytest.raises(ConnectionError, match="baseline reply lost"):
        service.sync_views(repo)
    assert repo.has_checkpoint()
    assert sum(item["view_count"] for item in client.diaries) in (5, 14)
    manager.increment_view_count(one["id"])
    assert len(repo.read_pending()) == 1
    assert service.sync_views(repo)["baseline_count"] == 15
    assert client.diaries[0]["view_count"] == 15
    assert manager.get_diary_by_id(one["id"])["view_count"] == 15
    assert repo.read_pending() == []


def test_lost_acknowledgements_and_other_device_are_counted_once(case):
    manager, service, client, one, _ = case
    repo = LocalViewRepository(manager.db_path)
    service.sync_views(repo)
    manager.increment_view_count(one["id"])
    manager.increment_view_count(one["id"])
    pending = repo.read_pending()
    for event in pending:
        client.record_view("remote-1", event["event_id"], event["viewed_at"])
    client.record_view("remote-1", "other-device", pending[0]["viewed_at"])
    assert service.sync_views(repo)["added"] == 1
    assert manager.get_diary_by_id(one["id"])["view_count"] == 17
    assert client.diaries[0]["view_count"] == 17
    assert repo.read_pending() == []
    assert service.sync_views(repo)["added"] == 0


def test_old_server_cannot_create_baseline_or_upload_queue(case):
    manager, service, client, one, _ = case
    client.old_server = True
    repo = LocalViewRepository(manager.db_path)
    with pytest.raises(RemoteApiError):
        service.sync_views(repo)
    assert not repo.has_checkpoint()
    assert client.baselines == {}
    assert manager.get_diary_by_id(one["id"])["view_count"] == 12


def test_regression_unstable_snapshot_and_mapping_fail_closed(case):
    manager, service, client, one, _ = case
    repo = LocalViewRepository(manager.db_path)
    service.sync_views(repo)
    client.diaries[0]["view_count"] = 13
    with pytest.raises(SyncConflict):
        service.sync_views(repo)
    assert manager.get_diary_by_id(one["id"])["view_count"] == 14
    client.diaries[0]["view_count"] = 14
    client.diaries[0]["date"] = "2000-01-01"
    with pytest.raises(SyncConflict):
        service.sync_views(repo)
    assert manager.get_diary_by_id(one["id"])["view_count"] == 14


def test_unstable_snapshot_does_not_prepare_baseline(case, monkeypatch):
    manager, service, client, one, _ = case
    original = client.list_all_diaries

    def moving():
        snapshot = original()
        if client.snapshots == 2:
            snapshot[0]["view_count"] += 1
        return snapshot

    monkeypatch.setattr(client, "list_all_diaries", moving)
    with pytest.raises(SyncConflict):
        service.sync_views(LocalViewRepository(manager.db_path))
    assert not LocalViewRepository(manager.db_path).has_checkpoint()
    assert manager.get_diary_by_id(one["id"])["view_count"] == 12


def test_mapped_state_required(case):
    manager, service, client, _, _ = case
    service.state_path.unlink()
    with pytest.raises(SyncConflict):
        service.sync_views(LocalViewRepository(manager.db_path))
    assert client.baselines == {}


def test_client_requires_both_server_capabilities(monkeypatch):
    client = DiaryServerClient("")
    monkeypatch.setattr(client, "_request", lambda method, path: {
        "capabilities": ["view_event_idempotent_v1"]})
    with pytest.raises(RemoteApiError):
        client.require_idempotent_views()
    monkeypatch.setattr(client, "_request", lambda method, path: {
        "capabilities": ["view_event_idempotent_v1", "desktop_view_baseline_v1"]})
    client.require_idempotent_views()

def test_legacy_downstream_checkpoint_cannot_reimport_history(case):
    manager, service, client, one, _ = case
    with sqlite3.connect(manager.db_path) as connection:
        connection.execute(
            "CREATE TABLE desktop_view_sync_state "
            "(local_id INTEGER PRIMARY KEY, remote_id TEXT UNIQUE, remote_count INTEGER)"
        )
        connection.execute(
            "INSERT INTO desktop_view_sync_state VALUES (?, ?, ?)",
            (one["id"], "remote-1", 2),
        )
    with pytest.raises(SyncConflict):
        service.sync_views(LocalViewRepository(manager.db_path))
    assert client.baselines == {}
    assert manager.get_diary_by_id(one["id"])["view_count"] == 12
