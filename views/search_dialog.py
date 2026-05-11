"""
搜索对话框 - 从主窗口中解耦出来的独立模块
"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QSplitter, 
                            QWidget, QListWidget, QListWidgetItem, QLabel, 
                            QLineEdit, QPushButton, QGroupBox, QGridLayout,
                            QMessageBox, QApplication)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence
from views.dialogs.base_dialog import CenteredDialogMixin, ContextMenuMixin


class SearchDialog(QDialog, CenteredDialogMixin, ContextMenuMixin):
    """搜索对话框 - 从主窗口解耦出来的功能"""

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.current_results = []  # 当前显示的结果
        self._current_item = None  # 当前右键点击的项
        self.init_ui()
        self.load_tags()  # 加载标签
    
    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle("搜索日记")
        # 设置窗口大小
        self.resize(700, 500)  # 增加窗口大小以容纳标签区域
        
        # 设置窗口居中于父窗口
        self.center_on_parent()
        
        layout = QVBoxLayout()
        
        # 创建水平分割器，左右分栏
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 左侧面板：搜索和标签
        left_panel = QWidget()
        left_layout = QVBoxLayout()
        
        # 搜索输入区域
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("关键词:"))
        self.keyword_input = QLineEdit()
        self.keyword_input.returnPressed.connect(self.perform_search)
        search_layout.addWidget(self.keyword_input)
        
        self.search_btn = QPushButton("搜索")
        self.search_btn.clicked.connect(self.perform_search)
        search_layout.addWidget(self.search_btn)
        
        left_layout.addLayout(search_layout)
        
        # 标签区域
        tags_group = QGroupBox("标签")
        tags_layout = QVBoxLayout()
        
        # 标签列表
        self.tags_list = QListWidget()
        self.tags_list.setMaximumWidth(200)  # 设置标签列表的最大宽度
        self.tags_list.itemClicked.connect(self.on_tag_clicked)
        tags_layout.addWidget(self.tags_list)
        
        # 标签操作按钮
        tag_button_layout = QHBoxLayout()
        
        self.refresh_tags_btn = QPushButton("刷新标签")
        self.refresh_tags_btn.clicked.connect(self.load_tags)
        tag_button_layout.addWidget(self.refresh_tags_btn)
        
        self.clear_filter_btn = QPushButton("清除筛选")
        self.clear_filter_btn.clicked.connect(self.clear_filter)
        tag_button_layout.addWidget(self.clear_filter_btn)
        
        # 添加删除未使用标签按钮
        self.delete_unused_tags_btn = QPushButton("删除未用标签")
        self.delete_unused_tags_btn.clicked.connect(self.delete_unused_tags)
        tag_button_layout.addWidget(self.delete_unused_tags_btn)
        
        tags_layout.addLayout(tag_button_layout)
        
        tags_group.setLayout(tags_layout)
        left_layout.addWidget(tags_group)
        
        left_panel.setLayout(left_layout)
        splitter.addWidget(left_panel)
        
        # 右侧面板：搜索结果
        right_panel = QWidget()
        right_layout = QVBoxLayout()
        
        # 结果标题
        self.result_title = QLabel("搜索结果")
        self.result_title.setStyleSheet("font-weight: bold; font-size: 12px;")
        right_layout.addWidget(self.result_title)
        
        # 结果列表
        self.results_list = QListWidget()
        right_layout.addWidget(self.results_list)
        
        # 结果计数
        self.result_count_label = QLabel("共 0 条结果")
        self.result_count_label.setStyleSheet("font-size: 10px; color: gray;")
        right_layout.addWidget(self.result_count_label)
        
        right_panel.setLayout(right_layout)
        splitter.addWidget(right_panel)
        
        # 设置分割器比例
        splitter.setSizes([250, 450])  # 左侧标签区域较窄，右侧结果区域较宽
        
        layout.addWidget(splitter)
        
        # 按钮区域 - 居中对齐
        button_layout = QHBoxLayout()
        button_layout.addStretch()  # 左侧弹性空间
        
        self.ok_btn = QPushButton("确定")
        self.ok_btn.clicked.connect(self.accept)
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        
        button_layout.addWidget(self.ok_btn)
        button_layout.addWidget(self.cancel_btn)
        button_layout.addStretch()  # 右侧弹性空间
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)

        # 设置焦点到输入框
        self.keyword_input.setFocus()

        # 设置结果列表的右键菜单
        self.setup_context_menu_for_list(self.results_list)

    def _on_result_item_clicked(self, item):
        """结果项被点击时保存引用"""
        self._current_item = item
    
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
    
    def load_tags(self):
        """加载所有标签"""
        self.tags_list.clear()
        
        # 从控制器获取所有标签
        tags = self.controller.get_all_tags()
        
        # 添加所有标签到列表
        for tag in tags:
            item = QListWidgetItem(f"#{tag['name']}")
            item.setData(Qt.ItemDataRole.UserRole, tag)
            self.tags_list.addItem(item)
        
        # 如果没有标签，显示提示信息
        if not tags:
            self.tags_list.addItem(QListWidgetItem("暂无标签"))
    
    def on_tag_clicked(self, item):
        """标签项被点击"""
        tag_data = item.data(Qt.ItemDataRole.UserRole)
        if tag_data:
            # 使用标签搜索日记
            tag_id = tag_data['id']
            diaries = self.controller.get_diaries_by_tag_id(tag_id)
            
            self.display_results(diaries, f"标签: #{tag_data['name']}")
    
    def perform_search(self):
        """执行关键词搜索"""
        keyword = self.keyword_input.text().strip()
        if not keyword:
            # 如果关键词为空，显示所有日记
            diaries = self.controller.get_all_diaries(limit=50)
            self.display_results(diaries, "全部日记")
            return
        
        # 执行关键词搜索
        results = self.controller.search_by_keyword(keyword)
        self.display_results(results, f"关键词: '{keyword}'")
    
    def display_results(self, diaries, search_type):
        """显示搜索结果"""
        self.results_list.clear()
        self.current_results = diaries
        
        for diary in diaries:
            # 获取日记的标签
            tags = self.controller.get_tags_by_diary_id(diary.id)
            tags_str = ""
            if tags:
                tags_str = f" [{', '.join([tag['name'] for tag in tags])}]"
            
            item = QListWidgetItem(f"[{diary.id}] {diary.date} (查看: {diary.view_count}){tags_str} - {diary.content[:50]}...")
            item.setData(Qt.ItemDataRole.UserRole, diary)
            self.results_list.addItem(item)
        
        # 更新结果计数
        count = len(diaries)
        self.result_count_label.setText(f"共 {count} 条结果 - {search_type}")
        
        if not diaries:
            self.results_list.addItem("没有找到匹配的日记")
    
    def clear_filter(self):
        """清除筛选，显示所有日记"""
        self.keyword_input.clear()
        diaries = self.controller.get_all_diaries(limit=50)
        self.display_results(diaries, "全部日记")
    
    def delete_unused_tags(self):
        """删除未被使用的标签"""
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

    def _remove_result_item(self, item):
        """从结果列表中移除项"""
        if item and item.listWidget():
            row = item.listWidget().row(item)
            item.listWidget().takeItem(row)
            if item in self.current_results:
                self.current_results.remove(item)
            self.result_count_label.setText(f"共 {len(self.current_results)} 条结果")

    def _refresh_search_results(self):
        """刷新搜索结果"""
        keyword = self.keyword_input.text().strip()
        if keyword:
            results = self.controller.search_by_keyword(keyword)
            self.display_results(results, f"关键词: '{keyword}'")
        else:
            results = self.controller.get_all_diaries(limit=50)
            self.display_results(results, "全部日记")