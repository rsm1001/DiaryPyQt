"""
标签选择组件 - 可重用的标签选择控件
"""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
                            QScrollArea, QCheckBox, QPushButton, QInputDialog, 
                            QMessageBox, QListWidget, QListWidgetItem)
from PyQt6.QtCore import Qt, pyqtSignal
from widgets.layouts.flow_layout import FlowLayout


class TagSelectorWidget(QWidget):
    """可重用的标签选择组件"""
    tagsChanged = pyqtSignal(set)  # 发出标签变化信号

    def __init__(self, parent=None, controller=None, initial_tags=None):
        super().__init__(parent)
        self.controller = controller
        self.all_tags = []  # 存储所有可用标签
        self.selected_tag_ids = set(initial_tags or [])  # 存储当前选中的标签ID
        self.tag_checkboxes = {}  # 存储标签复选框映射
        self.init_ui()
        self.load_tags()

    def init_ui(self):
        """初始化界面"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # 标签选择区域
        tags_group = QGroupBox("标签选择")
        tags_layout = QVBoxLayout()
        
        # 创建滚动区域以容纳可能很多的标签
        self.scroll_area = QScrollArea()
        self.scroll_widget = QWidget()
        # 使用流式布局替代垂直布局，标签自动从左到右排列
        self.tags_inner_layout = FlowLayout(margin=5, spacing=8)
        
        self.scroll_widget.setLayout(self.tags_inner_layout)
        self.scroll_area.setWidget(self.scroll_widget)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setMaximumHeight(120)  # 减小最大高度，流式布局更紧凑
        
        tags_layout.addWidget(self.scroll_area)
        
        # 标签按钮区域
        button_layout = QHBoxLayout()
        
        # 刷新标签按钮
        self.refresh_tags_btn = QPushButton("刷新标签")
        self.refresh_tags_btn.clicked.connect(self.load_tags)
        button_layout.addWidget(self.refresh_tags_btn)
        
        # 添加新标签按钮
        self.add_tag_btn = QPushButton("添加标签")
        self.add_tag_btn.clicked.connect(self.add_new_tag)
        button_layout.addWidget(self.add_tag_btn)
        
        # 删除未使用标签按钮
        self.delete_unused_tags_btn = QPushButton("删除未用标签")
        self.delete_unused_tags_btn.clicked.connect(self.delete_unused_tags)
        button_layout.addWidget(self.delete_unused_tags_btn)
        
        button_layout.addStretch()  # 弹性空间
        tags_layout.addLayout(button_layout)
        
        tags_group.setLayout(tags_layout)
        layout.addWidget(tags_group)
        self.setLayout(layout)

    def load_tags(self):
        """加载所有可用标签"""
        # 清除现有的复选框
        for checkbox in self.tag_checkboxes.values():
            checkbox.setParent(None)
        self.tag_checkboxes.clear()
        # 清空内部布局
        for i in reversed(range(self.tags_inner_layout.count())):
            self.tags_inner_layout.removeItem(i)
            item = self.tags_inner_layout.itemAt(i)
            if item.widget():
                item.widget().setParent(None)

        # 从控制器获取所有标签
        if self.controller:
            self.all_tags = self.controller.get_all_tags()
        else:
            # 如果没有控制器，显示空信息
            self.all_tags = []

        # 创建标签复选框
        for tag in self.all_tags:
            checkbox = QCheckBox(tag['name'])
            checkbox.setObjectName(f"tag_checkbox_{tag['id']}")
            checkbox.setChecked(tag['id'] in self.selected_tag_ids)
            checkbox.stateChanged.connect(self.on_tag_state_changed)
            
            # 为复选框添加胶囊样式
            checkbox.setStyleSheet("""
                QCheckBox {
                    spacing: 4px;
                    padding: 4px 10px;
                    border-radius: 12px;
                    background-color: #f5f5f5;
                }
                QCheckBox:hover {
                    background-color: #e8e8e8;
                }
                QCheckBox::indicator {
                    width: 14px;
                    height: 14px;
                    border-radius: 3px;
                }
                QCheckBox::indicator:checked {
                    background-color: #4CAF50;
                    border: 2px solid #4CAF50;
                }
                QCheckBox::indicator:unchecked {
                    background-color: white;
                    border: 2px solid #ccc;
                }
            """)
            
            self.tag_checkboxes[tag['id']] = checkbox
            self.tags_inner_layout.addWidget(checkbox)

    def update_tag_selections(self, tag_ids=None):
        """更新标签选择状态"""
        if tag_ids is not None:
            self.selected_tag_ids = set(tag_ids)
        for tag_id, checkbox in self.tag_checkboxes.items():
            checkbox.setChecked(tag_id in self.selected_tag_ids)

    def get_selected_tag_ids(self):
        """获取选中的标签ID集合"""
        return self.selected_tag_ids.copy()

    def set_selected_tag_ids(self, tag_ids):
        """设置选中的标签ID集合"""
        self.selected_tag_ids = set(tag_ids)
        self.update_tag_selections()

    def on_tag_state_changed(self, state):
        """处理标签选择状态变化"""
        sender = self.sender()
        # 提取标签ID
        for tag_id, checkbox in self.tag_checkboxes.items():
            if checkbox == sender:
                if state == Qt.CheckState.Checked.value:
                    self.selected_tag_ids.add(tag_id)
                else:
                    self.selected_tag_ids.discard(tag_id)
                break
        # 发出信号通知标签已更改
        self.tagsChanged.emit(self.selected_tag_ids)

    def add_new_tag(self):
        """添加新标签"""
        tag_name, ok = QInputDialog.getText(self, "添加新标签", "请输入标签名称:")
        if ok and tag_name.strip() and self.controller:
            result = self.controller.add_tag(tag_name.strip())
            if result:
                QMessageBox.information(self, "成功", f"标签 '{tag_name}' 添加成功！")
                self.load_tags()  # 重新加载标签列表
            else:
                QMessageBox.warning(self, "错误", f"标签 '{tag_name}' 已存在或添加失败！")

    def delete_unused_tags(self):
        """删除未被使用的标签"""
        if not self.controller:
            return

        unused_tags = self.controller.get_unused_tags()
        if not unused_tags:
            QMessageBox.information(self, "提示", "没有未被使用的标签，无需删除。")
            return

        # 显示未使用的标签列表供用户确认
        unused_tag_names = [tag['name'] for tag in unused_tags]
        tag_list_str = "\n".join(unused_tag_names)

        reply = QMessageBox.question(
            self,
            "确认删除未使用标签",
            f"以下标签未被任何日记使用，是否删除？\n\n{tag_list_str}\n\n确认删除吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            deleted_count = 0
            failed_count = 0

            for tag in unused_tags:
                try:
                    # 尝试删除标签
                    success = self.controller.delete_tag_by_id(tag['id'])
                    if success:
                        deleted_count += 1
                    else:
                        failed_count += 1
                except Exception as e:
                    failed_count += 1
                    print(f"删除标签失败: {e}")

            QMessageBox.information(self, "删除结果", 
                                   f"删除完成！\n成功删除: {deleted_count} 个\n失败: {failed_count} 个")
            self.load_tags()  # 重新加载标签列表