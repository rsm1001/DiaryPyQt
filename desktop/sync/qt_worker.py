"""在工作线程中执行同步，避免网络请求冻结界面。"""
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

from PyQt6.QtCore import QThread, pyqtSignal

from desktop.config.settings import get_sync_settings

from .client import DiaryServerClient
from .engine.backup import build_backup_manager
from .engine.service import BidirectionalSyncService
from .local_repository import LocalDiaryRepository
from .preview import preview_remote
from .reconcile import plan_mapping
from .service import DesktopSyncService
from .view_repository import LocalViewRepository

logger = logging.getLogger(__name__)


class SyncPreviewWorker(QThread):
    """只发出统计结果，不上传日记或修改同步状态。"""

    completed = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, diaries: List[Dict[str, Any]], parent=None):
        super().__init__(parent)
        self.diaries = diaries

    def run(self) -> None:
        request_id = str(uuid4())
        try:
            client = DiaryServerClient.from_environment()
            result = preview_remote(client, self.diaries)
            plan = plan_mapping(self.diaries, client.list_all_diaries())
            result.update({"matched": len(plan.matches), "local_only": len(plan.local_only),
                           "remote_only": len(plan.remote_only), "ambiguous": len(plan.ambiguous)})
        except Exception:
            logger.exception("桌面端服务器同步检查失败", extra={"request_id": request_id})
            self.failed.emit("服务器检查失败，请核对连接配置或查看日志。")
        else:
            logger.info("桌面端服务器同步检查完成", extra={"request_id": request_id, **result})
            self.completed.emit(result)


class SyncReviewWorker(QThread):
    """后台执行正文自动同步、预演和查看记录同步。"""

    completed = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, operation: str, diaries: List[Dict[str, Any]],
                 db_path: str, state_path: Path,
                 trash_callback: Optional[Callable[[int], Any]] = None, parent=None):
        super().__init__(parent)
        self.operation = operation
        self.diaries = diaries
        self.db_path = db_path
        self.state_path = Path(state_path)
        self.trash_callback = trash_callback

    def run(self) -> None:
        request_id = str(uuid4())
        try:
            settings = get_sync_settings()
            service = DesktopSyncService(DiaryServerClient.from_environment(), self.state_path)
            if self.operation == "preview":
                result = self._preview(service)
            elif self.operation == "map":
                plan = service.initialize_mapping(self.diaries)
                result = {"operation": self.operation, "mapped": len(plan.matches)}
            elif self.operation in ("sync", "scan"):
                result = self._sync(service, settings, plan_only=self.operation == "scan")
            elif self.operation == "views":
                result = service.sync_views(LocalViewRepository(Path(self.db_path)))
                result["operation"] = self.operation
            else:
                raise ValueError("未知的服务器同步操作")
        except Exception:
            logger.exception("桌面服务器同步操作失败", extra={"request_id": request_id,
                                                     "operation": self.operation})
            self.failed.emit("服务器同步失败，请核对映射与连接配置，详情见日志。")
        else:
            logger.info("桌面服务器同步操作完成", extra={"request_id": request_id,
                                                     "operation": self.operation})
            self.completed.emit(result)

    def _preview(self, service: DesktopSyncService) -> Dict[str, Any]:
        plan = service.plan_initial_mapping(self.diaries)
        return {
            "operation": self.operation,
            "local": len(self.diaries),
            "matched": len(plan.matches),
            "local_only": len(plan.local_only),
            "remote_only": len(plan.remote_only),
            "ambiguous": len(plan.ambiguous),
            "mapped": service.state.get("mapped") is True,
            "state_path": str(self.state_path),
        }

    def _sync(self, service: DesktopSyncService, settings, plan_only: bool) -> Dict[str, Any]:
        """组装引擎并执行一轮；删除传播必须拿到回收站入口才允许继续。"""
        if self.trash_callback is None:
            raise ValueError("缺少回收站入口，无法安全同步删除")
        backup = build_backup_manager(settings, self.db_path)
        engine = BidirectionalSyncService(
            service, LocalDiaryRepository(Path(self.db_path)), self.trash_callback,
            backup=backup.create if backup is not None else None,
            max_auto_push=settings.max_auto_push,
            max_auto_trash=settings.max_auto_trash,
            max_auto_delete=settings.max_auto_delete,
            epsilon_seconds=settings.timestamp_epsilon_seconds)
        result = engine.sync_round(plan_only=plan_only)
        result["operation"] = self.operation
        return result
