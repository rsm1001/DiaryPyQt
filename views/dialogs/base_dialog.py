"""
对话框基类模块 - 提供通用对话框功能
"""
from PyQt6.QtWidgets import QDialog, QApplication, QMenu, QMessageBox
from PyQt6.QtCore import Qt


class ContextMenuMixin:
    """列表右键菜单混入类 - 为 QListWidget 或 QTableView 提供右键菜单功能"""

    def setup_context_menu_for_list(self, list_widget):
        """
        为列表部件设置右键菜单
        list_widget: QListWidget 或 QTableView 实例
        """
        list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        list_widget.customContextMenuRequested.connect(
            lambda pos: self._on_context_menu_requested(list_widget, pos)
        )

    def _on_context_menu_requested(self, widget, position):
        """处理右键菜单请求"""
        item = widget.itemAt(position) if hasattr(widget, 'itemAt') else None
        if item is None:
            return

        diary = item.data(Qt.ItemDataRole.UserRole)
        if diary is None:
            return

        menu = QMenu()
        view_action = menu.addAction("查看")
        edit_action = menu.addAction("编辑")
        delete_action = menu.addAction("删除")

        action = menu.exec(widget.viewport().mapToGlobal(position))

        if action == view_action:
            self._context_view_diary(diary)
        elif action == edit_action:
            self._context_edit_diary(diary)
        elif action == delete_action:
            self._context_delete_diary(diary, item)

    def _context_view_diary(self, diary):
        """右键菜单查看日记"""
        from views.dialogs.diary_dialogs import DiaryViewDialog
        # 获取日记的标签并挂载到对象上，DiaryViewDialog.load_data 依赖 diary.tags
        tags = self.controller.get_tags_by_diary_id(diary.id)
        diary.tags = tags if tags else []
        dialog = DiaryViewDialog(diary, self, readonly=True)
        dialog.exec()

    def _context_edit_diary(self, diary):
        """右键菜单编辑日记"""
        from views.dialogs.diary_dialogs import DiaryEditDialog
        # 从数据库重新获取日记完整信息（含标签），否则编辑对话框无法正确勾选标签
        full_diary = self.controller.get_diary_by_id(diary.id)
        if full_diary is None:
            full_diary = diary
        # 获取日记的标签并挂载到对象上，DiaryEditDialog.load_data 依赖 diary.tags
        tags = self.controller.get_tags_by_diary_id(full_diary.id)
        full_diary.tags = tags if tags else []
        dialog = DiaryEditDialog(self, full_diary)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            content = dialog.get_content()
            selected_tag_ids = dialog.get_selected_tag_ids()
            if content.strip():
                self.controller.update_diary(diary.id, content)
                self.controller.assign_tags_to_diary(diary.id, selected_tag_ids)
            self._refresh_search_results()

    def _context_delete_diary(self, diary, item):
        """右键菜单删除日记"""
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除日记 ID:{diary.id} 吗？\n\n内容: {diary.content[:50]}...",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.controller.delete_diary_by_id(diary.id)
            self._remove_result_item(item)
            QMessageBox.information(self, "成功", "日记已删除")

    def _refresh_search_results(self):
        """刷新搜索结果 - 子类可覆盖"""
        pass

    def _remove_result_item(self, item):
        """从结果列表中移除项 - 子类可覆盖"""
        pass


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
