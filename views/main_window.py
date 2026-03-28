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
from utils.theme_utils import ThemeManager
from widgets.TagSelectorWidget import TagSelectorWidget
from views.search_dialog import SearchDialog  # 导入解耦的搜索对话框
from views.diary_dialogs import DiaryEditDialog, DiaryViewDialog  # 导入解耦的对话框





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


