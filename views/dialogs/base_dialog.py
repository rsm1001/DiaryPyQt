"""
对话框基类模块 - 提供通用对话框功能
"""
from PyQt6.QtWidgets import QDialog, QApplication


class CenteredDialogMixin:
    """对话框居中显示混入类"""
    
    def center_on_parent(self):
        """使对话框居中于父窗口"""
        parent = self.parentWidget()
        if parent:
            parent_geo = parent.geometry()
            x = parent_geo.x() + (parent_geo.width() - self.width()) // 2
            y = parent_geo.y() + (parent_geo.height() - self.height()) // 2
            # 确保对话框在屏幕上可见
            screen_geo = QApplication.primaryScreen().geometry()
            x = max(0, min(x, screen_geo.width() - self.width()))
            y = max(0, min(y, screen_geo.height() - self.height()))
            self.move(x, y)
        else:
            # 如果没有父窗口，则居中于屏幕
            screen_geo = QApplication.primaryScreen().geometry()
            x = (screen_geo.width() - self.width()) // 2
            y = (screen_geo.height() - self.height()) // 2
            self.move(screen_geo.x() + x, screen_geo.y() + y)


class BaseDialog(QDialog, CenteredDialogMixin):
    """对话框基类"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
