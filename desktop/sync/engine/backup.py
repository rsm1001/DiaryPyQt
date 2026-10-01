"""自动同步前的一次性备份。

正文同步会改写用户真实日记库，首次启用前必须留下可回滚的快照；
备份失败就拒绝本轮写入，宁可不同步也不能没有退路。
"""
import logging
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


def _snapshot_sqlite(source: Path, destination: Path) -> None:
    """用 SQLite 在线备份接口生成一致性快照（含 WAL 中未合并的内容）。"""
    source_connection = sqlite3.connect(str(source))
    destination_connection = sqlite3.connect(str(destination))
    try:
        source_connection.backup(destination_connection)
    finally:
        destination_connection.close()
        source_connection.close()


def _prune(backup_dir: Path, keep: int) -> None:
    """只保留最近若干份，避免长期占用磁盘。"""
    snapshots = sorted((path for path in backup_dir.glob("sync-*") if path.is_dir()),
                       key=lambda path: path.name)
    for stale in snapshots[:-keep]:
        shutil.rmtree(stale, ignore_errors=True)


class SyncBackupManager:
    """把主库、回收站库与同步状态一起快照到带时间戳的目录。"""

    def __init__(self, db_path, trash_db_path, state_path, backup_dir, keep: int = 5) -> None:
        self.db_path = Path(db_path)
        self.trash_db_path = Path(trash_db_path)
        self.state_path = Path(state_path)
        self.backup_dir = Path(backup_dir)
        self.keep = keep

    def create(self) -> Path:
        """创建一份备份并返回目录；任何失败都向上抛出以阻止同步。"""
        request_id = str(uuid4())
        target = self.backup_dir / f"sync-{datetime.now():%Y%m%d-%H%M%S}-{request_id[:8]}"
        target.mkdir(parents=True, exist_ok=False)
        _snapshot_sqlite(self.db_path, target / self.db_path.name)
        if self.trash_db_path.is_file():
            _snapshot_sqlite(self.trash_db_path, target / self.trash_db_path.name)
        if self.state_path.is_file():
            shutil.copy2(self.state_path, target / self.state_path.name)
        _prune(self.backup_dir, self.keep)
        logger.info("自动同步前备份完成", extra={"request_id": request_id, "path": str(target)})
        return target


def build_backup_manager(settings, db_path) -> Optional[SyncBackupManager]:
    """按同步配置组装备份管理器；未配置备份目录时返回 None。"""
    if settings.backup_dir is None:
        return None
    db_path = Path(db_path)
    return SyncBackupManager(
        db_path=db_path,
        trash_db_path=db_path.with_name(f"trash_{db_path.stem}.db"),
        state_path=settings.state_path,
        backup_dir=settings.backup_dir,
        keep=settings.backup_keep,
    )
