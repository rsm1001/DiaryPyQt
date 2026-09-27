"""在工作线程中执行只读同步检查，避免网络请求冻结界面。"""
import logging
from pathlib import Path
from typing import Any, Dict, List
from uuid import uuid4

from PyQt6.QtCore import QThread, pyqtSignal

from .client import DiaryServerClient
from .local_repository import LocalDiaryRepository
from .service import DesktopSyncService
from .preview import preview_remote
from .reconcile import plan_mapping

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
    """??????????????????"""

    completed = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, operation: str, diaries: List[Dict[str, Any]],
                 db_path: str, state_path: Path, parent=None):
        super().__init__(parent)
        self.operation = operation
        self.diaries = diaries
        self.db_path = db_path
        self.state_path = Path(state_path)

    def run(self) -> None:
        request_id = str(uuid4())
        try:
            service = DesktopSyncService(
                DiaryServerClient.from_environment(), self.state_path
            )
            if self.operation == "preview":
                plan = service.plan_initial_mapping(self.diaries)
                result = {
                    "operation": self.operation,
                    "local": len(self.diaries),
                    "matched": len(plan.matches),
                    "local_only": len(plan.local_only),
                    "remote_only": len(plan.remote_only),
                    "ambiguous": len(plan.ambiguous),
                    "mapped": service.state.get("mapped") is True,
                    "state_path": str(self.state_path),
                }
            elif self.operation == "map":
                plan = service.initialize_mapping(self.diaries)
                result = {"operation": self.operation, "mapped": len(plan.matches)}
            elif self.operation == "pull":
                result = service.pull_once(LocalDiaryRepository(Path(self.db_path)))
                result["operation"] = self.operation
            else:
                raise ValueError("????????")
        except Exception:
            logger.exception("??????????", extra={"request_id": request_id,
                                                     "operation": self.operation})
            self.failed.emit("?????????????????????")
        else:
            logger.info("??????????", extra={"request_id": request_id,
                                                     "operation": self.operation})
            self.completed.emit(result)
