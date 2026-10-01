"""主窗口的同步协调：定时器、后台任务、状态展示与冲突提示。

正文同步是自动的，界面只负责三件事：按配置起停定时器、把后台结果写进
状态栏、需要人工介入时把冲突摆出来。主窗口因此只保留装配与委托。
"""
import logging
from functools import partial

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QMessageBox

from desktop.config.settings import (CONTENT_SYNC_INTERVAL_MS, LOCAL_EDIT_SYNC_DEBOUNCE_MS,
                                     VIEW_SYNC_INTERVAL_MS, get_sync_settings,
                                     is_content_sync_enabled, set_content_sync_enabled)
from desktop.sync.engine.service import read_status
from desktop.sync.qt_worker import SyncReviewWorker
from desktop.sync.view_repository import LocalViewRepository
from views.sync_review import SyncReviewDialog

logger = logging.getLogger(__name__)

# 需要读取本地日记内容的 operation 名称
CONTENT_OPERATIONS = ("preview", "sync", "scan", "map")


class SyncController:
    """把同步相关的界面行为从主窗口里拆出来。"""

    def __init__(self, window) -> None:
        self.window = window
        self.auto_content_sync_enabled = is_content_sync_enabled()
        self._workers = {}
        self._dialog = None
        self._view_timer = self._build_timer(VIEW_SYNC_INTERVAL_MS, self.sync_views)
        self._content_timer = self._build_timer(CONTENT_SYNC_INTERVAL_MS, self.sync_content)
        self._debounce = self._build_timer(LOCAL_EDIT_SYNC_DEBOUNCE_MS, self.sync_content,
                                           single_shot=True)

    def _build_timer(self, interval_ms: int, slot, single_shot: bool = False) -> QTimer:
        timer = QTimer(self.window)
        timer.setInterval(interval_ms)
        timer.setSingleShot(single_shot)
        timer.timeout.connect(slot)
        return timer

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------
    def start(self) -> None:
        """启动时按配置决定是否自动同步；缺少配置就保持纯本地模式。"""
        settings = self._settings()
        if settings is None:
            self._show_status("同步未配置")
            return
        self._content_timer.setInterval(settings.content_sync_interval_ms)
        self._debounce.setInterval(settings.local_edit_debounce_ms)
        if self._has_view_checkpoint():
            self._view_timer.start()
        self.set_enabled(self.auto_content_sync_enabled)

    def stop(self) -> None:
        self._content_timer.stop()
        self._view_timer.stop()
        self._debounce.stop()

    def is_busy(self) -> bool:
        return any(worker is not None and worker.isRunning()
                   for worker in self._workers.values())

    def set_enabled(self, enabled: bool) -> None:
        """切换自动同步开关并持久化；关闭时立即停表。"""
        self.auto_content_sync_enabled = bool(enabled)
        set_content_sync_enabled(self.auto_content_sync_enabled)
        if not self.auto_content_sync_enabled:
            self._content_timer.stop()
            self._show_status("自动同步已关闭")
            return
        settings = self._settings()
        if settings is None:
            self._show_status("同步未配置")
            return
        if not read_status(settings.state_path).get("mapped"):
            self._show_status("同步未就绪：尚未建立 ID 映射")
            return
        self._content_timer.start()
        QTimer.singleShot(0, self.sync_content)

    def request_sync(self) -> None:
        """本地改动后延迟触发一轮，连续编辑只发一次请求。"""
        if self._content_timer.isActive():
            self._debounce.start()

    # ------------------------------------------------------------------
    # 启动同步任务
    # ------------------------------------------------------------------
    def sync_content(self) -> None:
        self._start("sync")

    def sync_views(self) -> None:
        self._start("views")

    def scan(self) -> None:
        """预演：只算计划，不写任何数据。"""
        self._start("scan")

    def check_server(self) -> None:
        """菜单入口：只读核对服务器，不写入本地。"""
        self.open_dialog()
        self._start("preview")

    def map_entries(self) -> None:
        """仅在两侧完全一对一时手工建立 ID 映射，绝不自动配对。"""
        self._start("map")

    def _start(self, operation: str) -> None:
        if self.is_busy():
            return
        settings = self._settings()
        if settings is None:
            self._report("请先配置服务器地址，再使用同步功能")
            return
        diaries = []
        if operation in CONTENT_OPERATIONS:
            diaries = [diary.to_dict()
                       for diary in self.window.controller.get_all_diaries_with_tags()]
        worker = SyncReviewWorker(operation, diaries, self._db_path(), settings.state_path,
                                  self._move_to_trash, self.window)
        self._workers[operation] = worker
        if self._dialog is not None and operation in CONTENT_OPERATIONS:
            self._dialog.set_busy(True)
        worker.completed.connect(partial(self._on_completed, operation))
        worker.failed.connect(partial(self._on_failed, operation))
        worker.finished.connect(partial(self._on_finished, operation))
        worker.start()

    def _on_completed(self, operation: str, result: dict) -> None:
        if operation == "views":
            self._on_views_completed(result)
        elif operation == "preview":
            self._show_status("服务器日记核对完成")
            if self._dialog is not None:
                self._dialog.set_precheck(result)
        elif operation == "map":
            self._show_status(f"已建立 ID 映射（{result.get('mapped', 0)} 篇）")
            self._refresh_dialog()
        elif operation == "scan" and self._dialog is not None:
            self._dialog.set_result(result)
        else:
            self._on_sync_completed(result)

    def _on_views_completed(self, result: dict) -> None:
        self.window.load_data()
        added = result.get("added", 0)
        self._show_status(f"查看记录已同步（新增 {added}）" if added else "查看记录已是最新")
        if not self._view_timer.isActive():
            self._view_timer.start()

    def _on_sync_completed(self, result: dict) -> None:
        if any(result.get(name) for name in ("pushed", "updated", "created", "trashed")):
            self.window.load_data()
        self._show_status(self._sync_summary(result))
        if self._dialog is not None:
            self._dialog.set_result(result)
            self._refresh_dialog()

    def _on_failed(self, operation: str, message: str) -> None:
        # 正文同步失败不停表：一次断网不应该永久关闭自动同步
        self._show_status("同步失败，稍后自动重试" if operation == "sync" else message)
        if operation == "views":
            self._view_timer.stop()
        if self._dialog is not None and operation in CONTENT_OPERATIONS:
            self._dialog.show_error(message)

    def _on_finished(self, operation: str) -> None:
        worker = self._workers.pop(operation, None)
        if worker is not None:
            worker.deleteLater()

    # ------------------------------------------------------------------
    # 状态页
    # ------------------------------------------------------------------
    def open_dialog(self) -> None:
        if self._dialog is not None:
            self._dialog.raise_()
            self._dialog.activateWindow()
            return
        dialog = SyncReviewDialog(self.window)
        self._dialog = dialog
        dialog.refresh_requested.connect(self._refresh_dialog)
        dialog.map_requested.connect(self.map_entries)
        dialog.scan_requested.connect(self.scan)
        dialog.sync_requested.connect(self.sync_content)
        dialog.views_requested.connect(self.sync_views)
        dialog.finished.connect(self._on_dialog_finished)
        dialog.show()
        self._refresh_dialog()

    def _refresh_dialog(self) -> None:
        if self._dialog is None:
            return
        settings = self._settings()
        if settings is None:
            self._dialog.show_error("请先配置服务器地址，再使用同步功能")
            return
        self._dialog.set_status(read_status(settings.state_path))

    def _on_dialog_finished(self) -> None:
        worker = self._workers.get("sync")
        if worker is not None and worker.isRunning():
            worker.requestInterruption()
        self._dialog = None

    # ------------------------------------------------------------------
    # 工具
    # ------------------------------------------------------------------
    def _settings(self):
        try:
            return get_sync_settings()
        except (ValueError, OSError):
            return None

    def _db_path(self) -> str:
        return self.window.controller.db_manager.db_path

    def _has_view_checkpoint(self) -> bool:
        try:
            return LocalViewRepository(self._db_path()).has_checkpoint()
        except OSError:
            return False

    def _move_to_trash(self, local_id: int):
        """服务器删除落到本地时走既有的两阶段回收站，不做物理删除。"""
        return self.window.controller.db_manager.move_to_trash(local_id)

    def _show_status(self, message: str) -> None:
        self.window.status_bar_manager.update_sync_status(message)

    def _report(self, message: str) -> None:
        QMessageBox.information(self.window, "服务器日记检查（只读）", message)

    @staticmethod
    def _sync_summary(result: dict) -> str:
        return (f"同步完成：上传 {result.get('pushed', 0)}，下行 {result.get('updated', 0)}，"
                f"新增 {result.get('created', 0)}，回收站 {result.get('trashed', 0)}，"
                f"冲突 {result.get('conflicts', 0)}")
