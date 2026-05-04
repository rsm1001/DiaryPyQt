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

from models.entities.diary import Diary
from models.table_models.diary_table_model import DiaryTableModel  # 导入解耦后的模型
from controllers.enhanced_diary_controller import EnhancedDiaryController
from utils.theme_utils import ThemeManager
from utils.formatters import format_tags_html  # 导入解耦的格式化工具
from widgets.TagSelectorWidget import TagSelectorWidget
from views.components.toolbar import MainToolBar  # 导入解耦的工具栏组件
from views.components.menu_bar import MainMenuBar  # 导入解耦的菜单栏组件
from views.search_dialog import SearchDialog  # 导入解耦的搜索对话框
from views.dialogs.diary_dialogs import DiaryEditDialog, DiaryViewDialog  # 导入解耦的对话框
from views.dialogs.trash_dialog import TrashDialog  # 导入垃圾桶对话框
from views.delegates.tag_delegate import TagDelegate  # 导入标签委托





class MainWindow(QMainWindow):
    """主窗口"""
    
    def __init__(self, db_path: str = None):
        super().__init__()
        self.controller = EnhancedDiaryController(db_path)
        self.db_path = db_path
        self.current_theme = 'light'
        
        # 启动时清理旧查看日志（只保留昨天和今天的记录）
        self.controller.cleanup_old_view_logs()
        
        # 初始化UI组件管理器
        self.toolbar_manager = MainToolBar(self)
        self.menu_manager = MainMenuBar(self)
        
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
        
        # 创建工具栏（通过组件管理器）
        self.toolbar_manager.create()
        
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
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)  # 标签列可调整
        self.table_view.setColumnWidth(3, 80)  # 设置标签列默认宽度为80像素
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)  # 内容预览列拉伸填充剩余空间
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)  # 设置表头居中对齐
        
        # 设置标签列的自定义委托
        self.tag_delegate = TagDelegate(self.table_view)
        self.table_view.setItemDelegateForColumn(3, self.tag_delegate)
        
        # 固定行高，防止标签撑大表格
        self.table_view.verticalHeader().setDefaultSectionSize(28)
        self.table_view.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        
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
        
        # 启用鼠标悬停提示（不计入查看次数）
        self.table_view.setMouseTracking(True)
        self.table_view.setToolTipDuration(999999)  # 不自动消失
        self.table_view.viewport().setStyleSheet("""
            QToolTip {
                background-color: #fffde7;
                color: #333333;
                border: 2px solid #ffc107;
                border-radius: 8px;
                padding: 12px 16px;
                font-size: 13px;
                font-family: 'Microsoft YaHei', sans-serif;
                max-width: 600px;
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
        
        # 创建菜单栏（通过组件管理器）
        self.menu_manager.create()
        
        # 连接信号
        self.table_view.clicked.connect(self.on_table_clicked)
        self.table_view.customContextMenuRequested.connect(self.show_context_menu)
    
    def center_on_screen(self):
        """使窗口居中于屏幕"""
        screen_geometry = QApplication.primaryScreen().geometry()
        x = (screen_geometry.width() - self.width()) // 2
        y = (screen_geometry.height() - self.height()) // 2
        self.move(screen_geometry.x() + x, screen_geometry.y() + y)
    

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
        daily_stats = self.controller.get_daily_stats()
        today_views = self.controller.get_today_total_views()
        self.status_bar.showMessage(f"总计: {stats['total']} 篇日记 | "
                                  f"总查看次数: {stats['total_views']} | "
                                  f"平均查看次数: {stats['avg_views']} | "
                                  f"今日查看: {today_views} | "
                                  f"昨日查看: {daily_stats['yesterday_total_views']} | "
                                  f"历史最佳: {daily_stats['all_time_max_single_views']}")
    
    def on_table_clicked(self, index):
        """表格点击事件"""
        if index.isValid():
            diary = self.model.data(index, Qt.ItemDataRole.UserRole)
            if diary:
                # 构建标签HTML（使用解耦的格式化工具）
                tags_html = format_tags_html(diary.tags if hasattr(diary, 'tags') else [])
                
                self.detail_label.setText(f"<b>ID:</b> {diary.id}<br>"
                                        f"<b>日期:</b> {diary.date}<br>"
                                        f"<b>查看次数:</b> {diary.view_count}<br>"
                                        f"<b>标签:</b> {tags_html}<br><br>"
                                        f"<b>内容:</b><br>{diary.content}")
                
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
            # 增加查看次数并刷新显示
            self.controller.increment_view_count(diary.id)
            self.load_data()
    
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
        daily_stats = self.controller.get_daily_stats()
        
        if stats['total'] == 0:
            QMessageBox.information(self, "统计", "暂无日记")
            return
        
        stats_text = f"""统计信息：
总计日记数：{stats['total']}
总查看次数：{stats['total_views']}
平均查看次数：{stats['avg_views']}
昨日查看总数：{daily_stats['yesterday_total_views']}
历史最佳单日：{daily_stats['all_time_max_single_views']} ({daily_stats['all_time_max_date'] if daily_stats['all_time_max_date'] else 'N/A'})

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
    
    def open_trash(self):
        """打开垃圾桶对话框"""
        dialog = TrashDialog(self.controller, self)
        dialog.exec()
        self.load_data()  # 恢复日记后刷新列表


