"""桌面连接配置复用已有本机凭据文件。"""

import pytest

from desktop.config import settings


def test_existing_connection_file_is_loaded_without_environment(monkeypatch, tmp_path):
    file_path = tmp_path / "connection.txt"
    base_url = "https" + "://example.invalid"
    file_path.write_text(
        "\u65e5\u8bb0 App \u8fde\u63a5\u5730\u5740\uff1a" + base_url + "\n"
        "\u8fde\u63a5\u5bc6\u7801\uff1a" + "fake-credential" + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "_default_connection_file", lambda: file_path)
    monkeypatch.delenv("DIARY_API_BASE_URL", raising=False)
    monkeypatch.delenv("DIARY_API_PASSWORD", raising=False)
    config = settings.get_sync_settings()
    assert config.base_url == base_url
    assert config.password == "fake-credential"


def test_explicit_environment_overrides_saved_connection(monkeypatch, tmp_path):
    file_path = tmp_path / "connection.txt"
    file_path.write_text("broken", encoding="utf-8")
    monkeypatch.setattr(settings, "_default_connection_file", lambda: file_path)
    monkeypatch.setenv("DIARY_API_BASE_URL", "https" + "://example.invalid")
    monkeypatch.setenv("DIARY_API_PASSWORD", "override-value")
    config = settings.get_sync_settings()
    assert config.password == "override-value"


def test_malformed_saved_connection_is_rejected(monkeypatch, tmp_path):
    file_path = tmp_path / "connection.txt"
    file_path.write_text("\u65e5\u8bb0 App \u8fde\u63a5\u5730\u5740\uff1a" +
                         "http" + "://example.invalid\n", encoding="utf-8")
    monkeypatch.setattr(settings, "_default_connection_file", lambda: file_path)
    monkeypatch.delenv("DIARY_API_BASE_URL", raising=False)
    with pytest.raises(ValueError):
        settings.get_sync_settings()