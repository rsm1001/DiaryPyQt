"""
日记对话框组件 - 从 main_window.py 解耦出来的对话框类
"""
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTextEdit,
                            QLabel, QPushButton, QMessageBox)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence

from i18n import _
from utils.formatters import format_tags_html
from widgets.TagSelectorWidget import TagSelectorWidget
from views.dialogs.base_dialog import CenteredDialogMixin
from views.dialogs.tag_manager_dialog import TagManagerMixin


class DiaryEditDialog(QDialog, CenteredDialogMixin, TagManagerMixin):
    """日记编辑对话框"""
    
    def __init__(self, parent=None, diary=None):
        super().__init__(parent)
        self.diary = diary
        self.init_tag_manager()
        self.init_ui()
        self.load_data()
        self.load_tags()
        self.update_tag_selections()
    
    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle(_("编辑日记") if self.diary else _("新建日记"))
        self.resize(770, 660)
        self.center_on_parent()
        
        layout = QVBoxLayout()
        
        # 信息显示区域（仅在编辑现有日记时显示）
        if self.diary:
            info_layout = QHBoxLayout()
            self.id_label = QLabel(_("ID:") + f" {self.diary.id}")
            self.date_label = QLabel(_("日期:") + f" {self.diary.date}")
            self.views_label = QLabel(_("查看次数:") + f" {self.diary.view_count}")
            self.id_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.date_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.views_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            info_layout.addWidget(self.id_label)
            info_layout.addWidget(self.date_label)
            info_layout.addWidget(self.views_label)
            layout.addLayout(info_layout)
        
        # 内容编辑区域
        self.content_edit = QTextEdit()
        layout.addWidget(self.content_edit)
        
        # 标签选择区域
        self.setup_tag_ui(layout)
        
        # 按钮区域 - 居中对齐
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.save_btn = QPushButton(_("保存"))
        self.save_btn.clicked.connect(self.accept)
        self.cancel_btn = QPushButton(_("取消"))
        self.cancel_btn.clicked.connect(self.reject)
        
        button_layout.addWidget(self.save_btn)
        button_layout.addWidget(self.cancel_btn)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
        # 设置快捷键
        self.save_btn.setShortcut(QKeySequence.StandardKey.Save)
        self.cancel_btn.setShortcut(QKeySequence.StandardKey.Cancel)
    
    def load_data(self):
        """加载日记数据"""
        if self.diary:
            self.content_edit.setPlainText(self.diary.content)
            if hasattr(self.diary, 'tags') and self.diary.tags:
                self.selected_tag_ids = {tag['id'] for tag in self.diary.tags}
    
    def get_content(self):
        """获取内容"""
        return self.content_edit.toPlainText()


