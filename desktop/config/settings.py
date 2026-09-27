"""桌面同步连接配置。"""
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SyncSettings:
    """仅在用户启用服务器检查时读取的连接参数。"""

    base_url: str
    timeout: float
    password: str
    state_path: Path


def get_sync_settings() -> SyncSettings:
    """缺少服务器地址时保持桌面端纯本地模式。"""
    base_url = os.getenv("DIARY_API_BASE_URL", "").strip()
    if not base_url:
        raise ValueError("未配置 DIARY_API_BASE_URL，无法连接日记服务器")
    configured_state = os.getenv("DIARY_SYNC_STATE_PATH", "").strip()
    default_root = Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / "DiaryPyQt"
    return SyncSettings(
        base_url=base_url,
        timeout=float(os.getenv("DIARY_API_TIMEOUT", "15")),
        password=os.getenv("DIARY_API_PASSWORD", ""),
        state_path=Path(configured_state) if configured_state else default_root / "sync-state.json",
    )
