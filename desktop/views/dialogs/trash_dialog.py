"""
垃圾桶对话框 - 从主窗口中解耦出来的独立模块
支持查看垃圾桶、搜索、双击恢复和永久删除功能
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QLineEdit, QPushButton, QMessageBox, QApplication,
    QInputDialog
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence

from i18n import _


class TrashDialog(QDialog):
    """垃圾桶对话框"""

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.current_results = []
        self.init_ui()
        self.load_trash_data()

    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle(_("垃圾桶"))
        self.resize(700, 500)
        self.center_on_parent()

        layout = QVBoxLayout()

        # 顶部搜索栏
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel(_("关键词:")))
        self.keyword_input = QLineEdit()
        self.keyword_input.returnPressed.connect(self.perform_search)
        search_layout.addWidget(self.keyword_input)

        self.search_btn = QPushButton(_("搜索"))
        self.search_btn.clicked.connect(self.perform_search)
        search_layout.addWidget(self.search_btn)

        self.refresh_btn = QPushButton(_("刷新"))
        self.refresh_btn.clicked.connect(self.load_trash_data)
        search_layout.addWidget(self.refresh_btn)

        layout.addLayout(search_layout)

        # 结果列表
        self.results_list = QListWidget()
        self.results_list.itemDoubleClicked.connect(self.on_item_double_clicked)
        layout.addWidget(self.results_list)

        # 结果计数
        self.result_count_label = QLabel(_("共 0 条记录"))
        self.result_count_label.setStyleSheet("font-size: 10px; color: gray;")
        layout.addWidget(self.result_count_label)

        # 按钮区域
        button_layout = QHBoxLayout()

        self.restore_btn = QPushButton(_("恢复"))
        self.restore_btn.clicked.connect(self.restore_selected)
        self.restore_btn.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white; }"
        )
        button_layout.addWidget(self.restore_btn)

        self.permanent_delete_btn = QPushButton(_("永久删除"))
        self.permanent_delete_btn.clicked.connect(self.permanent_delete_selected)
        self.permanent_delete_btn.setStyleSheet(
            "QPushButton { background-color: #f44336; color: white; }"
        )
        button_layout.addWidget(self.permanent_delete_btn)

        self.empty_trash_btn = QPushButton(_("清空垃圾桶"))
        self.empty_trash_btn.clicked.connect(self.empty_trash)
        self.empty_trash_btn.setStyleSheet(
            "QPushButton { background-color: #ff9800; color: white; }"
        )
        button_layout.addWidget(self.empty_trash_btn)

        button_layout.addStretch()

        self.ok_btn = QPushButton(_("关闭"))
        self.ok_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.ok_btn)

        layout.addLayout(button_layout)

        self.setLayout(layout)

        # 设置焦点到输入框
        self.keyword_input.setFocus()

    def center_on_parent(self):
        """使对话框居中于父窗口"""
        parent = self.parentWidget()
        if parent:
            parent_geo = parent.geometry()
            x = parent_geo.x() + (parent_geo.width() - self.width()) // 2
            y = parent_geo.y() + (parent_geo.height() - self.height()) // 2
            screen_geo = QApplication.primaryScreen().geometry()
            x = max(0, min(x, screen_geo.width() - self.width()))
            y = max(0, min(y, screen_geo.height() - self.height()))
            self.move(x, y)
        else:
            screen_geo = QApplication.primaryScreen().geometry()
            x = (screen_geo.width() - self.width()) // 2
            y = (screen_geo.height() - self.height()) // 2
            self.move(screen_geo.x() + x, screen_geo.y() + y)

    def load_trash_data(self):
        """加载垃圾桶数据"""
        self.keyword_input.clear()
        diaries = self.controller.get_all_trash_diaries(limit=1000)
        self.display_results(diaries, _("全部记录"))

    def perform_search(self):
        """执行搜索"""
        keyword = self.keyword_input.text().strip()
        if not keyword:
            self.load_trash_data()
            return

        results = self.controller.search_trash_by_keyword(keyword, limit=1000)
        self.display_results(results, f"{_('关键词:')} '{keyword}'")

    def display_results(self, diaries, search_type):
        """显示搜索结果"""
        self.results_list.clear()
        self.current_results = diaries

        for diary in diaries:
            # 构建显示文本
            tag_info = ""
            if diary.get('tag_names'):
                tag_info = f" [{diary['tag_names']}]"

            deleted_at = diary.get('deleted_at', _('未知'))
            item_text = (
                f"[{diary['id']}] {diary['date']} | "
                f"{_('删除于:')} {deleted_at} | "
                f"{_('查看:')} {diary.get('view_count', 0)}{tag_info}\n"
                f"    {diary['content'][:60]}..."
            )

            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, diary)
            self.results_list.addItem(item)

        count = len(diaries)
        self.result_count_label.setText(f"{_('共')} {count} {_('条记录')} - {search_type}")

        if not diaries:
            self.results_list.addItem(_("垃圾桶是空的"))

    def on_item_double_clicked(self, item):
        """双击项目，恢复日记"""
        diary = item.data(Qt.ItemDataRole.UserRole)
        if diary:
            trash_id = diary['id']

            reply = QMessageBox.question(
                self,
                _("确认恢复"),
                f"{_('确定要恢复这篇日记吗？')}\n\n{diary['content'][:100]}...",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                restored = self.controller.restore_from_trash(trash_id)
                if restored:
                    QMessageBox.information(
                        self,
                        _("成功"),
                        f"{_('日记已恢复！')}\n{_('新ID:')} {restored.id}"
                    )
                    self.load_trash_data()
                else:
                    QMessageBox.warning(self, _("错误"), _("恢复失败！"))

    def restore_selected(self):
        """恢复选中的日记"""
        selected = self.results_list.selectedItems()
        if not selected:
            QMessageBox.warning(self, _("警告"), _("请先选择一篇日记"))
            return

        item = selected[0]
        self.on_item_double_clicked(item)

    def permanent_delete_selected(self):
        """永久删除选中的日记"""
        selected = self.results_list.selectedItems()
        if not selected:
            QMessageBox.warning(self, _("警告"), _("请先选择一篇日记"))
            return

        item = selected[0]
        diary = item.data(Qt.ItemDataRole.UserRole)
        if not diary:
            return

        reply = QMessageBox.warning(
            self,
            _("危险操作"),
            f"<b>{_('确定要永久删除吗？此操作不可恢复！')}</b><br><br>"
            f"{_('内容:')} {diary['content'][:100]}...",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            success = self.controller.permanently_delete_trash(diary['id'])
            if success:
                QMessageBox.information(self, _("成功"), _("已永久删除"))
                self.load_trash_data()
            else:
                QMessageBox.warning(self, _("错误"), _("删除失败！"))

    def empty_trash(self):
        """清空整个垃圾桶"""
        count = self.controller.get_trash_count()
        if count == 0:
            QMessageBox.information(self, _("提示"), _("垃圾桶已经是空的"))
            return

        reply = QMessageBox.critical(
            self,
            _("危险操作"),
            f"<b>{_('确定要清空整个垃圾桶吗？此操作不可恢复！')}</b><br><br>"
            f"{_('将永久删除')} {count} {_('篇日记')}。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            deleted_count = self.controller.empty_trash()
            QMessageBox.information(
                self,
                _("成功"),
                f"{_('已清空垃圾桶，永久删除')} {deleted_count} {_('篇日记')}"
            )
            self.load_trash_data()
