"""PyQt 桌面端同步：状态管理、HTTP 适配与后台任务。"""

from .service import DesktopSyncService, SyncConflict

__all__ = ["DesktopSyncService", "SyncConflict"]
