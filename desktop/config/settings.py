"""桌面同步连接配置。"""
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

logger = logging.getLogger(__name__)

# 查看记录的自动同步间隔（沿用既有行为）
VIEW_SYNC_INTERVAL_MS = 5 * 60 * 1000
# 正文与标签的自动同步间隔
CONTENT_SYNC_INTERVAL_MS = 5 * 60 * 1000
# 本地改动后延迟触发一轮，避免连续编辑时反复联网
LOCAL_EDIT_SYNC_DEBOUNCE_MS = 3 * 1000
# 单轮允许自动上传的新日记数上限，超过即停下等人工确认
MAX_AUTO_PUSH = 50
# 单轮允许自动移入回收站的日记数上限
MAX_AUTO_TRASH = 20
# 单轮允许向服务器传播的删除数上限，防止本地库与映射不匹配时整库误删
MAX_AUTO_DELETE = 20
# 两端修改时间差在此范围内的判为"无法分辨"，一律不覆盖
TIMESTAMP_EPSILON_SECONDS = 120
# 自动同步前保留的数据库备份份数
BACKUP_KEEP = 5


@dataclass(frozen=True)
class SyncSettings:
    """仅在用户启用服务器检查时读取的连接参数。"""

    base_url: str
    timeout: float
    password: str
    state_path: Path
    content_sync_interval_ms: int = CONTENT_SYNC_INTERVAL_MS
    local_edit_debounce_ms: int = LOCAL_EDIT_SYNC_DEBOUNCE_MS
    max_auto_push: int = MAX_AUTO_PUSH
    max_auto_trash: int = MAX_AUTO_TRASH
    max_auto_delete: int = MAX_AUTO_DELETE
    timestamp_epsilon_seconds: int = TIMESTAMP_EPSILON_SECONDS
    backup_dir: Path = None
    backup_keep: int = BACKUP_KEEP


def _default_connection_file() -> Path:
    """复用现有本机日记连接文件。"""
    return Path.home() / "Desktop" / "DiaryPyQt-连接密码.txt"


def _desktop_connection() -> tuple[str, str]:
    file_path = _default_connection_file()
    if not file_path.is_file():
        return "", ""
    try:
        fields = dict(
            line.split("：", 1) for line in file_path.read_text(encoding="utf-8-sig").splitlines()
            if "：" in line
        )
    except (OSError, UnicodeError) as exc:
        raise ValueError("桌面日记连接文件无法读取") from exc
    address = fields.get("日记 App 连接地址", "").strip()
    password = fields.get("连接密码", "").strip()
    if not address or not password or not address.startswith("https://"):
        raise ValueError("桌面日记连接文件不完整或不是 HTTPS")
    return address, password


def _default_local_root() -> Path:
    return Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / "DiaryPyQt"


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
    local_root = _default_local_root()
    configured_backup = os.getenv("DIARY_SYNC_BACKUP_DIR", "").strip()
    return SyncSettings(
        base_url=base_url,
        timeout=float(os.getenv("DIARY_API_TIMEOUT", "15")),
        password=password,
        state_path=Path(configured_state) if configured_state else local_root / "sync-state.json",
        backup_dir=Path(configured_backup) if configured_backup else local_root / "backups",
    )


def _prefs_path() -> Path:
    return _default_local_root() / "sync-prefs.json"


def is_content_sync_enabled() -> bool:
    """正文自动同步开关，默认开启；环境变量优先于本地偏好。"""
    override = os.getenv("DIARY_CONTENT_SYNC_ENABLED", "").strip().lower()
    if override in ("0", "false", "no", "off"):
        return False
    if override in ("1", "true", "yes", "on"):
        return True
    path = _prefs_path()
    if not path.is_file():
        return True
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("content_sync_enabled") is not False
    except (OSError, ValueError):
        logger.warning("桌面同步偏好无法读取，按开启处理",
                       extra={"request_id": str(uuid4()), "path": str(path)})
        return True


def set_content_sync_enabled(enabled: bool) -> None:
    """记住用户的自动同步开关；写失败不阻断界面操作。"""
    path = _prefs_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"content_sync_enabled": bool(enabled)}), encoding="utf-8")
    except OSError:
        logger.warning("桌面同步偏好无法保存", extra={"request_id": str(uuid4()), "path": str(path)})
