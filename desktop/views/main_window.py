"""
主窗口 - PyQt6版本

主窗口作为应用层协调者，专注于窗口装配与生命周期管理，
业务动作（新建/编辑/删除/批量、侧栏日历、热力图刷新、
主题/语言切换等）已下沉至 ``views.actions`` 子包。
"""
import logging
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QSplitter, QTableView, QStatusBar, QTabWidget, QMessageBox)

from i18n import _
from controllers.enhanced_diary_controller import EnhancedDiaryController
from desktop.config.settings import get_sync_settings
from desktop.sync.qt_worker import SyncPreviewWorker, SyncReviewWorker
from models.table_models.diary_table_model import DiaryTableModel
from views.actions import ActionFactory
from views.components.calendar.calendar_panel import CalendarPanelFactory
from views.components.configuration.column_config_manager import ColumnConfigManager
from views.components.menus.context_menu_builder import ContextMenuBuilder
from views.components.panels.detail_panel import DetailPanel
from views.components.heatmap import HeatmapPanelFactory
from views.components.window_chrome.menu_bar import MainMenuBar
from views.components.window_chrome.status_bar_manager import StatusBarManager
from views.components.tables.table_view_manager import TableViewManager
from views.components.window_chrome.toolbar import MainToolBar
from views.delegates.tag_delegate import TagDelegate
from views.sync_review import SyncReviewDialog

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """日记管理系统主窗口"""

    def __init__(self, db_path: Optional[str] = None):
        super().__init__()
        logger.info("主窗口初始化开始, db_path=%s", db_path)
        self.controller = EnhancedDiaryController(db_path)
        self.db_path = db_path
        self.current_theme = "light"
        self.current_date_filter = None
        self.show_heatmap = True
        self._sync_preview_worker = None
        self._sync_review_worker = None
        self._sync_review_dialog = None
        self._sync_review_follow_up = None

        # 启动时清理旧查看日志
        self.controller.cleanup_old_view_logs()

        # 初始化列配置管理器
        self.column_config_manager = ColumnConfigManager()

        # 初始化随机查看筛选管理器
        from views.components.filters.random_view_filter_manager import RandomViewFilterManager
        self.random_filter_manager = RandomViewFilterManager()

        # 初始化组件管理器
        self.toolbar_manager = MainToolBar(self)
        self.menu_manager = MainMenuBar(self)
        self.context_menu_builder = ContextMenuBuilder(self)

        # 初始化动作聚合工厂（必须在 UI 装配之前，以便侧栏/表格回调引用）
        self.actions = ActionFactory.create(self)

        # 初始化 UI
        self._init_ui()
        self._setup_connections()

        # 加载数据与应用主题
        self.load_data()
        self.apply_theme()
        logger.info("主窗口初始化完成")

    # ------------------------------------------------------------------
    # UI 装配
    # ------------------------------------------------------------------
    def _init_ui(self) -> None:
        """初始化用户界面"""
        self.setWindowTitle(_("日记管理系统 - PyQt版"))
        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(
            (screen.width() - 1100) // 2, (screen.height() - 770) // 2, 1100, 770
        )

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        central_layout = QVBoxLayout(central_widget)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)

        self.toolbar_manager.create()

        # 上部分割器：侧栏 + 主表格
        top_splitter = QSplitter(Qt.Orientation.Horizontal)
        top_splitter.addWidget(self._build_sidebar_tabs())
        top_splitter.addWidget(self._build_table_view())
        central_layout.addWidget(top_splitter, 3)

        # 详情面板
        self.detail_panel = DetailPanel()
        self.detail_panel.set_max_height(180, 80)
        central_layout.addWidget(self.detail_panel)

        # 状态栏
        self.status_bar_manager = StatusBarManager(QStatusBar())
        self.setStatusBar(self.status_bar_manager.status_bar)

        # 菜单
        self.menu_manager.create()
        logger.debug("UI 组件初始化完成")

    def _build_sidebar_tabs(self) -> QTabWidget:
        """构建侧栏 tabs：月历视图 + 热力图"""
        sidebar_tabs = QTabWidget()
        sidebar_tabs.setObjectName("SidebarTabs")
        sidebar_tabs.setFixedWidth(280)

        calendar_panel = CalendarPanelFactory.create_calendar_panel(
            self,
            on_date_selected=self.actions.calendar.on_date_selected,
            on_show_all=self.actions.calendar.show_all_diaries,
        )
        self.calendar_panel = calendar_panel
        self.calendar_tab_index = sidebar_tabs.addTab(calendar_panel, _("月历视图"))

        heatmap_panel = HeatmapPanelFactory.create_heatmap_panel(
            self,
            on_date_clicked=self.actions.calendar.on_date_selected,
            on_month_changed=self.actions.heatmap.on_month_changed,
        )
        self.heatmap_panel = heatmap_panel
        self.heatmap_tab_index = sidebar_tabs.addTab(heatmap_panel, _("热力图"))

        self.sidebar_tabs = sidebar_tabs
        self.sidebar_tabs.currentChanged.connect(
            self.actions.calendar.on_sidebar_tab_changed
        )
        return sidebar_tabs

    def _build_table_view(self) -> QTableView:
        """构建主表格视图"""
        self.model = DiaryTableModel(self.column_config_manager)
        self.table_view = QTableView()
        self.table_manager = TableViewManager(
            self.table_view, self.model, self.column_config_manager
        )
        self.table_manager.set_tag_delegate_by_id(TagDelegate(self.table_view))
        return self.table_view

    def _setup_connections(self) -> None:
        """设置表格信号连接"""
        self.table_manager.connect_clicked(self.actions.diary.on_table_clicked)
        self.table_manager.connect_context_menu(self.show_context_menu)
        self.table_manager.connect_selection_changed(self.on_selection_changed)

    # ------------------------------------------------------------------
    # 居中
    # ------------------------------------------------------------------
    def center_on_screen(self) -> None:
        """使窗口居中于屏幕"""
        screen = QApplication.primaryScreen().geometry()
        self.move(
            screen.x() + (screen.width() - self.width()) // 2,
            screen.y() + (screen.height() - self.height()) // 2,
        )

    # ------------------------------------------------------------------
    # 数据加载与状态
    # ------------------------------------------------------------------
    def on_selection_changed(self) -> None:
        """选择行变化时更新批量按钮状态"""
        count = self.table_manager.get_selected_count()
        self.toolbar_manager.set_batch_actions_enabled(count > 0)
        logger.debug("选中行数变化: %d", count)

    def review_server_sync(self) -> None:
        """?????????????????"""
        if self._sync_review_dialog is not None:
            self._sync_review_dialog.raise_()
            self._sync_review_dialog.activateWindow()
            return
        try:
            get_sync_settings()
        except ValueError:
            QMessageBox.information(self, "????", "???? DIARY_API_BASE_URL?")
            return
        dialog = SyncReviewDialog(self)
        self._sync_review_dialog = dialog
        dialog.refresh_requested.connect(self._start_sync_review)
        dialog.map_requested.connect(lambda: self._start_sync_review("map"))
        dialog.pull_requested.connect(lambda: self._start_sync_review("pull"))
        dialog.finished.connect(self._on_sync_review_dialog_finished)
        dialog.show()
        self._start_sync_review("preview")

    def _start_sync_review(self, operation: str = "preview") -> None:
        if self._sync_review_worker is not None or self._sync_review_dialog is None:
            return
        try:
            settings = get_sync_settings()
        except ValueError as exc:
            self._sync_review_dialog.show_error(str(exc))
            return
        diaries = [diary.to_dict() for diary in self.controller.get_all_diaries_with_tags()]
        worker = SyncReviewWorker(
            operation, diaries, str(self.db_path), settings.state_path, self
        )
        self._sync_review_worker = worker
        self._sync_review_dialog.set_busy(True)
        worker.completed.connect(self._on_sync_review_completed)
        worker.failed.connect(self._on_sync_review_failed)
        worker.finished.connect(self._on_sync_review_finished)
        worker.start()

    def _on_sync_review_completed(self, result: dict) -> None:
        operation = result.get("operation")
        if operation == "pull":
            self.load_data()
            self.statusBar().showMessage(
                f"??? {result.get('applied', 0)} ?????? {result.get('cursor', 0)}", 5000
            )
        elif operation == "map":
            self.statusBar().showMessage(
                f"??? {result.get('mapped', 0)} ???/?????", 5000
            )
        if operation != "preview":
            self._sync_review_follow_up = "preview"
            return
        if self._sync_review_dialog is not None:
            self._sync_review_dialog.set_result(result)
            self.statusBar().showMessage("????????", 5000)

    def _on_sync_review_failed(self, message: str) -> None:
        if self._sync_review_dialog is not None:
            self._sync_review_dialog.show_error(message)
        self.statusBar().showMessage("???????", 5000)

    def _on_sync_review_finished(self) -> None:
        self._sync_review_worker.deleteLater()
        self._sync_review_worker = None
        follow_up = self._sync_review_follow_up
        self._sync_review_follow_up = None
        if follow_up is not None:
            self._start_sync_review(follow_up)

    def _on_sync_review_dialog_finished(self) -> None:
        if self._sync_review_worker is not None and self._sync_review_worker.isRunning():
            self._sync_review_worker.requestInterruption()
        self._sync_review_dialog = None

    def preview_server_sync(self) -> None:
        """只读检查同步数据；服务器有历史日记时禁止自动上传。"""
        if self._sync_preview_worker is not None:
            return
        try:
            get_sync_settings()
        except ValueError:
            QMessageBox.information(self, "服务器检查", "请配置 DIARY_API_BASE_URL，并检查 DIARY_API_TIMEOUT。")
            return
        diaries = [diary.to_dict() for diary in self.controller.get_all_diaries_with_tags()]
        worker = SyncPreviewWorker(diaries, self)
        self._sync_preview_worker = worker
        worker.completed.connect(self._on_sync_preview_completed)
        worker.failed.connect(self._on_sync_preview_failed)
        worker.finished.connect(self._on_sync_preview_finished)
        self.statusBar().showMessage("正在检查服务器日记，请稍候……")
        worker.start()

    def _on_sync_preview_completed(self, result: dict) -> None:
        self.statusBar().showMessage("服务器日记检查已完成（只读）", 5000)
        QMessageBox.information(
            self, "服务器日记检查（只读）",
            f"本地日记：{result['local']} 篇\n"
            f"服务器同步记录中仍存在：{result['remote']} 篇\n"
            f"日期和内容相同：{result['same_content']} 篇\n"
            f"日期、正文和标签唯一匹配：{result['matched']} 篇\n"
            f"未匹配本地：{result['local_only']}，服务器：{result['remote_only']}；歧义：{result['ambiguous']}\n"
            "此检查不会上传、下载或修改任何日记；内容相同不代表已建立同步映射。",
        )

    def _on_sync_preview_failed(self, message: str) -> None:
        self.statusBar().showMessage("服务器日记检查失败", 5000)
        QMessageBox.warning(self, "服务器检查", message)

    def _on_sync_preview_finished(self) -> None:
        self._sync_preview_worker.deleteLater()
        self._sync_preview_worker = None

    def closeEvent(self, event) -> None:
        """????????????????"""
        if ((self._sync_preview_worker is not None and self._sync_preview_worker.isRunning())
                or (self._sync_review_worker is not None and self._sync_review_worker.isRunning())):
            event.ignore()
            self.statusBar().showMessage("?????????????????", 5000)
            return
        super().closeEvent(event)

    def load_data(self) -> None:
        """加载日记数据并刷新日历与热力图标记"""
        diaries = self.controller.get_all_diaries(limit=25)
        self.model.update_data(diaries)
        self._update_calendar_diary_marks()
        self.update_status_bar()
        logger.info("加载日记数据: %d 篇", len(diaries))

    def _update_calendar_diary_marks(self) -> None:
        """更新日历标记（含月历视图与热力图）"""
        self.actions.calendar.refresh_calendar_marks()

    def _refresh_heatmap(self) -> None:
        """刷新热力图委托给 HeatmapActions"""
        self.actions.heatmap.refresh_heatmap()

    def update_status_bar(self) -> None:
        """更新状态栏"""
        stats = self.controller.get_statistics()
        daily_stats = self.controller.get_daily_stats()
        today_views = self.controller.get_today_total_views()
        self.status_bar_manager.update_statistics(
            stats, daily_stats, today_views, self.current_date_filter
        )

    # ------------------------------------------------------------------
    # 右键菜单
    # ------------------------------------------------------------------
    def show_context_menu(self, position) -> None:
        """显示右键菜单"""
        count = self.table_manager.get_selected_count()
        if count == 0:
            return
        from views.components.menus.context_menu_builder import ContextMenuFactory

        handlers = {
            "view": self.actions.diary.view_selected,
            "edit": self.actions.diary.edit_selected,
            "delete": self.actions.diary.delete_selected,
            "batch_delete": self.actions.diary.batch_delete_selected,
            "batch_tag": self.actions.diary.batch_tag_selected,
        }
        menu = ContextMenuFactory.create_context_menu(self, count, handlers)
        if menu:
            menu.exec(self.table_view.viewport().mapToGlobal(position))
        logger.debug("显示右键菜单, 选中: %d 篇", count)

    # ------------------------------------------------------------------
    # 热力图显隐
    # ------------------------------------------------------------------
    def toggle_heatmap_visibility(self, checked: bool) -> None:
        """切换热力图 tab 的显隐（供菜单调用）"""
        self.actions.heatmap.toggle_visibility(checked)

    # ------------------------------------------------------------------
    # 委托给 DiaryActions
    # ------------------------------------------------------------------
    def on_table_clicked(self, index) -> None:
        self.actions.diary.on_table_clicked(index)

    def new_diary(self) -> None:
        self.actions.diary.new_diary()

    def random_view(self) -> None:
        self.actions.diary.random_view()

    def random_delete(self) -> None:
        self.actions.diary.random_delete()

    def search_diary(self) -> None:
        self.actions.diary.search_diary()

    def view_selected(self) -> None:
        self.actions.diary.view_selected()

    def edit_selected(self) -> None:
        self.actions.diary.edit_selected()

    def delete_selected(self) -> None:
        self.actions.diary.delete_selected()

    def batch_delete_selected(self) -> None:
        self.actions.diary.batch_delete_selected()

    def batch_tag_selected(self) -> None:
        self.actions.diary.batch_tag_selected()

    # ------------------------------------------------------------------
    # 委托给 UIActions
    # ------------------------------------------------------------------
    def toggle_theme(self) -> None:
        self.actions.ui.toggle_theme()

    def apply_theme(self) -> None:
        self.actions.ui.apply_theme()

    def on_language_changed(self, lang: str) -> None:
        self.actions.ui.on_language_changed(lang)

    def show_column_settings(self) -> None:
        self.actions.ui.show_column_settings()

    def show_statistics(self) -> None:
        self.actions.ui.show_statistics()

    def run_tests(self) -> None:
        self.actions.ui.run_tests()

    def export_data(self) -> None:
        self.actions.ui.export_data()

    def import_data(self) -> None:
        self.actions.ui.import_data()

    def show_about(self) -> None:
        self.actions.ui.show_about()

    def open_trash(self) -> None:
        self.actions.ui.open_trash()

    # ------------------------------------------------------------------
    # 内部：日历 / 热力图私有回调（供 actions 回调到 MainWindow）
    # ------------------------------------------------------------------
    def _on_date_selected(self, date_str: str) -> None:
        """日期选中入口（与组件回调签名保持兼容）"""
        self.actions.calendar.on_date_selected(date_str)

    def _show_all_diaries(self) -> None:
        """显示全部日记入口（与组件回调签名保持兼容）"""
        self.actions.calendar.show_all_diaries()

    def _on_heatmap_month_changed(self, year: int, month: int) -> None:
        """热力图月份切换入口（与组件回调签名保持兼容）"""
        self.actions.heatmap.on_month_changed(year, month)

    def _on_sidebar_tab_changed(self, index: int) -> None:
        """侧栏 tab 切换入口（与组件回调签名保持兼容）"""
        self.actions.calendar.on_sidebar_tab_changed(index)

    def _on_tests_finished(self, returncode: int, output: str) -> None:
        """测试完成回调（与组件信号签名保持兼容）"""
        self.actions.ui._on_tests_finished(returncode, output)
