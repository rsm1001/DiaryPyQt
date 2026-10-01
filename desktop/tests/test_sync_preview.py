"""桌面端只读检查和连接鉴权测试。"""
import base64
import io
import json
import urllib.error

import pytest

from desktop.sync.client import DiaryServerClient, RemoteApiError
from desktop.sync.preview import preview_remote


class FakeClient:
    """模拟服务端增量游标及历史重复变更。"""

    def __init__(self, pages):
        self.pages = pages
        self.cursors = []

    def pull(self, cursor):
        self.cursors.append(cursor)
        return self.pages[cursor]


def change(cursor, diary_id, content=None):
    return {
        "change": {"cursor": cursor, "entity_id": diary_id, "entity_type": "diary"},
        "data": None if content is None else {
            "date": "2026-09-26", "content": content, "deleted_at": None,
        },
    }


def test_preview_pages_and_deduplicates_without_writes():
    client = FakeClient({
        0: {"items": [change(1, "a", "旧版"), change(2, "b", "删除前")], "next_cursor": 2},
        2: {"items": [change(3, "a", "最新版"), change(4, "b")], "next_cursor": 4},
        4: {"items": [], "next_cursor": 4},
    })
    diaries = [{"date": "2026-09-26 08:00", "content": "最新版"}]
    assert preview_remote(client, diaries) == {
        "local": 1, "remote": 1, "same_content": 1, "changes": 4,
    }
    assert client.cursors == [0, 2, 4]


def test_preview_rejects_stuck_cursor():
    client = FakeClient({0: {"items": [change(1, "a", "正文")], "next_cursor": 0}})
    with pytest.raises(ValueError, match="游标"):
        preview_remote(client, [])


def test_client_uses_basic_auth_and_request_id(monkeypatch):
    observed = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return json.dumps({"items": [], "next_cursor": 0}).encode("utf-8")

    def fake_urlopen(req, timeout):
        observed.append((req, timeout))
        return Response()

    monkeypatch.setattr("desktop.sync.client.request.urlopen", fake_urlopen)
    monkeypatch.setenv("DIARY_API_BASE_URL", "https:" + "//test.invalid")
    monkeypatch.setenv("DIARY_API_PASSWORD", "测试密码")
    client = DiaryServerClient.from_environment()
    client.pull(0)
    req, timeout = observed[0]
    assert req.get_header("Authorization") == "Basic " + base64.b64encode(
        "diary:测试密码".encode("utf-8")
    ).decode("ascii")
    assert req.get_header("X-request-id")
    assert timeout == 15


def test_client_unwraps_nested_error_details(monkeypatch):
    """服务端错误体把业务字段放在 details 里，客户端必须拆出来。

    版本冲突降级依赖 server_data；整包当 details 会让自动同步拿不到
    可对照的服务器版本，只能整轮中止。
    """
    def fake_urlopen(req, timeout):
        body = json.dumps({
            "code": "DIARY_VERSION_CONFLICT",
            "message": "日记版本冲突",
            "request_id": "req-1",
            "details": {"server_version": 7, "server_data": {"id": "remote-1"}},
        }).encode("utf-8")
        raise urllib.error.HTTPError(req.full_url, 409, "Conflict", {}, io.BytesIO(body))

    monkeypatch.setattr("desktop.sync.client.request.urlopen", fake_urlopen)
    client = DiaryServerClient("mock://test")
    with pytest.raises(RemoteApiError) as caught:
        client.pull(0)
    assert caught.value.status_code == 409
    assert caught.value.error_code == "DIARY_VERSION_CONFLICT"
    assert caught.value.details["server_version"] == 7
    assert caught.value.details["server_data"]["id"] == "remote-1"


def test_client_requires_opt_in_address(monkeypatch, tmp_path):
    monkeypatch.delenv("DIARY_API_BASE_URL", raising=False)
    monkeypatch.setattr("desktop.config.settings._default_connection_file",
                        lambda: tmp_path / "missing-connection.txt")
    with pytest.raises(ValueError, match="DIARY_API_BASE_URL"):
        DiaryServerClient.from_environment()


def test_client_refuses_password_without_tls():
    with pytest.raises(ValueError, match='HTTPS'):
        DiaryServerClient('mock://test', password='x')


def test_client_paginates_full_list_and_rejects_duplicate_ids(monkeypatch):
    client = DiaryServerClient("mock://test")
    offsets = []

    def pages(offset, limit=100):
        offsets.append(offset)
        if offset == 0:
            return {"items": [{"id": str(i)} for i in range(100)]}
        return {"items": [{"id": "unique"}]}

    monkeypatch.setattr(client, "list_diaries", pages)
    assert len(client.list_all_diaries()) == 101
    assert offsets == [0, 100]

    monkeypatch.setattr(client, "list_diaries", lambda offset, limit=100: {
        "items": [{"id": "same"}] * 100,
    })
    with pytest.raises(ValueError, match="分页重复"):
        client.list_all_diaries()
