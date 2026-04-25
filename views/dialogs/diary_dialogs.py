"""
日记对话框组件 - 从 main_window.py 解耦出来的对话框类
"""
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, QLabel, QPushButton, 
                            QCheckBox, QScrollArea, QWidget, QGroupBox, QScrollArea, QInputDialog, 
                            QLineEdit, QCheckBox, QMessageBox, QFileDialog, QApplication)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence

from widgets.TagSelectorWidget import TagSelectorWidget
import os
from controllers.enhanced_diary_controller import EnhancedDiaryController


class DiaryEditDialog(QDialog):
    """日记编辑对话框"""
    
    def __init__(self, parent=None, diary=None):
        super().__init__(parent)
        self.diary = diary
        self.all_tags = []  # 存储所有可用标签
        self.selected_tag_ids = set()  # 存储当前选中的标签ID
        self.tag_checkboxes = {}  # 存储标签复选框映射
        self.init_ui()
        self.load_data()
        self.load_tags()  # 加载所有标签
        self.update_tag_selections()  # 更新标签选择状态
    
    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle("编辑日记" if self.diary else "新建日记")
        # 设置窗口大小
        self.resize(600, 500)  # 增加高度以容纳标签选择
        
        # 设置窗口居中于父窗口
        self.center_on_parent()
        
        layout = QVBoxLayout()
        
        # 信息显示区域（仅在编辑现有日记时显示）
        if self.diary:
            info_layout = QHBoxLayout()
            self.id_label = QLabel(f"ID: {self.diary.id}")
            self.date_label = QLabel(f"日期: {self.diary.date}")
            self.views_label = QLabel(f"查看次数: {self.diary.view_count}")
            # 设置标签对齐
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
        
        # 创建滚动区域以容纳可能很多的标签
        self.scroll_area = QScrollArea()
        self.scroll_widget = QWidget()
        self.tags_inner_layout = QVBoxLayout()
        
        self.scroll_widget.setLayout(self.tags_inner_layout)
        self.scroll_area.setWidget(self.scroll_widget)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setMaximumHeight(150)  # 设置最大高度
        
        tags_layout.addWidget(self.scroll_area)
        tags_group.setLayout(tags_layout)
        layout.addWidget(tags_group)
        
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
        
        # 管理特定标签按钮
        self.manage_specific_tag_btn = QPushButton("管理标签")
        self.manage_specific_tag_btn.clicked.connect(self.manage_specific_tag)
        button_layout.addWidget(self.manage_specific_tag_btn)
        
        button_layout.addStretch()  # 弹性空间
        tags_layout.addLayout(button_layout)
        
        # 按钮区域 - 居中对齐
        button_layout = QHBoxLayout()
        button_layout.addStretch()  # 左侧弹性空间
        
        self.save_btn = QPushButton("保存")
        self.save_btn.clicked.connect(self.accept)
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        
        button_layout.addWidget(self.save_btn)
        button_layout.addWidget(self.cancel_btn)
        button_layout.addStretch()  # 右侧弹性空间
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
        # 设置快捷键
        self.save_btn.setShortcut(QKeySequence.StandardKey.Save)
        self.cancel_btn.setShortcut(QKeySequence.StandardKey.Cancel)
    
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
    
    def load_data(self):
        """加载日记数据"""
        if self.diary:
            self.content_edit.setPlainText(self.diary.content)
            # 如果是编辑现有日记，加载其已有的标签
            if hasattr(self.diary, 'tags') and self.diary.tags:
                self.selected_tag_ids = {tag['id'] for tag in self.diary.tags}
    
    def load_tags(self):
        """加载所有可用标签"""
        # 清除现有的复选框
        for checkbox in self.tag_checkboxes.values():
            checkbox.setParent(None)
        self.tag_checkboxes.clear()
        
        # 清空内部布局
        for i in reversed(range(self.tags_inner_layout.count())):
            item = self.tags_inner_layout.itemAt(i)
            if item and item.widget():
                item.widget().setParent(None)
        
        # 从控制器获取所有标签
        try:
            # 通过父窗口获取控制器
            controller = self.parent().controller
            self.all_tags = controller.get_all_tags()
        except:
            # 如果无法访问父窗口控制器，则创建临时控制器
            from controllers.enhanced_diary_controller import EnhancedDiaryController
            import os
            db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "diary.db")
            temp_controller = EnhancedDiaryController(db_path)
            self.all_tags = temp_controller.get_all_tags()
        
        # 应用搜索过滤并渲染标签
        self.filter_tags(self.tag_search_input.text() if hasattr(self, 'tag_search_input') else "")
    
    def filter_tags(self, keyword=""):
        """根据关键词过滤标签列表"""
        keyword = keyword.strip().lower()
        
        # 清空当前显示的复选框
        for checkbox in self.tag_checkboxes.values():
            checkbox.setParent(None)
        self.tag_checkboxes.clear()
        
        # 清空内部布局中的所有控件
        for i in reversed(range(self.tags_inner_layout.count())):
            item = self.tags_inner_layout.itemAt(i)
            if item and item.widget():
                item.widget().setParent(None)
        
        # 过滤标签
        filtered_tags = self.all_tags
        if keyword:
            filtered_tags = [tag for tag in self.all_tags if keyword in tag['name'].lower()]
        
        # 创建过滤后的标签复选框
        for tag in filtered_tags:
            checkbox = QCheckBox(tag['name'])
            checkbox.setObjectName(f"tag_checkbox_{tag['id']}")
            checkbox.setChecked(tag['id'] in self.selected_tag_ids)
            checkbox.stateChanged.connect(self.on_tag_state_changed)
            self.tag_checkboxes[tag['id']] = checkbox
            self.tags_inner_layout.addWidget(checkbox)
        
        # 显示过滤结果数量
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
        # 提取标签ID
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
            try:
                # 通过父窗口获取控制器
                controller = self.parent().controller
                result = controller.add_tag(tag_name.strip())
                if result:
                    QMessageBox.information(self, "成功", f"标签 '{tag_name}' 添加成功！")
                    self.load_tags()  # 重新加载标签列表
                else:
                    QMessageBox.warning(self, "错误", f"标签 '{tag_name}' 已存在或添加失败！")
            except:
                # 如果无法访问父窗口控制器，则创建临时控制器
                from controllers.enhanced_diary_controller import EnhancedDiaryController
                import os
                db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "diary.db")
                temp_controller = EnhancedDiaryController(db_path)
                result = temp_controller.add_tag(tag_name.strip())
                if result:
                    QMessageBox.information(self, "成功", f"标签 '{tag_name}' 添加成功！")
                    self.load_tags()  # 重新加载标签列表
                else:
                    QMessageBox.warning(self, "错误", f"标签 '{tag_name}' 已存在或添加失败！")

    def delete_unused_tags(self):
        """删除未被使用的标签"""
        try:
            # 通过父窗口获取控制器
            controller = self.parent().controller
            unused_tags = controller.get_unused_tags()
        except:
            # 如果无法访问父窗口控制器，则创建临时控制器
            from controllers.enhanced_diary_controller import EnhancedDiaryController
            import os
            db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "diary.db")
            temp_controller = EnhancedDiaryController(db_path)
            unused_tags = temp_controller.get_unused_tags()
        
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
            self.load_tags()  # 重新加载标签列表

    def manage_specific_tag(self):
        """管理特定标签（用于删除特定标签）"""
        try:
            # 通过父窗口获取控制器
            controller = self.parent().controller
            all_tags = controller.get_all_tags()
        except:
            # 如果无法访问父窗口控制器，则创建临时控制器
            from controllers.enhanced_diary_controller import EnhancedDiaryController
            import os
            db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "diary.db")
            temp_controller = EnhancedDiaryController(db_path)
            all_tags = temp_controller.get_all_tags()
        
        if not all_tags:
            QMessageBox.information(self, "提示", "当前没有标签。")
            return
        
        # 创建标签列表供用户选择
        tag_names = [tag['name'] for tag in all_tags]
        selected_tag, ok = QInputDialog.getItem(self, "选择标签", "选择要管理的标签:", tag_names, 0, False)
        
        if not (ok and selected_tag):
            return
        
        # 查找所选标签的详细信息
        selected_tag_detail = next((tag for tag in all_tags if tag['name'] == selected_tag), None)
        if not selected_tag_detail:
            return
        
        # 检查标签是否被使用
        try:
            diaries_using_tag = controller.get_diaries_by_tag_id(selected_tag_detail['id'])
            usage_count = len(diaries_using_tag)
        except:
            from controllers.enhanced_diary_controller import EnhancedDiaryController
            import os
            db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "diary.db")
            temp_controller = EnhancedDiaryController(db_path)
            diaries_using_tag = temp_controller.get_diaries_by_tag_id(selected_tag_detail['id'])
            usage_count = len(diaries_using_tag)
        
        # 根据使用情况决定操作
        if usage_count > 0:
            reply = QMessageBox.question(
                self,
                "标签正在被使用",
                f"标签 '{selected_tag}' 正在被 {usage_count} 篇日记使用，无法删除。\n\n"
                f"您可以选择其他标签进行操作。",
                QMessageBox.StandardButton.Ok
            )
        else:
            reply = QMessageBox.question(
                self,
                "确认删除未使用标签",
                f"标签 '{selected_tag}' 未被任何日记使用，是否删除？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                try:
                    success = controller.delete_tag_by_id(selected_tag_detail['id'])
                    if success:
                        QMessageBox.information(self, "成功", f"标签 '{selected_tag}' 已删除。")
                        self.load_tags()  # 重新加载标签列表
                    else:
                        QMessageBox.warning(self, "失败", f"删除标签 '{selected_tag}' 失败。")
                except Exception as e:
                    QMessageBox.critical(self, "错误", f"删除标签时发生错误: {str(e)}")
    
    def get_content(self):
        """获取内容"""
        return self.content_edit.toPlainText()
    
    def get_selected_tag_ids(self):
        """获取选中的标签ID列表"""
        return list(self.selected_tag_ids)


class DiaryViewDialog(QDialog):
    """日记查看对话框"""
    
    def __init__(self, diary, parent=None, readonly=False):
        super().__init__(parent)
        self.diary = diary
        self.readonly = readonly
        self.init_ui()
        self.load_data()
    
    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle("查看日记")
        # 设置窗口大小
        self.resize(700, 600)
        
        # 设置窗口居中于父窗口
        self.center_on_parent()
        
        layout = QVBoxLayout()
        
        # 信息显示区域
        info_layout = QHBoxLayout()
        self.id_label = QLabel(f"ID: {self.diary.id}")
        self.date_label = QLabel(f"日期: {self.diary.date}")
        self.views_label = QLabel(f"查看次数: {self.diary.view_count}")
        # 设置标签居中对齐
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
        
        # 标签选择区域
        try:
            controller = self.parent().controller
        except:
            from controllers.enhanced_diary_controller import EnhancedDiaryController
            import os
            db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "diary.db")
            controller = EnhancedDiaryController(db_path)
        
        # 获取日记的当前标签ID
        initial_tag_ids = []
        if hasattr(self.diary, 'tags') and self.diary.tags:
            initial_tag_ids = [tag['id'] for tag in self.diary.tags]
        
        # 创建标签选择组件
        self.tag_selector = TagSelectorWidget(self, controller, initial_tag_ids)
        layout.addWidget(self.tag_selector)
        
        # 按钮区域 - 居中对齐
        button_layout = QHBoxLayout()
        button_layout.addStretch()  # 左侧弹性空间
        
        # 保存标签按钮
        self.save_tags_btn = QPushButton("保存标签")
        self.save_tags_btn.clicked.connect(self.save_tags)
        self.save_tags_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; }")
        button_layout.addWidget(self.save_tags_btn)
        
        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.close)
        
        button_layout.addWidget(self.close_btn)
        button_layout.addStretch()  # 右侧弹性空间
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
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
    
    def load_data(self):
        """加载日记数据"""
        self.content_display.setPlainText(self.diary.content)
    
    def save_tags(self):
        """保存标签更改到数据库"""
        try:
            # 通过父窗口获取控制器
            controller = self.parent().controller
        except:
            # 如果无法访问父窗口控制器，则创建临时控制器
            from controllers.enhanced_diary_controller import EnhancedDiaryController
            import os
            db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "diary.db")
            controller = EnhancedDiaryController(db_path)
        
        # 从标签选择组件获取选中的标签ID
        selected_tag_ids = self.tag_selector.get_selected_tag_ids()
        
        # 更新日记的标签
        tag_ids_list = list(selected_tag_ids)
        success = controller.assign_tags_to_diary(self.diary.id, tag_ids_list)
        
        if success:
            QMessageBox.information(self, "成功", "标签更新成功！")
            # 更新日记对象的标签
            try:
                # 获取更新后的标签信息
                self.diary.tags = controller.get_tags_by_diary_id(self.diary.id)
            except:
                import os
                from controllers.enhanced_diary_controller import EnhancedDiaryController
                db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "diary.db")
                temp_controller = EnhancedDiaryController(db_path)
                self.diary.tags = temp_controller.get_tags_by_diary_id(self.diary.id)
        else:
            QMessageBox.warning(self, "错误", "标签更新失败！")