class DiaryViewDialog(QDialog, CenteredDialogMixin, TagManagerMixin):
    """Dialog used for viewing a diary and correcting it in place."""

    def __init__(self, diary, parent=None, readonly=False, tag_ids=None):
        super().__init__(parent)
        self.diary = diary
        self.readonly = readonly
        self.editing = not readonly
        self.tag_ids = tag_ids or []
        self._edit_backup = None
        self.init_tag_manager()
        self.init_ui()
        self.load_data()
        self.load_tags()
        self.update_tag_selections()
        self._set_editable_state(self.editing)
        self._update_action_buttons()

    def init_ui(self):
        """Build the view dialog."""
        self.setWindowTitle(_("查看日记"))
        self.resize(770, 660)
        self.center_on_parent()

        layout = QVBoxLayout()
        layout.setSpacing(10)

        info_layout = QHBoxLayout()
        info_layout.setSpacing(12)
        self.id_label = QLabel(_("ID:") + f" {self.diary.id}")
        self.date_label = QLabel(_("日期:") + f" {self.diary.date}")
        self.views_label = QLabel(_("查看次数:") + f" {self.diary.view_count}")
        for label in (self.id_label, self.date_label, self.views_label):
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            info_layout.addWidget(label)
        layout.addLayout(info_layout)

        self.content_display = QTextEdit()
        self.content_display.setReadOnly(self.readonly)
        layout.addWidget(self.content_display)

        self.setup_tag_ui(layout)

        # Keep the action area compact: view mode has 3 buttons, edit mode has 3.
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        button_layout.addStretch()

        self.correct_btn = QPushButton(_("更正"))
        self.correct_btn.clicked.connect(self.toggle_correction)
        button_layout.addWidget(self.correct_btn)

        self.cancel_correction_btn = QPushButton(_("取消"))
        self.cancel_correction_btn.clicked.connect(self.cancel_correction)
        button_layout.addWidget(self.cancel_correction_btn)

        self.next_btn = QPushButton(_("下一个"))
        self.next_btn.clicked.connect(self.next_diary)
        button_layout.addWidget(self.next_btn)

        self.close_btn = QPushButton(_("关闭"))
        self.close_btn.clicked.connect(self.close)
        button_layout.addWidget(self.close_btn)
        button_layout.addStretch()

        for button in (
            self.correct_btn,
            self.cancel_correction_btn,
            self.next_btn,
            self.close_btn,
        ):
            button.setMinimumSize(88, 32)

        self.correct_btn.setStyleSheet(
            "QPushButton { background-color: #4A90E2; color: white; "
            "border: none; border-radius: 4px; padding: 6px 14px; }"
            "QPushButton:hover { background-color: #357ABD; }"
        )
        self.cancel_correction_btn.setStyleSheet(
            "QPushButton { background-color: #F0F0F0; color: #333; "
            "border: 1px solid #CCC; border-radius: 4px; padding: 6px 14px; }"
        )
        self.next_btn.setStyleSheet(
            "QPushButton { background-color: #6C757D; color: white; "
            "border: none; border-radius: 4px; padding: 6px 14px; }"
            "QPushButton:hover { background-color: #5A6268; }"
        )
        self.close_btn.setStyleSheet(
            "QPushButton { background-color: #F0F0F0; color: #333; "
            "border: 1px solid #CCC; border-radius: 4px; padding: 6px 14px; }"
        )

        layout.addLayout(button_layout)
        self.setLayout(layout)

    def _set_editable_state(self, enabled):
        """Toggle editing for both content and tag controls."""
        self.content_display.setReadOnly(not enabled)
        for name in (
            "tag_search_input",
            "refresh_tags_btn",
            "add_tag_btn",
            "delete_unused_tags_btn",
            "manage_specific_tag_btn",
        ):
            widget = getattr(self, name, None)
            if widget is not None:
                widget.setEnabled(enabled)
        for checkbox in self.tag_checkboxes.values():
            checkbox.setEnabled(enabled)

    def _update_action_buttons(self):
        """Keep only the actions relevant to the current mode visible."""
        self.correct_btn.setVisible(True)
        self.cancel_correction_btn.setVisible(self.editing)
        self.next_btn.setVisible(not self.editing)
        self.correct_btn.setText(_("保存") if self.editing else _("更正"))

    def toggle_correction(self):
        """Enter correction mode or save the current correction."""
        if self.editing:
            self.save_correction()
            return

        self._edit_backup = (
            self.diary.content,
            list(self.diary.tags or []),
        )
        self.editing = True
        self._set_editable_state(True)
        self._update_action_buttons()
        self.content_display.setFocus()

    def cancel_correction(self):
        """Discard unsaved changes and return to view mode."""
        if self._edit_backup is not None:
            content, tags = self._edit_backup
            self.diary.content = content
            self.diary.tags = tags
            self.load_data()
            self.load_tags()
            self.update_tag_selections()
        self._edit_backup = None
        self.editing = False if self.readonly else True
        self._set_editable_state(self.editing)
        self._update_action_buttons()

    def save_correction(self):
        """Persist the inline correction, including the selected tags."""
        content = self.content_display.toPlainText()
        if not content.strip():
            QMessageBox.warning(self, _("提示"), _("日记内容不能为空！"))
            return

        controller = self.get_controller()
        selected_tag_ids = self.get_selected_tag_ids()
        if not controller.update_diary(self.diary.id, content, selected_tag_ids):
            QMessageBox.warning(self, _("错误"), _("日记更新失败！"))
            return

        self.diary.content = content
        self.diary.tags = controller.get_tags_by_diary_id(self.diary.id) or []
        self._edit_backup = None
        self.editing = False if self.readonly else True
        self.load_data()
        self.load_tags()
        self.update_tag_selections()
        self._set_editable_state(self.editing)
        self._update_action_buttons()
        self._refresh_parent_after_update()
        QMessageBox.information(self, _("成功"), _("日记更新成功！"))

    def _refresh_parent_after_update(self):
        """Refresh the parent list, detail panel and statistics if available."""
        parent = self.parentWidget()
        if not parent:
            return

        if hasattr(parent, "load_data"):
            parent.load_data()
        elif hasattr(parent, "_refresh_search_results"):
            parent._refresh_search_results()

        if hasattr(parent, "detail_panel"):
            parent.detail_panel.update_content(
                self.diary, self._format_tags_html()
            )
        if hasattr(parent, "update_status_bar"):
            parent.update_status_bar()

    def next_diary(self):
        """View the next random diary."""
        controller = self.get_controller()
        new_diary = controller.random_view_diary(tag_ids=self.tag_ids)
        if not new_diary:
            QMessageBox.information(self, _("提示"), _("没有更多日记了"))
            return
        new_count = controller.increment_view_count(new_diary.id)
        if new_count is not None:
            new_diary.view_count = new_count
        self.diary = new_diary
        self._edit_backup = None
        self.editing = False
        self.load_data()
        self.load_tags()
        self.update_tag_selections()
        self._set_editable_state(False)
        self._update_action_buttons()

        parent = self.parentWidget()
        if parent:
            tags_html = self._format_tags_html()
            if hasattr(parent, "detail_panel"):
                parent.detail_panel.update_content(self.diary, tags_html)
            if hasattr(parent, "update_status_bar"):
                parent.update_status_bar()

    def _format_tags_html(self):
        """Format tags as HTML."""
        if not getattr(self.diary, "tags", None):
            return ""
        return format_tags_html(self.diary.tags)

    def load_data(self):
        """Load diary data into the dialog."""
        self.id_label.setText(_("ID:") + f" {self.diary.id}")
        self.date_label.setText(_("日期:") + f" {self.diary.date}")
        self.views_label.setText(_("查看次数:") + f" {self.diary.view_count}")
        self.content_display.setPlainText(self.diary.content)
        self.selected_tag_ids = {
            tag["id"] for tag in (self.diary.tags or [])
        }

    def save_tags(self):
        """Keep the legacy tag-only API for callers outside this dialog."""
        controller = self.get_controller()
        selected_tag_ids = self.get_selected_tag_ids()
        success = controller.assign_tags_to_diary(self.diary.id, selected_tag_ids)

        if success:
            QMessageBox.information(self, _("成功"), _("标签更新成功！"))
            self.diary.tags = controller.get_tags_by_diary_id(self.diary.id) or []
            self.load_tags()
            self.update_tag_selections()
        else:
            QMessageBox.warning(self, _("错误"), _("标签更新失败！"))
