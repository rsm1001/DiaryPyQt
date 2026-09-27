"""桌面同步连接配置。"""
import os
from dataclasses import dataclass
from pathlib import Path


VIEW_SYNC_INTERVAL_MS = 5 * 60 * 1000


@dataclass(frozen=True)
class SyncSettings:
    """仅在用户启用服务器检查时读取的连接参数。"""

    base_url: str
    timeout: float
    password: str
    state_path: Path


def _default_connection_file() -> Path:
    """复用现有本机日记连接文件。"""
    return Path.home() / "Desktop" / "DiaryPyQt-\u8fde\u63a5\u5bc6\u7801.txt"


def _desktop_connection() -> tuple[str, str]:
    file_path = _default_connection_file()
    if not file_path.is_file():
        return "", ""
    try:
        fields = dict(
            line.split("\uff1a", 1) for line in file_path.read_text(encoding="utf-8-sig").splitlines()
            if "\uff1a" in line
        )
    except (OSError, UnicodeError) as exc:
        raise ValueError("桌面日记连接文件无法读取") from exc
    address = fields.get("\u65e5\u8bb0 App \u8fde\u63a5\u5730\u5740", "").strip()
    password = fields.get("\u8fde\u63a5\u5bc6\u7801", "").strip()
    if not address or not password or not address.startswith("https://"):
        raise ValueError("桌面日记连接文件不完整或不是 HTTPS")
    return address, password


def get_sync_settings() -> SyncSettings:
    """缺少服务器地址时保持桌面端纯本地模式。"""
    base_url = os.getenv("DIARY_API_BASE_URL", "").strip()
    password = os.getenv("DIARY_API_PASSWORD", "")
    if not base_url:
        base_url, saved_password = _desktop_connection()
        password = password or saved_password
    if not base_url:
        raise ValueError("未配置 DIARY_API_BASE_URL，无法连接日记服务器")
    configured_state = os.getenv("DIARY_SYNC_STATE_PATH", "").strip()
    default_root = Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / "DiaryPyQt"
    return SyncSettings(
        base_url=base_url,
        timeout=float(os.getenv("DIARY_API_TIMEOUT", "15")),
        password=password,
        state_path=Path(configured_state) if configured_state else default_root / "sync-state.json",
    )
