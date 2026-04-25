"""
标签管理对话框组件 - 处理标签相关的UI和逻辑
"""
from PyQt6.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                            QScrollArea, QWidget, QGroupBox, QLineEdit, 
                            QCheckBox, QMessageBox, QInputDialog)
from PyQt6.QtCore import Qt


class TagManagerMixin:
    """标签管理功能混入类"""
    
    def init_tag_manager(self):
        """初始化标签管理器属性"""
        self.all_tags = []
        self.selected_tag_ids = set()
        self.tag_checkboxes = {}
    
    def setup_tag_ui(self, parent_layout):
        """设置标签选择UI"""
        tags_group = QGroupBox("标签选择")
        tags_layout = QVBoxLayout()
        
        # 标签搜索框
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("搜索标签:"))
        self.tag_search_input = QLineEdit()
        self.tag_search_input.setPlaceholderText("输入关键词过滤标签...")
        self.tag_search_input.textChanged.connect(self.filter_tags)
        search_layout.addWidget(self.tag_search_input)
        tags_layout.addLayout(search_layout)
        
        # 创建滚动区域
        self.scroll_area = QScrollArea()
        self.scroll_widget = QWidget()
        self.tags_inner_layout = QVBoxLayout()
        
        self.scroll_widget.setLayout(self.tags_inner_layout)
        self.scroll_area.setWidget(self.scroll_widget)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setMaximumHeight(150)
        
        tags_layout.addWidget(self.scroll_area)
        tags_group.setLayout(tags_layout)
        parent_layout.addWidget(tags_group)
        
        # 标签按钮区域
        btn_layout = QHBoxLayout()
        
        self.refresh_tags_btn = QPushButton("刷新标签")
        self.refresh_tags_btn.clicked.connect(self.load_tags)
        btn_layout.addWidget(self.refresh_tags_btn)
        
        self.add_tag_btn = QPushButton("添加标签")
        self.add_tag_btn.clicked.connect(self.add_new_tag)
        btn_layout.addWidget(self.add_tag_btn)
        
        self.delete_unused_tags_btn = QPushButton("删除未用标签")
        self.delete_unused_tags_btn.clicked.connect(self.delete_unused_tags)
        btn_layout.addWidget(self.delete_unused_tags_btn)
        
        self.manage_specific_tag_btn = QPushButton("管理标签")
        self.manage_specific_tag_btn.clicked.connect(self.manage_specific_tag)
        btn_layout.addWidget(self.manage_specific_tag_btn)
        
        btn_layout.addStretch()
        tags_layout.addLayout(btn_layout)
    
    def get_controller(self):
        """获取控制器实例"""
        try:
            return self.parent().controller
        except:
            from controllers.enhanced_diary_controller import EnhancedDiaryController
            from config.config import get_db_path
            return EnhancedDiaryController(get_db_path())
    
    def load_tags(self):
        """加载所有可用标签"""
        for checkbox in self.tag_checkboxes.values():
            checkbox.setParent(None)
        self.tag_checkboxes.clear()
        
        for i in reversed(range(self.tags_inner_layout.count())):
            item = self.tags_inner_layout.itemAt(i)
            if item and item.widget():
                item.widget().setParent(None)
        
        controller = self.get_controller()
        self.all_tags = controller.get_all_tags()
        
        keyword = self.tag_search_input.text() if hasattr(self, 'tag_search_input') else ""
        self.filter_tags(keyword)
    
    def filter_tags(self, keyword=""):
        """根据关键词过滤标签列表"""
        keyword = keyword.strip().lower()
        
        for checkbox in self.tag_checkboxes.values():
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
            checkbox.setObjectName(f"tag_checkbox_{tag['id']}")
            checkbox.setChecked(tag['id'] in self.selected_tag_ids)
            checkbox.stateChanged.connect(self.on_tag_state_changed)
            self.tag_checkboxes[tag['id']] = checkbox
            self.tags_inner_layout.addWidget(checkbox)
        
        if keyword:
            self.tag_search_input.setPlaceholderText(f"找到 {len(filtered_tags)} 个标签")
        else:
            self.tag_search_input.setPlaceholderText("输入关键词过滤标签...")
    
    def update_tag_selections(self):
        """更新标签选择状态"""
        for tag_id, checkbox in self.tag_checkboxes.items():
            checkbox.setChecked(tag_id in self.selected_tag_ids)
    
    def on_tag_state_changed(self, state):
        """处理标签选择状态变化"""
        sender = self.sender()
        for tag_id, checkbox in self.tag_checkboxes.items():
            if checkbox == sender:
                if state == Qt.CheckState.Checked.value:
                    self.selected_tag_ids.add(tag_id)
                else:
                    self.selected_tag_ids.discard(tag_id)
                break
    
    def add_new_tag(self):
        """添加新标签"""
        tag_name, ok = QInputDialog.getText(self, "添加新标签", "请输入标签名称:")
        if ok and tag_name.strip():
            controller = self.get_controller()
            result = controller.add_tag(tag_name.strip())
            if result:
                QMessageBox.information(self, "成功", f"标签 '{tag_name}' 添加成功！")
                self.load_tags()
            else:
                QMessageBox.warning(self, "错误", f"标签 '{tag_name}' 已存在或添加失败！")
    
    def delete_unused_tags(self):
        """删除未被使用的标签"""
        controller = self.get_controller()
        unused_tags = controller.get_unused_tags()
        
        if not unused_tags:
            QMessageBox.information(self, "提示", "没有未被使用的标签，无需删除。")
            return
        
        unused_tag_names = [tag['name'] for tag in unused_tags]
        tag_list_str = "\n".join(unused_tag_names)
        
        reply = QMessageBox.question(
            self, "确认删除未使用标签",
            f"以下标签未被任何日记使用，是否删除？\n\n{tag_list_str}\n\n确认删除吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            deleted_count = 0
            failed_count = 0
            
            for tag in unused_tags:
                try:
                    success = controller.delete_tag_by_id(tag['id'])
                    if success:
                        deleted_count += 1
                    else:
                        failed_count += 1
                except Exception as e:
                    failed_count += 1
                    print(f"删除标签失败: {e}")
            
            QMessageBox.information(self, "删除结果", 
                                   f"删除完成！\n成功删除: {deleted_count} 个\n失败: {failed_count} 个")
            self.load_tags()
    
    def manage_specific_tag(self):
        """管理特定标签"""
        controller = self.get_controller()
        all_tags = controller.get_all_tags()
        
        if not all_tags:
            QMessageBox.information(self, "提示", "当前没有标签。")
            return
        
        tag_names = [tag['name'] for tag in all_tags]
        selected_tag, ok = QInputDialog.getItem(
            self, "选择标签", "选择要管理的标签:", tag_names, 0, False
        )
        
        if not (ok and selected_tag):
            return
        
        selected_tag_detail = next(
            (tag for tag in all_tags if tag['name'] == selected_tag), None
        )
        if not selected_tag_detail:
            return
        
        diaries_using_tag = controller.get_diaries_by_tag_id(selected_tag_detail['id'])
        usage_count = len(diaries_using_tag)
        
        if usage_count > 0:
            QMessageBox.information(
                self, "标签正在被使用",
                f"标签 '{selected_tag}' 正在被 {usage_count} 篇日记使用，无法删除。"
            )
        else:
            reply = QMessageBox.question(
                self, "确认删除未使用标签",
                f"标签 '{selected_tag}' 未被任何日记使用，是否删除？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                try:
                    success = controller.delete_tag_by_id(selected_tag_detail['id'])
                    if success:
                        QMessageBox.information(self, "成功", f"标签 '{selected_tag}' 已删除。")
                        self.load_tags()
                    else:
                        QMessageBox.warning(self, "失败", f"删除标签 '{selected_tag}' 失败。")
                except Exception as e:
                    QMessageBox.critical(self, "错误", f"删除标签时发生错误: {str(e)}")
    
    def get_selected_tag_ids(self):
        """获取选中的标签ID列表"""
        return list(self.selected_tag_ids)
