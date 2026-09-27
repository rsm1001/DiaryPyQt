"""桌面服务器数据核对和下行确认对话框。"""
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QPushButton, QVBoxLayout


class SyncReviewDialog(QDialog):
    """用户先确认映射，再选择历史查看上传或内容下行。"""

    refresh_requested = pyqtSignal()
    map_requested = pyqtSignal()
    pull_requested = pyqtSignal()
    views_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("服务器日记同步审核")
        self.setMinimumWidth(480)
        self.summary = QLabel("正在检查服务器日记……")
        self.summary.setWordWrap(True)
        self.hint = QLabel("建立一对一映射后才能补齐电脑历史查看记录。")
        self.hint.setWordWrap(True)
        self.refresh_button = QPushButton("重新检查")
        self.map_button = QPushButton("确认并保存 ID 映射")
        self.pull_button = QPushButton("下行日记内容")
        self.views_button = QPushButton("上传电脑历史并同步查看记录")
        close_button = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_button.rejected.connect(self.reject)
        self.refresh_button.clicked.connect(self.refresh_requested)
        self.map_button.clicked.connect(self.map_requested)
        self.pull_button.clicked.connect(self.pull_requested)
        self.views_button.clicked.connect(self.views_requested)
        layout = QVBoxLayout(self)
        for widget in (self.summary, self.hint, self.refresh_button, self.map_button,
                       self.pull_button, self.views_button, close_button):
            layout.addWidget(widget)
        self.set_busy(True)

    def set_busy(self, busy: bool) -> None:
        for button in (self.refresh_button, self.map_button, self.pull_button, self.views_button):
            button.setEnabled(not busy)
        if busy:
            self.hint.setText("正在后台核对，请勿关闭窗口或修改日记。")

    def set_result(self, result: dict) -> None:
        mapped = bool(result.get("mapped"))
        complete = (result.get("matched", 0) == result.get("local", 0)
                    and result.get("local_only", 0) == 0
                    and result.get("remote_only", 0) == 0
                    and result.get("ambiguous", 0) == 0)
        self.summary.setText(
            f"本地日记：{result.get('local', 0)} 篇；唯一匹配：{result.get('matched', 0)} 篇\n"
            f"本地未匹配：{result.get('local_only', 0)}；服务器未匹配：{result.get('remote_only', 0)}\n"
            f"歧义：{result.get('ambiguous', 0)}；映射：{'已确认' if mapped else '未确认'}"
        )
        self.hint.setText(
            "先将电脑原有查看次数和最后查看时间补入服务器，不覆盖服务器新记录；"
            "完成基线后双向同步新增查看，检查点保证断网重试不会重复计数。"
        )
        self.map_button.setEnabled(not mapped and complete)
        self.pull_button.setEnabled(mapped)
        self.views_button.setEnabled(mapped)
        self.refresh_button.setEnabled(True)

    def show_error(self, message: str) -> None:
        self.hint.setText(message)
        self.set_busy(False)