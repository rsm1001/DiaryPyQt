"""
批量打标签对话框 - 为多篇日记同时打标签
复用 TagManagerMixin，与 DiaryEditDialog 保持一致的标签编辑方式
"""
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMessageBox)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence

from views.dialogs.base_dialog import CenteredDialogMixin
from views.dialogs.tag_manager_dialog import TagManagerMixin


class BatchTagDialog(QDialog, CenteredDialogMixin, TagManagerMixin):
    """批量打标签对话框"""

    def __init__(self, controller, diaries, parent=None):
        """
        Args:
            controller: EnhancedDiaryController 实例
            diaries: 日记对象列表（Diary 实例列表）
            parent: 父窗口
        """
        super().__init__(parent)
        self.controller = controller
        self.diaries = diaries
        self.init_tag_manager()
        self.init_ui()

    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle(f"批量打标签 - 已选 {len(self.diaries)} 篇日记")
        self.resize(500, 420)
        self.center_on_parent()

        layout = QVBoxLayout()

        # 顶部提示信息
        diary_ids = [d.id for d in self.diaries]
        id_preview = ", ".join(str(i) for i in diary_ids[:10])
        if len(diary_ids) > 10:
            id_preview += f" ... (共{len(diary_ids)}篇)"
        hint_label = QLabel(f"将为以下日记打标签：ID [{id_preview}]")
        hint_label.setStyleSheet("color: #666; font-size: 12px;")
        hint_label.setWordWrap(True)
        layout.addWidget(hint_label)

        # 标签选择区域 - 复用 TagManagerMixin，与 DiaryEditDialog 保持一致
        self.setup_tag_ui(layout)

        # 初始化选中状态：所有选中日记标签的并集
        all_tag_ids = set()
        for diary in self.diaries:
            if hasattr(diary, 'tags') and diary.tags:
                for tag in diary.tags:
                    if 'id' in tag:
                        all_tag_ids.add(tag['id'])
        self.selected_tag_ids = all_tag_ids

        # 加载标签并更新勾选状态
        self.load_tags()
        self.update_tag_selections()

        # 按钮区域
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.save_btn = QPushButton("保存")
        self.save_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; }")
        self.save_btn.clicked.connect(self._save_and_accept)
        self.save_btn.setShortcut(QKeySequence.StandardKey.Save)
        button_layout.addWidget(self.save_btn)

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        self.cancel_btn.setShortcut(QKeySequence.StandardKey.Cancel)
        button_layout.addWidget(self.cancel_btn)

        layout.addLayout(button_layout)
        self.setLayout(layout)

    def get_controller(self):
        """获取控制器实例"""
        return self.controller

    def _save_and_accept(self):
        """保存并关闭对话框"""
        self.accept()

    def get_selected_tag_ids(self):
        """获取选中的标签ID列表"""
        return list(self.selected_tag_ids)
