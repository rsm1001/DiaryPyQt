"""
列设置对话框
允许用户自定义列的显示/隐藏和顺序
"""
import logging
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListWidget,
                             QListWidgetItem, QPushButton, QLabel, QCheckBox,
                             QGroupBox, QDialogButtonBox)
from PyQt6.QtCore import Qt
from views.components.column_config_manager import ColumnConfigManager

from i18n import _

logger = logging.getLogger(__name__)


class ColumnSettingsDialog(QDialog):
    """列设置对话框"""

    def __init__(self, config_manager: ColumnConfigManager, parent=None):
        """
        初始化列设置对话框

        Args:
            config_manager: 列配置管理器实例
            parent: 父窗口
        """
        super().__init__(parent)
        self.config_manager = config_manager
        self._original_config = config_manager.get_config()  # 保存原始配置用于取消
        self._setup_ui()
        self._load_current_config()

    def _setup_ui(self):
        """设置UI"""
        self.setWindowTitle(_("自定义列表列"))
        self.setMinimumSize(450, 350)
        self.setModal(True)

        main_layout = QVBoxLayout(self)

        # 说明标签
        hint_label = QLabel(_("勾选要显示的列，可拖拽调整显示顺序。点击行区域切换显示/隐藏。"))
        hint_label.setStyleSheet("color: #666; font-size: 12px;")
        hint_label.setWordWrap(True)
        main_layout.addWidget(hint_label)

        # 列列表区域
        list_group = QGroupBox(_("显示列（拖拽调整顺序）"))
        list_layout = QVBoxLayout()

        self.column_list = QListWidget()
        self.column_list.setDragEnabled(True)
        self.column_list.setAcceptDrops(True)
        self.column_list.setDropIndicatorShown(True)
        self.column_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.column_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.column_list.setMinimumHeight(200)

        # 点击行区域切换复选框
        self.column_list.itemClicked.connect(self._on_item_clicked)

        list_layout.addWidget(self.column_list)
        list_group.setLayout(list_layout)
        main_layout.addWidget(list_group)

        # 按钮区域
        button_layout = QHBoxLayout()

        self.reset_btn = QPushButton(_("重置默认"))
        self.reset_btn.clicked.connect(self._on_reset)
        button_layout.addWidget(self.reset_btn)

        button_layout.addStretch()

        # 标准按钮
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                      QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self._on_reject)
        button_layout.addWidget(button_box)

        main_layout.addLayout(button_layout)

    def _load_current_config(self):
        """加载当前配置到列表（加载所有列，按 order 排序）"""
        self.column_list.clear()
        all_config = self.config_manager.get_config()

        # 按 order 排序
        sorted_config = sorted(all_config, key=lambda x: x['order'])

        for col in sorted_config:
            item = ColumnListItem(col['id'], col['title'], col['visible'])
            item.setData(Qt.ItemDataRole.UserRole, col)
            self.column_list.addItem(item)

    def _on_item_clicked(self, item):
        """点击列表项时切换复选框状态"""
        if isinstance(item, ColumnListItem):
            item.toggle_visible()
            # 阻止默认的检查行为（因为我们手动处理了）
            item.setCheckState(
                Qt.CheckState.Checked if item.is_visible() else Qt.CheckState.Unchecked
            )

    def _on_reset(self):
        """重置为默认配置"""
        self.config_manager.reset_to_default()
        self._load_current_config()
        logger.debug("列设置已重置为默认")

    def _on_accept(self):
        """确认保存"""
        # 从列表收集配置
        new_config = []
        for i in range(self.column_list.count()):
            item = self.column_list.item(i)
            col_data = item.data(Qt.ItemDataRole.UserRole)
            new_config.append({
                'id': col_data['id'],
                'title': col_data['title'],
                'visible': item.is_visible(),
                'width': self.config_manager.get_col_width(col_data['id']),
                'order': i
            })

        # 更新配置管理器
        if self.config_manager.update_config(new_config):
            self.config_manager.save()
            logger.info("列设置已保存")
            self.accept()
        else:
            logger.error("列设置保存失败")

    def _on_reject(self):
        """取消，恢复原始配置"""
        self.config_manager.update_config(self._original_config)
        self.reject()

    def get_config_manager(self):
        """获取配置管理器"""
        return self.config_manager


class ColumnListItem(QListWidgetItem):
    """列列表项，包含复选框和标题"""

    def __init__(self, col_id, title, visible, parent=None):
        super().__init__(parent)
        self.col_id = col_id
        self._visible = visible
        self.setText(f"  {title}")
        self.setFlags(self.flags() | Qt.ItemFlag.ItemIsUserCheckable |
                      Qt.ItemFlag.ItemIsDragEnabled)

        if visible:
            self.setCheckState(Qt.CheckState.Checked)
        else:
            self.setCheckState(Qt.CheckState.Unchecked)

    def is_visible(self):
        """获取可见性"""
        return self._visible

    def toggle_visible(self):
        """切换可见性"""
        self._visible = not self._visible

    def set_visible(self, visible):
        """设置可见性"""
        self._visible = visible
        if visible:
            self.setCheckState(Qt.CheckState.Checked)
        else:
            self.setCheckState(Qt.CheckState.Unchecked)
