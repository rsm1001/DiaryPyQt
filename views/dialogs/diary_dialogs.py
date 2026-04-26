"""
日记对话框组件 - 从 main_window.py 解耦出来的对话框类
"""
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, 
                            QLabel, QPushButton, QMessageBox)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence

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
        self.setWindowTitle("编辑日记" if self.diary else "新建日记")
        self.resize(600, 500)
        self.center_on_parent()
        
        layout = QVBoxLayout()
        
        # 信息显示区域（仅在编辑现有日记时显示）
        if self.diary:
            info_layout = QHBoxLayout()
            self.id_label = QLabel(f"ID: {self.diary.id}")
            self.date_label = QLabel(f"日期: {self.diary.date}")
            self.views_label = QLabel(f"查看次数: {self.diary.view_count}")
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
        
        self.save_btn = QPushButton("保存")
        self.save_btn.clicked.connect(self.accept)
        self.cancel_btn = QPushButton("取消")
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
    """日记查看对话框"""
    
    def __init__(self, diary, parent=None, readonly=False):
        super().__init__(parent)
        self.diary = diary
        self.readonly = readonly
        self.init_tag_manager()
        self.init_ui()
        self.load_data()
        self.load_tags()
        self.update_tag_selections()
    
    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle("查看日记")
        self.resize(700, 600)
        self.center_on_parent()
        
        layout = QVBoxLayout()
        
        # 信息显示区域
        info_layout = QHBoxLayout()
        self.id_label = QLabel(f"ID: {self.diary.id}")
        self.date_label = QLabel(f"日期: {self.diary.date}")
        self.views_label = QLabel(f"查看次数: {self.diary.view_count}")
        self.id_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.date_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.views_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_layout.addWidget(self.id_label)
        info_layout.addWidget(self.date_label)
        info_layout.addWidget(self.views_label)
        layout.addLayout(info_layout)
        
        # 内容显示区域
        self.content_display = QTextEdit()
        self.content_display.setReadOnly(self.readonly)
        layout.addWidget(self.content_display)
        
        # 标签选择区域 - 使用 TagManagerMixin 提供的标签UI
        self.setup_tag_ui(layout)
        
        # 按钮区域 - 居中对齐
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        # 保存标签按钮
        self.save_tags_btn = QPushButton("保存标签")
        self.save_tags_btn.clicked.connect(self.save_tags)
        self.save_tags_btn.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white; }"
        )
        button_layout.addWidget(self.save_tags_btn)
        
        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.close)
        button_layout.addWidget(self.close_btn)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def load_data(self):
        """加载日记数据"""
        self.content_display.setPlainText(self.diary.content)
        # 加载日记的标签到选中状态
        if hasattr(self.diary, 'tags') and self.diary.tags:
            self.selected_tag_ids = {tag['id'] for tag in self.diary.tags}
    
    def save_tags(self):
        """保存标签更改到数据库"""
        controller = self.get_controller()
        selected_tag_ids = self.get_selected_tag_ids()
        success = controller.assign_tags_to_diary(self.diary.id, selected_tag_ids)
        
        if success:
            QMessageBox.information(self, "成功", "标签更新成功！")
            self.diary.tags = controller.get_tags_by_diary_id(self.diary.id)
        else:
            QMessageBox.warning(self, "错误", "标签更新失败！")
