"""日记后端基础和音频接口测试。"""
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from server.audio_repository import AudioRepository
from server.audio_service import AudioService
from server.config.settings import Settings
from server.main import create_app
from server.repository import DiaryRepository
from server.service import DiaryService


class FakeTTSProvider:
    """写入可验证的测试音频内容。"""

    async def synthesize(self, text, output_path, voice):
        output_path.write_bytes(f"audio:{text}".encode("utf-8"))
        return 1234


def build_settings(temp_dir):
    """创建测试配置。"""
    return Settings(
        host="test-host",
        port=8010,
        db_path=Path(temp_dir) / "diary.db",
        audio_root=Path(temp_dir) / "audio",
        default_voice_name="test-voice",
        allowed_origins=["*"],
    )


def build_audio_service(settings):
    """创建使用测试 TTS 的音频服务。"""
    diary_service = DiaryService(DiaryRepository(settings.db_path))
    return diary_service, AudioService(
        diary_service=diary_service,
        audio_repository=AudioRepository(settings.db_path),
        provider=FakeTTSProvider(),
        audio_root=settings.audio_root,
        default_voice_name=settings.default_voice_name,
    )


def test_diary_crud_and_version_conflict():
    """验证日记 CRUD、标签和版本冲突。"""
    with TemporaryDirectory() as temp_dir:
        settings = build_settings(temp_dir)
        with TestClient(create_app(settings=settings)) as client:
            created = client.post(
                "/api/v1/diaries",
                json={"date": "2026-09-25", "content": "测试日记", "tags": ["学习"]},
            )
            assert created.status_code == 201
            diary = created.json()
            assert diary["version"] == 1
            assert diary["tags"] == ["学习"]

            diary_id = diary["id"]
            updated = client.patch(
                f"/api/v1/diaries/{diary_id}",
                json={"content": "更新后的测试日记", "version": 1},
            )
            assert updated.status_code == 200
            assert updated.json()["version"] == 2

            conflict = client.patch(
                f"/api/v1/diaries/{diary_id}",
                json={"content": "冲突内容", "version": 1},
            )
            assert conflict.status_code == 409
            assert conflict.json()["code"] == "DIARY_VERSION_CONFLICT"

            tags = client.get("/api/v1/tags")
            assert tags.status_code == 200
            assert tags.json()["items"][0]["name"] == "学习"

            deleted = client.delete(f"/api/v1/diaries/{diary_id}?version=2")
            assert deleted.status_code == 204
            assert client.get(f"/api/v1/diaries/{diary_id}").status_code == 404


def test_health_returns_request_id():
    """验证健康检查和请求追踪 ID。"""
    with TemporaryDirectory() as temp_dir:
        settings = build_settings(temp_dir)
        with TestClient(create_app(settings=settings)) as client:
            response = client.get("/health", headers={"X-Request-ID": "test-request"})
            assert response.status_code == 200
            assert response.json()["status"] == "ok"
            assert response.headers["X-Request-ID"] == "test-request"


def test_audio_generation_cache_update_and_download():
    """验证音频生成、缓存复用、日记更新和下载。"""
    with TemporaryDirectory() as temp_dir:
        settings = build_settings(temp_dir)
        diary_service, audio_service = build_audio_service(settings)
        app = create_app(settings=settings, service=diary_service, audio_service=audio_service)
        with TestClient(app) as client:
            created = client.post(
                "/api/v1/diaries",
                json={"date": "2026-09-25", "content": "第一版内容", "tags": []},
            )
            diary_id = created.json()["id"]

            voices = client.get("/api/v1/voices")
            assert voices.status_code == 200
            assert len(voices.json()["items"]) == 1

            generated = client.post(f"/api/v1/diaries/{diary_id}/audio/generate", json={})
            assert generated.status_code == 200, generated.text
            first_asset = generated.json()
            assert first_asset["duration_ms"] == 1234
            assert first_asset["status"] == "ready"

            cached = client.post(f"/api/v1/diaries/{diary_id}/audio/generate", json={})
            assert cached.json()["id"] == first_asset["id"]

            downloaded = client.get(first_asset["download_url"])
            assert downloaded.status_code == 200
            assert downloaded.content == "audio:第一版内容".encode("utf-8")

            updated = client.patch(
                f"/api/v1/diaries/{diary_id}",
                json={"content": "第二版内容", "version": 1},
            )
            assert updated.status_code == 200

            regenerated = client.post(f"/api/v1/diaries/{diary_id}/audio/generate", json={})
            assert regenerated.status_code == 200
            assert regenerated.json()["id"] != first_asset["id"]

            assets = client.get(f"/api/v1/diaries/{diary_id}/audio")
            assert len(assets.json()["items"]) == 1


