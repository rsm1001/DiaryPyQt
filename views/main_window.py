"""
主窗口 - PyQt6版本
"""
import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                            QSplitter, QTableWidget, QTableWidgetItem, QHeaderView, 
                            QToolBar, QStatusBar, QMenuBar, QMenu, QFileDialog, 
                            QMessageBox, QDialog, QTextEdit, QLabel, QPushButton, 
                            QTabWidget, QFrame, QScrollArea, QGroupBox, QListWidget,
                            QListWidgetItem, QInputDialog, QLineEdit, QCheckBox, QTableView, QAbstractItemView)
from PyQt6.QtCore import Qt, QModelIndex, pyqtSignal, QTimer
from PyQt6.QtGui import QAction, QIcon, QFont, QKeySequence

from models.diary import Diary
from models.diary_table_model import DiaryTableModel  # 导入解耦后的模型
from controllers.enhanced_diary_controller import EnhancedDiaryController
from utils.themes import ThemeManager
from widgets.TagSelectorWidget import TagSelectorWidget





class MainWindow(QMainWindow):
    """主窗口"""
    
    def __init__(self, db_path: str = None):
        super().__init__()
        self.controller = EnhancedDiaryController(db_path)
        self.db_path = db_path
        self.current_theme = 'light'
        
        self.init_ui()
        self.setup_connections()
        self.load_data()
        self.apply_theme()
    
    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle("日记管理系统 - PyQt版")
        # 获取屏幕几何信息并居中显示
        screen_geometry = QApplication.primaryScreen().geometry()
        x = (screen_geometry.width() - 1000) // 2
        y = (screen_geometry.height() - 700) // 2
        self.setGeometry(x, y, 1000, 700)
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        layout = QVBoxLayout(central_widget)
        
        # 创建工具栏
        self.create_toolbar()
        
        # 创建分割器
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # 日记列表表格 - 使用QTableView配合自定义模型
        self.model = DiaryTableModel()
        self.table_view = QTableView()
        self.table_view.setModel(self.model)
        
        # 设置表头
        header = self.table_view.horizontalHeader()
        # 设置不同列的尺寸调整模式
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # ID列自适应内容
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # 日期列自适应内容
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # 查看次数列自适应内容
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # 标签列自适应内容
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)  # 内容预览列拉伸填充剩余空间
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)  # 设置表头居中对齐
        
        # 设置表格样式
        self.table_view.setStyleSheet("""
            QTableView {
                gridline-color: #d3d3d3;
                selection-background-color: #3ea6ff;
                selection-color: white;
            }
            QHeaderView::section {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #f2f2f2, stop:1 #e2e2e2);
                padding: 4px;
                border: 1px solid #d8d8d8;
                font-weight: bold;
                color: black;
            }
        """)
        
        # 设置选择行为
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        
        splitter.addWidget(self.table_view)
        
        # 底部区域（显示日记详情）
        detail_widget = QWidget()
        detail_layout = QVBoxLayout(detail_widget)
        
        self.detail_label = QLabel("请选择一篇日记查看详情")
        self.detail_label.setWordWrap(True)
        self.detail_label.setAlignment(Qt.AlignmentFlag.AlignLeft)  # 左对齐更易读
        self.detail_label.setContentsMargins(10, 10, 10, 10)  # 添加边距
        self.detail_label.setStyleSheet("""
            QLabel {
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 8px;
            }
        """)
        detail_layout.addWidget(self.detail_label)
        
        splitter.addWidget(detail_widget)
        splitter.setSizes([500, 200])  # 设置初始大小比例
        
        layout.addWidget(splitter)
        
        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # 创建菜单栏
        self.create_menu()
        
        # 连接信号
        self.table_view.clicked.connect(self.on_table_clicked)
        self.table_view.customContextMenuRequested.connect(self.show_context_menu)
    
    def center_on_screen(self):
        """使窗口居中于屏幕"""
        screen_geometry = QApplication.primaryScreen().geometry()
        x = (screen_geometry.width() - self.width()) // 2
        y = (screen_geometry.height() - self.height()) // 2
        self.move(screen_geometry.x() + x, screen_geometry.y() + y)
    
    def create_toolbar(self):
        """创建工具栏"""
        toolbar = self.addToolBar('Main')
        
        # 新建日记
        self.new_action = QAction(QIcon(), '新建日记', self)
        self.new_action.setShortcut('Ctrl+N')
        self.new_action.triggered.connect(self.new_diary)
        toolbar.addAction(self.new_action)
        
        # 随机查看
        self.random_action = QAction(QIcon(), '随机查看', self)
        self.random_action.setShortcut('Ctrl+R')
        self.random_action.triggered.connect(self.random_view)
        toolbar.addAction(self.random_action)
        
        # 随机删除
        self.random_delete_action = QAction(QIcon(), '随机删除', self)
        self.random_delete_action.triggered.connect(self.random_delete)
        toolbar.addAction(self.random_delete_action)
        
        # 搜索
        self.search_action = QAction(QIcon(), '搜索', self)
        self.search_action.setShortcut('Ctrl+F')
        self.search_action.triggered.connect(self.search_diary)
        toolbar.addAction(self.search_action)
        
        # 切换主题
        self.theme_action = QAction(QIcon(), '切换主题', self)
        self.theme_action.triggered.connect(self.toggle_theme)
        toolbar.addAction(self.theme_action)
        
        # 统计
        self.stats_action = QAction(QIcon(), '统计', self)
        self.stats_action.triggered.connect(self.show_statistics)
        toolbar.addAction(self.stats_action)
        
        # 刷新
        self.refresh_action = QAction(QIcon(), '刷新', self)
        self.refresh_action.setShortcut('F5')
        self.refresh_action.triggered.connect(self.load_data)
        toolbar.addAction(self.refresh_action)
    
    def create_menu(self):
        """创建菜单栏"""
        menubar = self.menuBar()
        
        # 文件菜单
        file_menu = menubar.addMenu('文件')
        
        export_action = QAction('导出数据...', self)
        export_action.triggered.connect(self.export_data)
        file_menu.addAction(export_action)
        
        import_action = QAction('导入数据...', self)
        import_action.triggered.connect(self.import_data)
        file_menu.addAction(import_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction('退出', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # 编辑菜单
        edit_menu = menubar.addMenu('编辑')
        
        new_action = QAction('新建日记', self)
        new_action.setShortcut('Ctrl+N')
        new_action.triggered.connect(self.new_diary)
        edit_menu.addAction(new_action)
        
        edit_menu.addSeparator()
        
        search_action = QAction('搜索', self)
        search_action.setShortcut('Ctrl+F')
        search_action.triggered.connect(self.search_diary)
        edit_menu.addAction(search_action)
        
        # 视图菜单
        view_menu = menubar.addMenu('视图')
        
        theme_action = QAction('切换主题', self)
        theme_action.triggered.connect(self.toggle_theme)
        view_menu.addAction(theme_action)
        
        # 工具菜单
        tools_menu = menubar.addMenu('工具')
        
        stats_action = QAction('统计信息', self)
        stats_action.triggered.connect(self.show_statistics)
        tools_menu.addAction(stats_action)
        
        # 帮助菜单
        help_menu = menubar.addMenu('帮助')
        
        about_action = QAction('关于', self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def setup_connections(self):
        """设置信号连接"""
        pass
    
    def load_data(self):
        """加载日记数据"""
        diaries = self.controller.get_all_diaries(limit=25)
        self.model.update_data(diaries)
        self.update_status_bar()
    
    def update_status_bar(self):
        """更新状态栏"""
        stats = self.controller.get_statistics()
        self.status_bar.showMessage(f"总计: {stats['total']} 篇日记 | "
                                  f"总查看次数: {stats['total_views']} | "
                                  f"平均查看次数: {stats['avg_views']}")
    
    def on_table_clicked(self, index):
        """表格点击事件"""
        if index.isValid():
            diary = self.model.data(index, Qt.ItemDataRole.UserRole)
            if diary:
                # 构建标签字符串
                tags_str = "无标签"
                if hasattr(diary, 'tags') and diary.tags:
                    tags_str = ", ".join([tag['name'] for tag in diary.tags])
                
                self.detail_label.setText(f"<b>ID:</b> {diary.id}<br>"
                                        f"<b>日期:</b> {diary.date}<br>"
                                        f"<b>查看次数:</b> {diary.view_count}<br>"
                                        f"<b>标签:</b> {tags_str}<br>"
                                        f"<b>内容:</b> {diary.content}")
                
                # 增加查看次数
                self.controller.increment_view_count(diary.id)
                self.load_data()  # 重新加载以更新查看次数
    
    def show_context_menu(self, position):
        """显示右键菜单"""
        menu = QMenu()
        
        view_action = menu.addAction("查看")
        edit_action = menu.addAction("编辑")
        delete_action = menu.addAction("删除")
        
        action = menu.exec(self.table_view.viewport().mapToGlobal(position))
        
        if action == view_action:
            self.view_selected()
        elif action == edit_action:
            self.edit_selected()
        elif action == delete_action:
            self.delete_selected()
    
    def new_diary(self):
        """新建日记"""
        dialog = DiaryEditDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            content = dialog.get_content()
            selected_tag_ids = dialog.get_selected_tag_ids()
            if content.strip():
                diary = self.controller.add_diary(content)
                if diary and selected_tag_ids:
                    # 为新日记分配选中的标签
                    self.controller.assign_tags_to_diary(diary.id, selected_tag_ids)
                self.load_data()
    
    def random_view(self):
        """随机查看日记"""
        diary_dict = self.controller.random_view_diary()
        if diary_dict:
            # diary_dict 已经是 Diary 对象，无需再次转换
            diary_obj = diary_dict
            dialog = DiaryViewDialog(diary_obj, self, readonly=True)
            dialog.exec()
            # 增加查看次数
            self.controller.increment_view_count(diary_obj.id)
            self.load_data()
        else:
            QMessageBox.information(self, "提示", "当前没有日记")
    
    def random_delete(self):
        """随机删除一篇日记（时间久远且查看次数多的优先）"""
        diary_dict = self.controller.get_diary_for_deletion()
        if not diary_dict:
            QMessageBox.information(self, "提示", "没有可删除的日记")
            return
        
        # 准备详细的消息文本
        content_preview = diary_dict.content[:200]  # 显示前200个字符
        if len(diary_dict.content) > 200:
            content_preview += "..."
        
        message = (f"即将随机删除一篇日记：\n\n"
                  f"ID: {diary_dict.id}\n"
                  f"日期: {diary_dict.date}\n"
                  f"查看次数: {diary_dict.view_count}\n\n"
                  f"内容:\n{content_preview}\n\n"
                  f"确定要删除这条日记吗？")
        
        reply = QMessageBox.question(
            self,
            "确认删除",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.controller.delete_diary_by_id(diary_dict.id)
            self.load_data()
            QMessageBox.information(self, "成功", f"日记 ID:{diary_dict.id} 已删除")
    
    def search_diary(self):
        """搜索日记"""
        dialog = SearchDialog(self.controller, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_data()
    
    def view_selected(self):
        """查看选中日记"""
        selected = self.table_view.selectionModel().selectedRows()
        if not selected:
            QMessageBox.warning(self, "警告", "请先选择一篇日记")
            return
        
        index = selected[0]
        diary = self.model.data(index, Qt.ItemDataRole.UserRole)
        if diary:
            dialog = DiaryViewDialog(diary, self, readonly=True)
            dialog.exec()
    
    def edit_selected(self):
        """编辑选中日记"""
        selected = self.table_view.selectionModel().selectedRows()
        if not selected:
            QMessageBox.warning(self, "警告", "请先选择一篇日记")
            return
        
        index = selected[0]
        diary = self.model.data(index, Qt.ItemDataRole.UserRole)
        if diary:
            dialog = DiaryEditDialog(self, diary)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                content = dialog.get_content()
                selected_tag_ids = dialog.get_selected_tag_ids()
                if content.strip():
                    self.controller.update_diary(diary.id, content)
                    # 更新日记的标签
                    self.controller.assign_tags_to_diary(diary.id, selected_tag_ids)
                    self.load_data()
    
    def delete_selected(self):
        """删除选中日记"""
        selected = self.table_view.selectionModel().selectedRows()
        if not selected:
            QMessageBox.warning(self, "警告", "请先选择一篇日记")
            return
        
        index = selected[0]
        diary = self.model.data(index, Qt.ItemDataRole.UserRole)
        if diary:
            reply = QMessageBox.question(
                self,
                "确认删除",
                f"确定要删除日记 ID:{diary.id} 吗？\n\n内容: {diary.content[:50]}...",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.controller.delete_diary_by_id(diary.id)
                self.load_data()
                QMessageBox.information(self, "成功", "日记已删除")
    
    def toggle_theme(self):
        """切换主题"""
        self.current_theme = 'dark' if self.current_theme == 'light' else 'light'
        self.apply_theme()
    
    def apply_theme(self):
        """应用主题"""
        theme_manager = ThemeManager()
        theme_manager.apply_theme(self, self.current_theme)
    
    def show_statistics(self):
        """显示统计信息"""
        stats = self.controller.get_statistics()
        
        if stats['total'] == 0:
            QMessageBox.information(self, "统计", "暂无日记")
            return
        
        stats_text = f"""统计信息：
总计日记数：{stats['total']}
总查看次数：{stats['total_views']}
平均查看次数：{stats['avg_views']}

最多查看的日记：
ID: {stats['most_viewed']['id'] if stats['most_viewed'] else 'N/A'}
查看次数: {stats['most_viewed']['view_count'] if stats['most_viewed'] else 'N/A'}
内容: {stats['most_viewed']['content'][:30] + '...' if stats['most_viewed'] and len(stats['most_viewed']['content']) > 30 else (stats['most_viewed']['content'] if stats['most_viewed'] else 'N/A') if stats['most_viewed'] else 'N/A'}

最少查看的日记：
ID: {stats['least_viewed']['id'] if stats['least_viewed'] else 'N/A'}
查看次数: {stats['least_viewed']['view_count'] if stats['least_viewed'] else 'N/A'}
内容: {stats['least_viewed']['content'][:30] + '...' if stats['least_viewed'] and len(stats['least_viewed']['content']) > 30 else (stats['least_viewed']['content'] if stats['least_viewed'] else 'N/A') if stats['least_viewed'] else 'N/A'}"""
        
        QMessageBox.information(self, "统计信息", stats_text)
    
    def export_data(self):
        """导出数据"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "导出数据", 
            "", 
            "JSON Files (*.json);;All Files (*)"
        )
        
        if file_path:
            if self.controller.export_to_json(file_path):
                QMessageBox.information(self, "成功", "数据导出成功")
            else:
                QMessageBox.critical(self, "错误", "数据导出失败")
    
    def import_data(self):
        """导入数据"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "导入数据", 
            "", 
            "JSON Files (*.json);;All Files (*)"
        )
        
        if file_path:
            result = self.controller.migrate_from_json(file_path)
            QMessageBox.information(self, "导入结果", f"成功导入 {result} 篇日记")
            self.load_data()
    
    def show_about(self):
        """显示关于对话框"""
        QMessageBox.about(
            self,
            "关于",
            "日记管理系统 PyQt版\n\n版本: 1.0\n作者: Assistant\n\n基于PyQt6开发的现代化日记管理系统。"
        )


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
        
        # 从控制器获取所有标签
        try:
            # 通过父窗口获取控制器
            controller = self.parent().controller
            self.all_tags = controller.get_all_tags()
        except:
            # 如果无法访问父窗口控制器，则创建临时控制器
            from controllers.enhanced_diary_controller import EnhancedDiaryController
            import os
            db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "diary.db")
            temp_controller = EnhancedDiaryController(db_path)
            self.all_tags = temp_controller.get_all_tags()
        
        # 创建标签复选框
        for tag in self.all_tags:
            checkbox = QCheckBox(tag['name'])
            checkbox.setObjectName(f"tag_checkbox_{tag['id']}")
            checkbox.setChecked(tag['id'] in self.selected_tag_ids)
            checkbox.stateChanged.connect(self.on_tag_state_changed)
            self.tag_checkboxes[tag['id']] = checkbox
            self.tags_inner_layout.addWidget(checkbox)
    
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
                db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "diary.db")
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
            db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "diary.db")
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
            db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "diary.db")
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
            db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "diary.db")
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
            db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "diary.db")
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
            db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "diary.db")
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
                db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "diary.db")
                temp_controller = EnhancedDiaryController(db_path)
                self.diary.tags = temp_controller.get_tags_by_diary_id(self.diary.id)
        else:
            QMessageBox.warning(self, "错误", "标签更新失败！")


class SearchDialog(QDialog):
    """搜索对话框"""
    
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.current_results = []  # 当前显示的结果
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