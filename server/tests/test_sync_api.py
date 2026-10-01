"""同步推送接口：客户端 UUID 新建、幂等与版本冲突降级。"""
from tempfile import TemporaryDirectory
from uuid import uuid4

from fastapi.testclient import TestClient

from server.main import create_app
from server.tests.support import build_settings


def test_sync_push_creates_diary_with_client_uuid():
    """电脑端首次上传用本地推导的 UUID，服务端必须按该 ID 建库。"""
    with TemporaryDirectory() as temp_dir:
        settings = build_settings(temp_dir)
        with TestClient(create_app(settings=settings)) as client:
            remote_id = str(uuid4())
            pushed = client.post("/api/v1/sync/push", json={"operations": [{
                "entity_type": "diary", "entity_id": remote_id, "action": "upsert",
                "base_version": None,
                "data": {"date": "2026-09-26", "content": "电脑新写的", "tags": ["电脑"]},
            }]})
            assert pushed.status_code == 200
            item = pushed.json()["items"][0]
            assert item["status"] == "accepted"
            assert item["data"]["id"] == remote_id
            assert item["data"]["version"] == 1
            assert item["data"]["content"] == "电脑新写的"

            # 新建必须同时产生一条可供其他设备拉取的变更
            pulled = client.get("/api/v1/sync/pull?cursor=0").json()
            assert [entry["change"]["entity_id"] for entry in pulled["items"]] == [remote_id]
            assert client.get(f"/api/v1/diaries/{remote_id}").json()["tags"] == ["电脑"]


def test_sync_push_create_retry_does_not_duplicate():
    """同一篇新日记重试上传必须幂等，不能建出第二篇或提升版本。"""
    with TemporaryDirectory() as temp_dir:
        settings = build_settings(temp_dir)
        with TestClient(create_app(settings=settings)) as client:
            remote_id = str(uuid4())
            operation = {
                "entity_type": "diary", "entity_id": remote_id, "action": "upsert",
                "base_version": None,
                "data": {"date": "2026-09-26", "content": "重试正文", "tags": []},
            }
            assert client.post("/api/v1/sync/push",
                               json={"operations": [operation]}).status_code == 200
            retried = client.post("/api/v1/sync/push", json={"operations": [operation]})
            assert retried.status_code == 200
            assert retried.json()["items"][0]["data"]["version"] == 1
            assert len(client.get("/api/v1/diaries").json()["items"]) == 1


def test_sync_push_occupied_id_without_base_version_conflicts():
    """ID 已被别的日记占用时不能静默覆盖，必须返回可核对的冲突数据。"""
    with TemporaryDirectory() as temp_dir:
        settings = build_settings(temp_dir)
        with TestClient(create_app(settings=settings)) as client:
            existing = client.post(
                "/api/v1/diaries",
                json={"date": "2026-09-26", "content": "服务器已有", "tags": []},
            ).json()
            conflict = client.post("/api/v1/sync/push", json={"operations": [{
                "entity_type": "diary", "entity_id": existing["id"], "action": "upsert",
                "base_version": None,
                "data": {"date": "2026-09-26", "content": "电脑以为的新日记", "tags": []},
            }]})
            assert conflict.status_code == 409
            details = conflict.json()["details"]
            assert conflict.json()["code"] == "DIARY_VERSION_CONFLICT"
            assert details["server_version"] == existing["version"]
            assert details["server_data"]["id"] == existing["id"]
            assert details["server_data"]["content"] == "服务器已有"
            # 被拒绝的上传不能改动服务器内容
            assert client.get(f"/api/v1/diaries/{existing['id']}").json()["content"] == "服务器已有"


def test_sync_push_stale_base_version_conflicts():
    """本地基线落后时必须拒绝，并回传服务器当前版本供客户端降级。"""
    with TemporaryDirectory() as temp_dir:
        settings = build_settings(temp_dir)
        with TestClient(create_app(settings=settings)) as client:
            created = client.post(
                "/api/v1/diaries",
                json={"date": "2026-09-26", "content": "第一版", "tags": []},
            ).json()
            updated = client.patch(
                f"/api/v1/diaries/{created['id']}",
                json={"content": "第二版", "version": created["version"]},
            ).json()
            assert updated["version"] == created["version"] + 1

            conflict = client.post("/api/v1/sync/push", json={"operations": [{
                "entity_type": "diary", "entity_id": created["id"], "action": "upsert",
                "base_version": created["version"],
                "data": {"date": created["date"], "content": "本地基于旧版的修改", "tags": []},
            }]})
            assert conflict.status_code == 409
            details = conflict.json()["details"]
            assert details["server_version"] == updated["version"]
            assert details["server_data"]["content"] == "第二版"


def test_sync_push_batch_conflict_identifies_the_entity():
    """批量推送遇冲突会中断整批，必须回传冲突实体供客户端逐条降级。"""
    with TemporaryDirectory() as temp_dir:
        settings = build_settings(temp_dir)
        with TestClient(create_app(settings=settings)) as client:
            existing = client.post(
                "/api/v1/diaries",
                json={"date": "2026-09-26", "content": "会冲突的", "tags": []},
            ).json()
            new_id = str(uuid4())
            conflict = client.post("/api/v1/sync/push", json={"operations": [
                {"entity_type": "diary", "entity_id": new_id, "action": "upsert",
                 "base_version": None,
                 "data": {"date": "2026-09-27", "content": "同批的新日记", "tags": []}},
                {"entity_type": "diary", "entity_id": existing["id"], "action": "upsert",
                 "base_version": None,
                 "data": {"date": "2026-09-26", "content": "冲突正文", "tags": []}},
            ]})
            assert conflict.status_code == 409
            assert conflict.json()["details"]["server_data"]["id"] == existing["id"]
