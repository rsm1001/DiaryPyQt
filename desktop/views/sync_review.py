"""????????????"""
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QPushButton, QVBoxLayout


class SyncReviewDialog(QDialog):
    """???????????????????"""

    refresh_requested = pyqtSignal()
    map_requested = pyqtSignal()
    pull_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("???????")
        self.setMinimumWidth(480)
        self.summary = QLabel("???????????")
        self.summary.setWordWrap(True)
        self.hint = QLabel("?????????????????")
        self.hint.setWordWrap(True)
        self.refresh_button = QPushButton("????")
        self.map_button = QPushButton("??????")
        self.pull_button = QPushButton("???????")
        close_button = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_button.rejected.connect(self.reject)
        self.refresh_button.clicked.connect(self.refresh_requested)
        self.map_button.clicked.connect(self.map_requested)
        self.pull_button.clicked.connect(self.pull_requested)
        layout = QVBoxLayout(self)
        layout.addWidget(self.summary)
        layout.addWidget(self.hint)
        layout.addWidget(self.refresh_button)
        layout.addWidget(self.map_button)
        layout.addWidget(self.pull_button)
        layout.addWidget(close_button)
        self.set_busy(True)

    def set_busy(self, busy: bool) -> None:
        self.refresh_button.setEnabled(not busy)
        self.map_button.setEnabled(not busy)
        self.pull_button.setEnabled(not busy)
        if busy:
            self.hint.setText("?????????????????????")

    def set_result(self, result: dict) -> None:
        mapped = bool(result.get("mapped"))
        complete = result.get("matched", 0) == result.get("local", 0)
        self.summary.setText(
            f"?????{result.get('local', 0)} ?\n"
            f"?????{result.get('matched', 0)} ?\n"
            f"????{result.get('local_only', 0)} ???????{result.get('remote_only', 0)} ?\n"
            f"???{result.get('ambiguous', 0)} ?\n"
            f"?????{'?????' if mapped else '??????'}"
        )
        self.hint.setText(
            "???????????????????????????????"
            "??????????????????????"
        )
        self.map_button.setEnabled(not mapped and complete)
        self.pull_button.setEnabled(mapped)
        self.refresh_button.setEnabled(True)

    def show_error(self, message: str) -> None:
        self.hint.setText(message)
        self.set_busy(False)
