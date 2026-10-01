"""桌面服务器同步状态页：只读展示，冲突时才需要人工介入。"""
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (QDialog, QDialogButtonBox, QLabel, QListWidget,
                             QListWidgetItem, QMessageBox, QPushButton, QVBoxLayout)

CONFLICT_KIND_LABELS = {
    "local_overwritten": "本地被服务器版本覆盖",
    "timestamp_ambiguous": "修改时间无法分辨，已搁置",
    "push_rejected": "上传被服务器拒绝，已保留服务器版本",
    "delete_vs_remote_edit": "删除与服务器修改冲突",
    "server_deleted": "服务器已删除，本地内容已留档",
}


class SyncReviewDialog(QDialog):
    """展示同步状态与待处理冲突，并提供手动兜底入口。"""

    refresh_requested = pyqtSignal()
    map_requested = pyqtSignal()
    scan_requested = pyqtSignal()
    sync_requested = pyqtSignal()
    views_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("服务器日记同步状态")
        self.setMinimumWidth(560)
        self._conflicts = []
        self._match_complete = False

        self.summary = QLabel("正在读取同步状态……")
        self.summary.setWordWrap(True)
        self.conflict_hint = QLabel("")
        self.conflict_hint.setWordWrap(True)
        self.conflict_hint.setVisible(False)
        self.conflict_list = QListWidget()
        self.conflict_list.setVisible(False)
        self.conflict_list.itemDoubleClicked.connect(self._show_conflict)

        self.refresh_button = QPushButton("重新检查")
        self.map_button = QPushButton("建立并保存 ID 映射")
        self.scan_button = QPushButton("预演（不写入）")
        self.sync_button = QPushButton("立即同步")
        self.views_button = QPushButton("上传电脑历史并同步查看记录")
        close_button = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)

        self.refresh_button.clicked.connect(self.refresh_requested)
        self.map_button.clicked.connect(self.map_requested)
        self.scan_button.clicked.connect(self.scan_requested)
        self.sync_button.clicked.connect(self.sync_requested)
        self.views_button.clicked.connect(self.views_requested)
        close_button.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        for widget in (self.summary, self.conflict_hint, self.conflict_list,
                       self.map_button, self.scan_button, self.sync_button,
                       self.views_button, self.refresh_button, close_button):
            layout.addWidget(widget)
        self.set_busy(True)

    def _action_buttons(self):
        return (self.refresh_button, self.map_button, self.scan_button,
                self.sync_button, self.views_button)

    def set_busy(self, busy: bool) -> None:
        for button in self._action_buttons():
            button.setEnabled(not busy)
        if busy:
            self.conflict_hint.setText("正在核对，请勿关闭窗口或修改日记。")
            self.conflict_hint.setVisible(True)

    def set_status(self, status: dict) -> None:
        """按同步状态刷新只读页面。"""
        mapped = bool(status.get("mapped"))
        stats = status.get("last_sync_stats") or {}
        detail = "，".join(f"{name} {value}" for name, value in stats.items() if value) or "无变更"
        self.summary.setText(
            f"映射：{'已建立' if mapped else '尚未建立'}"
            f"（{status.get('entries', 0)} 篇，游标 {status.get('cursor', 0)}）\n"
            f"上次同步：{status.get('last_sync_at') or '尚未同步'}\n"
            f"最近一轮：{detail}"
        )
        if status.get("error"):
            self.summary.setText(f"{self.summary.text()}\n{status['error']}")
        self._set_conflicts(status.get("conflicts") or [])
        for button in (self.scan_button, self.sync_button, self.views_button):
            button.setEnabled(mapped)
        # 未建立映射时只允许在"本地与服务器完全一对一"的前提下手工建立，
        # 绝不自动配对
        self.map_button.setEnabled(not mapped and self._match_complete)
        self.refresh_button.setEnabled(True)

    def set_precheck(self, result: dict) -> None:
        """只读检查结果：决定是否允许手工建立 ID 映射。"""
        mapped = bool(result.get("mapped"))
        self._match_complete = (
            not mapped
            and result.get("matched", 0) == result.get("local", 0)
            and result.get("local_only", 0) == 0
            and result.get("remote_only", 0) == 0
            and result.get("ambiguous", 0) == 0)
        self.conflict_hint.setText(
            f"本地 {result.get('local', 0)} 篇，唯一匹配 {result.get('matched', 0)} 篇；"
            f"本地未匹配 {result.get('local_only', 0)}，服务器未匹配 {result.get('remote_only', 0)}，"
            f"歧义 {result.get('ambiguous', 0)}。"
            + ("映射已建立，可正常同步。" if mapped
               else "两侧完全一对一后才能建立映射。"))
        self.conflict_hint.setVisible(True)
        self.map_button.setEnabled(self._match_complete)

    def set_result(self, result: dict) -> None:
        """展示预演结果；预演不改动任何数据。"""
        if result.get("plan_only"):
            self.conflict_hint.setText(
                f"预演结果：计划上传 {result.get('planned_push', 0)} 篇，"
                f"计划下行 {result.get('planned_pull', 0)} 篇，"
                f"计划移入回收站 {result.get('planned_trash', 0)} 篇。"
                "预演不写入任何数据。"
            )
        else:
            self.conflict_hint.setText(
                f"本轮完成：上传 {result.get('pushed', 0)} 篇，"
                f"下行 {result.get('updated', 0)} 篇，"
                f"新增 {result.get('created', 0)} 篇，"
                f"移入回收站 {result.get('trashed', 0)} 篇，"
                f"待处理冲突 {result.get('conflicts', 0)} 条。"
            )
        self.conflict_hint.setVisible(True)

    def show_error(self, message: str) -> None:
        self.conflict_hint.setText(message)
        self.conflict_hint.setVisible(True)
        self.set_busy(False)

    def _set_conflicts(self, conflicts: list) -> None:
        self._conflicts = conflicts
        self.conflict_list.clear()
        has_conflicts = bool(conflicts)
        self.conflict_hint.setVisible(has_conflicts)
        self.conflict_list.setVisible(has_conflicts)
        if not has_conflicts:
            return
        self.conflict_hint.setText(
            f"待处理冲突 {len(conflicts)} 条，双击可查看双方正文；同步已跳过这些日记。")
        for conflict in conflicts:
            label = CONFLICT_KIND_LABELS.get(conflict.get("kind"), conflict.get("kind", "未知冲突"))
            local_id = conflict.get("local_id")
            self.conflict_list.addItem(QListWidgetItem(
                f"{label}（本地 {local_id if local_id is not None else '-'}）"
                f"  {conflict.get('at', '')}"))

    def _show_conflict(self, item: QListWidgetItem) -> None:
        conflict = self._conflicts[self.conflict_list.row(item)]
        local = conflict.get("local_payload") or {}
        remote = conflict.get("remote_payload") or {}
        QMessageBox.information(
            self, "冲突详情",
            f"原因：{conflict.get('note') or conflict.get('kind')}\n\n"
            f"本地版本：{local.get('content', '（无）')}\n\n"
            f"服务器版本：{remote.get('content', '（无）')}\n\n"
            "完整内容已保存在同步状态文件中，可据此手工恢复。"
        )