def test_sync_and_playback_records():
    """?????????????????"""
    with TemporaryDirectory() as temp_dir:
        settings = build_settings(temp_dir)
        with TestClient(create_app(settings=settings)) as client:
            created = client.post(
                "/api/v1/diaries",
                json={"date": "2026-09-25", "content": "????", "tags": []},
            )
            assert created.status_code == 201
            diary = created.json()
            diary_id = diary["id"]

            pulled = client.get("/api/v1/sync/pull?cursor=0")
            assert pulled.status_code == 200
            assert pulled.json()["items"][0]["change"]["entity_id"] == diary_id

            playback = client.post(
                "/api/v1/playback-records",
                json={
                    "device_id": "test-device", "diary_id": diary_id, "voice_id": "default",
                    "round_number": 1, "position_ms": 1200, "status": "paused",
                    "updated_at": "2026-09-25T12:00:00Z",
                },
            )
            assert playback.status_code == 200
            assert playback.json()["position_ms"] == 1200

            pushed = client.post(
                "/api/v1/sync/push",
                json={
                    "operations": [{
                        "entity_type": "diary", "entity_id": diary_id, "action": "upsert",
                        "base_version": 1,
                        "data": {"date": "2026-09-25", "content": "????", "tags": []},
                    }]
                },
            )
            assert pushed.status_code == 200
            assert pushed.json()["items"][0]["data"]["version"] == 2

def test_sync_retries_are_idempotent_for_create_and_delete():
    """离线队列重试同一操作时不重复创建，也不因重复删除失败。"""
    with TemporaryDirectory() as temp_dir:
        settings = build_settings(temp_dir)
        with TestClient(create_app(settings=settings)) as client:
            created = client.post(
                "/api/v1/diaries",
                json={"date": "2026-09-26", "content": "幂等日记", "tags": ["队列"]},
            ).json()
            operation = {
                "entity_type": "diary",
                "entity_id": created["id"],
                "action": "upsert",
                "base_version": None,
                "data": {"date": created["date"], "content": created["content"],
                         "tags": created["tags"]},
            }
            retried = client.post("/api/v1/sync/push", json={"operations": [operation]})
            assert retried.status_code == 200
            assert retried.json()["items"][0]["status"] == "accepted"
            assert client.get("/api/v1/diaries").json()["items"]

            deleted = client.delete(
                f"/api/v1/diaries/{created['id']}?version={created['version']}"
            )
            assert deleted.status_code == 204
            repeated_delete = client.post(
                "/api/v1/sync/push",
                json={"operations": [{
                    "entity_type": "diary", "entity_id": created["id"],
                    "action": "delete", "base_version": created["version"], "data": {},
                }]},
            )
            assert repeated_delete.status_code == 200
            assert repeated_delete.json()["items"][0]["status"] == "accepted"

def test_tag_management_rejects_deleting_used_tags():
    """标签管理 API 保留桌面端的重命名和占用保护。"""
    with TemporaryDirectory() as temp_dir:
        settings = build_settings(temp_dir)
        with TestClient(create_app(settings=settings)) as client:
            created = client.post("/api/v1/tags", json={"name": "学习"})
            assert created.status_code == 201
            tag = created.json()
            duplicate = client.post("/api/v1/tags", json={"name": "学习"})
            assert duplicate.status_code == 201
            assert duplicate.json()["id"] == tag["id"]

            renamed = client.patch(
                f"/api/v1/tags/{tag['id']}", json={"name": "研究"}
            )
            assert renamed.status_code == 200
            assert renamed.json()["name"] == "研究"

            diary = client.post(
                "/api/v1/diaries",
                json={"date": "2026-09-26", "content": "标签使用", "tags": ["研究"]},
            )
            assert diary.status_code == 201
            blocked = client.delete(f"/api/v1/tags/{tag['id']}")
            assert blocked.status_code == 409
            assert blocked.json()["code"] == "TAG_IN_USE"

            deleted_diary = client.delete(
                f"/api/v1/diaries/{diary.json()['id']}?version=1"
            )
            assert deleted_diary.status_code == 204
            deleted_tag = client.delete(f"/api/v1/tags/{tag['id']}")
            assert deleted_tag.status_code == 204
            assert all(item["id"] != tag["id"] for item in client.get("/api/v1/tags").json()["items"])

def test_view_tracking_updates_diary_response_and_statistics():
    """查看事件写入独立统计表，并反映到日记响应。"""
    with TemporaryDirectory() as temp_dir:
        settings = build_settings(temp_dir)
        with TestClient(create_app(settings=settings)) as client:
            created = client.post(
                "/api/v1/diaries",
                json={"date": "2026-09-26", "content": "查看统计", "tags": []},
            )
            diary = created.json()
            assert diary["view_count"] == 0

            first = client.post(f"/api/v1/diaries/{diary['id']}/view")
            second = client.post(f"/api/v1/diaries/{diary['id']}/view")
            assert first.status_code == 200
            assert second.json()["view_count"] == 2
            assert second.json()["viewed_at"]
            fetched = client.get(f"/api/v1/diaries/{diary['id']}").json()
            assert fetched["view_count"] == 2
            assert fetched["last_viewed_at"]

            stats = client.get("/api/v1/statistics")
            assert stats.status_code == 200
            assert stats.json()["total_diaries"] == 1
            assert stats.json()["total_views"] == 2
            assert stats.json()["most_viewed_id"] == diary["id"]

