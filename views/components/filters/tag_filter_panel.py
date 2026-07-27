"""
标签筛选面板 - 专用于随机查看筛选弹窗
复用 TagManagerMixin 的搜索过滤和复选框逻辑，去除增删标签按钮
"""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                            QScrollArea, QCheckBox, QLineEdit, QLabel)
from PyQt6.QtCore import Qt, pyqtSignal
from widgets.layouts.flow_layout import FlowLayout

from i18n import _


class TagFilterPanel(QWidget):
    """标签筛选面板，支持搜索过滤，仅用于筛选场景"""
    tagsChanged = pyqtSignal(set)

    def __init__(self, parent=None, controller=None, initial_tag_ids=None):
        super().__init__(parent)
        self.controller = controller
        self.all_tags = []
        self.selected_tag_ids = set(initial_tag_ids or [])
        self.tag_checkboxes = {}
        self.init_ui()
        self.load_tags()

    def init_ui(self):
        """初始化界面"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # 搜索框
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel(_("搜索标签:")))
        self.tag_search_input = QLineEdit()
        self.tag_search_input.setPlaceholderText(_("输入关键词过滤标签..."))
        self.tag_search_input.textChanged.connect(self._filter_tags)
        search_layout.addWidget(self.tag_search_input)
        layout.addLayout(search_layout)

        # 标签复选框区域
        tags_group = QGroupBox(_("选择标签（留空表示不限制）："))
        tags_layout = QVBoxLayout()

        self.scroll_area = QScrollArea()
        self.scroll_widget = QWidget()
        self.tags_inner_layout = FlowLayout(margin=5, spacing=8)

        self.scroll_widget.setLayout(self.tags_inner_layout)
        self.scroll_area.setWidget(self.scroll_widget)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setMaximumHeight(180)

        tags_layout.addWidget(self.scroll_area)
        tags_group.setLayout(tags_layout)
        layout.addWidget(tags_group)

        self.setLayout(layout)

    def _get_controller(self):
        """获取控制器实例"""
        if self.controller:
            return self.controller
        try:
            return self.parent().parent().controller
        except Exception:
            from controllers.enhanced_diary_controller import EnhancedDiaryController
            from config.config import get_db_path
            return EnhancedDiaryController(get_db_path())

    def load_tags(self):
        """加载所有可用标签"""
        for checkbox in list(self.tag_checkboxes.values()):
            checkbox.setParent(None)
        self.tag_checkboxes.clear()

        for i in reversed(range(self.tags_inner_layout.count())):
            item = self.tags_inner_layout.itemAt(i)
            if item and item.widget():
                item.widget().setParent(None)

        controller = self._get_controller()
        self.all_tags = controller.get_all_tags()

        keyword = self.tag_search_input.text().strip().lower()
        self._render_checkboxes(keyword)

    def _filter_tags(self, keyword=""):
        """根据关键词过滤标签列表"""
        keyword = keyword.strip().lower()
        self._render_checkboxes(keyword)

    def _render_checkboxes(self, keyword=""):
        """渲染符合过滤条件的标签复选框"""
        # 清除现有复选框
        for checkbox in list(self.tag_checkboxes.values()):
            checkbox.setParent(None)
        self.tag_checkboxes.clear()

        for i in reversed(range(self.tags_inner_layout.count())):
            item = self.tags_inner_layout.itemAt(i)
            if item and item.widget():
                item.widget().setParent(None)

        filtered_tags = self.all_tags
        if keyword:
            filtered_tags = [tag for tag in self.all_tags if keyword in tag['name'].lower()]

        for tag in filtered_tags:
            checkbox = QCheckBox(tag['name'])
            checkbox.setObjectName(f"filter_tag_{tag['id']}")
            checkbox.setChecked(tag['id'] in self.selected_tag_ids)
            checkbox.stateChanged.connect(self._on_checkbox_state_changed)
            self.tag_checkboxes[tag['id']] = checkbox
            self.tags_inner_layout.addWidget(checkbox)

    def _on_checkbox_state_changed(self, state):
        """处理标签选择状态变化"""
        sender = self.sender()
        for tag_id, checkbox in self.tag_checkboxes.items():
            if checkbox == sender:
                if state == Qt.CheckState.Checked.value:
                    self.selected_tag_ids.add(tag_id)
                else:
                    self.selected_tag_ids.discard(tag_id)
                break
        self.tagsChanged.emit(self.selected_tag_ids)

    def get_selected_tag_ids(self):
        """获取当前选中的标签ID集合"""
        return self.selected_tag_ids.copy()

    def set_selected_tag_ids(self, tag_ids):
        """设置选中的标签ID集合"""
        self.selected_tag_ids = set(tag_ids or [])
        for tag_id, checkbox in self.tag_checkboxes.items():
            checkbox.setChecked(tag_id in self.selected_tag_ids)
