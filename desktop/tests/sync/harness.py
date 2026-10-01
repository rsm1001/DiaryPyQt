"""双向同步测试的共用脚手架：服务端替身与临时库构造。"""
import hashlib
from datetime import datetime, timezone

from desktop.sync.client import RemoteApiError
from desktop.sync.engine.service import BidirectionalSyncService
from desktop.sync.local_repository import LocalDiaryRepository
from desktop.sync.reconcile import plan_mapping
from desktop.sync.service import DesktopSyncService


def content_hash(content):
    return "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()


def utc(moment):
    return moment.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def remote_diary(remote_id, date, content, tags=(), version=1, updated_at=None, deleted_at=None):
    now = updated_at or utc(datetime.now(timezone.utc))
    return {"id": remote_id, "date": date, "content": content, "content_hash": content_hash(content),
            "version": version, "tags": sorted(tags), "created_at": now, "updated_at": now,
            "deleted_at": deleted_at}


class FakeClient:
    """最小可用的服务端替身：维护记录与变更游标，并可强制制造 409。"""

    def __init__(self):
        self.records = {}
        self.changes = []
        self.cursor = 0
        self.pushed = []
        self.forced_conflict = {}
        self.page_size = 100

    # ---------------- 服务端数据准备 ----------------
    def seed(self, record):
        self.records[record["id"]] = dict(record)
        self._record(record["id"], "upsert", record["version"], record["updated_at"])
        return self.records[record["id"]]

    def edit_remote(self, remote_id, content, updated_at=None, tags=None):
        """模拟别的设备改了服务器。"""
        record = self.records[remote_id]
        moment = updated_at or utc(datetime.now(timezone.utc))
        record = {**record, "content": content, "content_hash": content_hash(content),
                  "version": record["version"] + 1, "updated_at": moment,
                  "tags": sorted(tags) if tags is not None else record["tags"]}
        self.records[remote_id] = record
        self._record(remote_id, "upsert", record["version"], moment)
        return record

    def delete_remote(self, remote_id, updated_at=None):
        record = self.records[remote_id]
        moment = updated_at or utc(datetime.now(timezone.utc))
        record = {**record, "version": record["version"] + 1, "updated_at": moment,
                  "deleted_at": moment}
        self.records[remote_id] = record
        self._record(remote_id, "delete", record["version"], moment)
        return record

    def _record(self, remote_id, action, version, updated_at):
        self.cursor += 1
        self.changes.append({"cursor": self.cursor, "entity_type": "diary",
                             "entity_id": remote_id, "action": action,
                             "version": version, "updated_at": updated_at})

    # ---------------- 客户端接口 ----------------
    def list_all_diaries(self):
        return [dict(record) for record in self.records.values()]

    def pull(self, cursor):
        items = []
        for change in self.changes:
            if change["cursor"] <= cursor:
                continue
            record = self.records.get(change["entity_id"])
            items.append({"change": dict(change), "data": dict(record) if record else None})
            if len(items) >= self.page_size:
                break
        next_cursor = items[-1]["change"]["cursor"] if items else cursor
        return {"items": items, "next_cursor": next_cursor}

    def push(self, operations):
        results = []
        for operation in operations:
            entity_id = operation["entity_id"]
            if entity_id in self.forced_conflict:
                server = self.forced_conflict.pop(entity_id)
                raise RemoteApiError("日记版本冲突", 409,
                                     {"server_version": server["version"], "server_data": server})
            current = self.records.get(entity_id)
            data = operation.get("data") or {}
            if operation["action"] == "delete":
                if current and not current.get("deleted_at"):
                    current = {**current, "version": current["version"] + 1,
                               "deleted_at": utc(datetime.now(timezone.utc))}
                    self.records[entity_id] = current
                    self._record(entity_id, "delete", current["version"], current["updated_at"])
                results.append({"entity_id": entity_id, "status": "accepted"})
                continue
            if current is None:
                current = remote_diary(entity_id, data["date"], data["content"], data["tags"])
            else:
                same = (current["date"] == data["date"] and current["content"] == data["content"]
                        and current["tags"] == sorted(data["tags"]))
                base_version = operation.get("base_version")
                if not same and (base_version is None or current["version"] != base_version):
                    raise RemoteApiError("日记版本冲突", 409, {
                        "server_version": current["version"], "server_data": dict(current)})
                if not same:
                    current = {**current, "date": data["date"], "content": data["content"],
                               "content_hash": content_hash(data["content"]),
                               "tags": sorted(data["tags"]),
                               "version": current["version"] + 1,
                               "updated_at": utc(datetime.now(timezone.utc))}
            self.records[entity_id] = current
            self._record(entity_id, "upsert", current["version"], current["updated_at"])
            results.append({"entity_id": entity_id, "status": "accepted", "data": dict(current)})
        self.pushed.append(operations)
        return {"items": results}


def seed_local(manager, content, tags=()):
    tag_ids = [manager.add_tag(name)["id"] for name in tags]
    diary = manager.add_diary_with_tags(content, tag_ids)
    diary["tags"] = manager.get_tags_by_diary_id(diary["id"])
    return diary


def build(tmp_path, manager, client):
    """按现有测试的做法建立一对一映射并返回引擎。"""
    diaries = manager.get_all_diaries_with_tags()
    plan = plan_mapping(diaries, client.list_all_diaries())
    assert plan.complete
    service = DesktopSyncService(client, tmp_path / "sync-state.json")
    service.state = {"mapped": True, "cursor": client.cursor, "entries": plan.matches}
    service.save_state()
    engine = BidirectionalSyncService(service, LocalDiaryRepository(manager.db_path),
                                      manager.move_to_trash, backup=BackupSpy())
    return service, engine


class BackupSpy:
    """记录备份调用次数，供测试确认"写前必先备份"。"""

    def __init__(self):
        self.calls = 0

    def __call__(self):
        self.calls += 1


def make_engine(service, manager, backup=None):
    """用给定服务对象构造引擎，不重建状态（用于校验前置条件的测试）。"""
    return BidirectionalSyncService(service, LocalDiaryRepository(manager.db_path),
                                    manager.move_to_trash,
                                    backup=backup if backup is not None else BackupSpy())


def rebuild_engine(tmp_path, manager, client, backup=None):
    """按磁盘上的状态文件重建服务与引擎，用于崩溃恢复类测试。"""
    service = DesktopSyncService(client, tmp_path / "sync-state.json")
    engine = BidirectionalSyncService(service, LocalDiaryRepository(manager.db_path),
                                      manager.move_to_trash,
                                      backup=backup if backup is not None else BackupSpy())
    return service, engine


def make_mapped(tmp_path, local_db, contents=("正文",)):
    """建立本地与服务器的唯一映射；服务器日期取本地日期前 10 位。"""
    client = FakeClient()
    for index, content in enumerate(contents):
        diary = seed_local(local_db, content)
        client.seed(remote_diary(f"remote-{index + 1}", diary["date"][:10], content))
    return client, build(tmp_path, local_db, client)