def test_trash_restore_and_permanent_delete():
    with TemporaryDirectory() as temp_dir:
        settings = build_settings(temp_dir)
        with TestClient(create_app(settings=settings)) as client:
            created = client.post(
                "/api/v1/diaries",
                json={"date": "2026-09-27", "content": "回收站测试", "tags": []},
            ).json()
            diary_id = created["id"]
            assert client.delete(f"/api/v1/diaries/{diary_id}?version=1").status_code == 204
            trash = client.get("/api/v1/trash")
            assert trash.status_code == 200
            assert trash.json()["items"][0]["id"] == diary_id
            restored = client.post(f"/api/v1/trash/{diary_id}/restore?version=2")
            assert restored.status_code == 200
            assert restored.json()["deleted_at"] is None
            assert client.delete(f"/api/v1/diaries/{diary_id}?version=3").status_code == 204
            assert client.delete(f"/api/v1/trash/{diary_id}").status_code == 204
            assert client.get(f"/api/v1/diaries/{diary_id}").status_code == 404
            assert client.get("/api/v1/trash").json()["items"] == []


def test_desktop_baseline_is_idempotent_and_keeps_server_views():
    with TemporaryDirectory() as temp_dir:
        settings = build_settings(temp_dir)
        with TestClient(create_app(settings=settings)) as client:
            created = client.post("/api/v1/diaries", json={
                "date": "2026-09-27", "content": "history", "tags": [],
            }).json()
            url = f"/api/v1/diaries/{created['id']}"
            client.post(url + "/view", json={
                "event_id": "mobile-one", "viewed_at": "2026-09-27T10:00:00Z",
            })
            baseline = {"source_id": "desktop-initial:" + created["id"],
                        "view_count": 12, "last_viewed_at": "2026-09-26T12:00:00Z"}
            first = client.post(url + "/view-baselines", json=baseline)
            assert first.status_code == 200
            assert first.json()["view_count"] == 13
            assert first.json()["last_viewed_at"] == "2026-09-27T10:00:00Z"
            assert client.post(url + "/view-baselines", json=baseline).json()["view_count"] == 13
            other = {**baseline, "view_count": 11}
            assert client.post(url + "/view-baselines", json=other).status_code == 409
            assert client.get(url).json()["view_count"] == 13
            client.post(url + "/view", json={
                "event_id": "mobile-two", "viewed_at": "2026-09-27T11:00:00Z",
            })
            assert client.get(url).json()["view_count"] == 14
        reopened = DiaryRepository(settings.db_path)
        assert reopened.import_view_baseline(
            created["id"], baseline["source_id"], 12, "2026-09-26T12:00:00Z"
        )["view_count"] == 14


def test_health_advertises_idempotent_view_events():
    with TemporaryDirectory() as temp_dir:
        with TestClient(create_app(settings=build_settings(temp_dir))) as client:
            health = client.get("/health")
            assert health.status_code == 200
            assert "view_event_idempotent_v1" in health.json()["capabilities"]
            assert "desktop_view_baseline_v1" in health.json()["capabilities"]


def test_view_events_are_idempotent_across_retries_and_devices():
    """断网重试与多设备提交只累加不同事件。"""
    with TemporaryDirectory() as temp_dir:
        settings = build_settings(temp_dir)
        with TestClient(create_app(settings=settings)) as client:
            first = client.post("/api/v1/diaries", json={
                "date": "2026-09-27", "content": "离线查看", "tags": [],
            }).json()["id"]
            second = client.post("/api/v1/diaries", json={
                "date": "2026-09-27", "content": "另一本", "tags": [],
            }).json()["id"]
            url = f"/api/v1/diaries/{first}/view"
            recent = {"event_id": "device-a-1", "viewed_at": "2026-09-27T12:00:00+00:00"}
            older = {"event_id": "device-b-1", "viewed_at": "2026-09-26T12:00:00+00:00"}
            assert client.post(url, json=recent).json()["view_count"] == 1
            assert client.post(url, json=recent).json()["view_count"] == 1
            assert client.post(url, json=older).json()["view_count"] == 2
            assert client.post(url, json=older).json()["viewed_at"] == "2026-09-27T12:00:00Z"
            assert client.post(f"/api/v1/diaries/{second}/view", json=recent).status_code == 409
            assert client.get("/api/v1/statistics").json()["total_views"] == 2
            assert client.post(url, json={"event_id": "naive", "viewed_at": "2026-09-27T12:00:00"}).status_code == 422

        # 重开数据库时重试仍只计一次。
        repository = DiaryRepository(settings.db_path)
        assert repository.record_view(first, recent["viewed_at"], recent["event_id"])["view_count"] == 2
