"""
主窗口 - PyQt6版本
"""
import sys
import logging
from datetime import datetime
from typing import Dict
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                            QSplitter, QMessageBox, QDialog, QTableView, QStatusBar,
                            QTabWidget)
from PyQt6.QtCore import Qt
from i18n import _
from views.dialogs.diary_action_helper import DiaryActionHelper, AboutDialog
from views.dialogs.test_dialog_helper import TestDialogHelper
from views.dialogs.statistics_dialog import StatisticsDialog
from views.dialogs.import_export_helper import ImportExportHelper
from views.dialogs.column_settings_dialog import ColumnSettingsDialog
from views.test_runner_thread import TestRunnerThread

from models.table_models.diary_table_model import DiaryTableModel
from controllers.enhanced_diary_controller import EnhancedDiaryController
from utils.theme_utils import ThemeManager
from utils.formatters import format_tags_html
from views.components.toolbar import MainToolBar
from views.components.menu_bar import MainMenuBar
from views.components.calendar_panel import CalendarPanelFactory
from views.components.heatmap import HeatmapPanelFactory
from views.components.detail_panel import DetailPanel
from views.components.status_bar_manager import StatusBarManager
from views.components.table_view_manager import TableViewManager
from views.components.context_menu_builder import ContextMenuBuilder, ContextMenuFactory
from views.components.column_config_manager import ColumnConfigManager
from views.search_dialog import SearchDialog
from views.dialogs.diary_dialogs import DiaryEditDialog, DiaryViewDialog
from views.dialogs.trash_dialog import TrashDialog
from views.dialogs.batch_tag_dialog import BatchTagDialog
from views.delegates.tag_delegate import TagDelegate

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self, db_path: str = None):
        super().__init__()
        logger.info(f"主窗口初始化开始, db_path={db_path}")
        self.controller = EnhancedDiaryController(db_path)
        self.db_path = db_path
        self.current_theme = 'light'
        self.current_date_filter = None
        self.show_heatmap = True

        # 启动时清理旧查看日志
        self.controller.cleanup_old_view_logs()

        # 初始化列配置管理器
        self.column_config_manager = ColumnConfigManager()

        # 初始化组件管理器
        self.toolbar_manager = MainToolBar(self)
        self.menu_manager = MainMenuBar(self)
        self.context_menu_builder = ContextMenuBuilder(self)

        self.init_ui()
        self.setup_connections()
        self.load_data()
        self.apply_theme()
        logger.info("主窗口初始化完成")

    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle(_("日记管理系统 - PyQt版"))
        screen_geometry = QApplication.primaryScreen().geometry()
        x = (screen_geometry.width() - 1000) // 2
        y = (screen_geometry.height() - 700) // 2
        self.setGeometry(x, y, 1000, 700)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        central_layout = QVBoxLayout(central_widget)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)

        # 创建工具栏
        self.toolbar_manager.create()

        # 上部分割器
        top_splitter = QSplitter(Qt.Orientation.Horizontal)

        # 创建侧边栏（QTabWidget 容纳月历视图与热力图）
        sidebar_tabs = QTabWidget()
        sidebar_tabs.setObjectName("SidebarTabs")
        sidebar_tabs.setFixedWidth(280)

        # 月历视图 tab
        calendar_panel = CalendarPanelFactory.create_calendar_panel(
            self,
            on_date_selected=self._on_date_selected,
            on_show_all=self._show_all_diaries
        )
        self.calendar_panel = calendar_panel
        self.calendar_tab_index = sidebar_tabs.addTab(
            calendar_panel, _("月历视图")
        )

        # 热力图 tab
        heatmap_panel = HeatmapPanelFactory.create_heatmap_panel(
            self,
            on_date_clicked=self._on_date_selected,
            on_month_changed=self._on_heatmap_month_changed,
        )
        self.heatmap_panel = heatmap_panel
        self.heatmap_tab_index = sidebar_tabs.addTab(
            heatmap_panel, _("热力图")
        )

        self.sidebar_tabs = sidebar_tabs
        self.sidebar_tabs.currentChanged.connect(self._on_sidebar_tab_changed)
        top_splitter.addWidget(sidebar_tabs)

        # 创建表格视图
        self.model = DiaryTableModel(self.column_config_manager)
        self.table_view = QTableView()
        self.table_manager = TableViewManager(self.table_view, self.model, self.column_config_manager)
        self.table_manager.set_tag_delegate_by_id(TagDelegate(self.table_view))

        top_splitter.addWidget(self.table_view)
        central_layout.addWidget(top_splitter, 3)

        # 创建详情面板
        self.detail_panel = DetailPanel()
        self.detail_panel.set_max_height(180, 80)
        central_layout.addWidget(self.detail_panel)

        # 创建状态栏
        self.status_bar_manager = StatusBarManager(QStatusBar())
        self.setStatusBar(self.status_bar_manager.status_bar)

        # 创建菜单
        self.menu_manager.create()
        logger.debug("UI 组件初始化完成")

    def setup_connections(self):
        """设置信号连接"""
        self.table_manager.connect_clicked(self.on_table_clicked)
        self.table_manager.connect_context_menu(self.show_context_menu)
        self.table_manager.connect_selection_changed(self.on_selection_changed)

    def _on_date_selected(self, date_str: str):
        """日历日期选择事件"""
        self.current_date_filter = date_str
        diaries = self.controller.get_diaries_by_date(date_str)
        self.model.update_data(diaries)
        date_filter_label = self.calendar_panel._date_filter_label
        date_filter_label.setText(f"📆 {date_str}")
        date_filter_label.setStyleSheet("color: #228be6; font-size: 12px; padding: 6px; font-weight: bold;")
        self.update_status_bar()
        logger.info(f"日期过滤: {date_str}")

    def _show_all_diaries(self):
        """显示全部日记"""
        self.current_date_filter = None
        self.load_data()
        date_filter_label = self.calendar_panel._date_filter_label
        date_filter_label.setText(_("全部日记"))
        date_filter_label.setStyleSheet("color: #868e96; font-size: 12px; padding: 6px;")
        logger.debug("显示全部日记")

    def _on_sidebar_tab_changed(self, index: int):
        """侧栏 tab 切换：切到月历视图时清除日期筛选"""
        if index == self.calendar_tab_index:
            self._show_all_diaries()

    def center_on_screen(self):
        """使窗口居中于屏幕"""
        screen_geometry = QApplication.primaryScreen().geometry()
        x = (screen_geometry.width() - self.width()) // 2
        y = (screen_geometry.height() - self.height()) // 2
        self.move(screen_geometry.x() + x, screen_geometry.y() + y)

    def on_selection_changed(self):
        """选择行变化时更新批量按钮状态"""
        count = self.table_manager.get_selected_count()
        self.toolbar_manager.set_batch_actions_enabled(count > 0)
        logger.debug(f"选中行数变化: {count}")

    def load_data(self):
        """加载日记数据"""
        diaries = self.controller.get_all_diaries(limit=25)
        self.model.update_data(diaries)
        self._update_calendar_diary_marks()
        self.update_status_bar()
        logger.info(f"加载日记数据: {len(diaries)} 篇")

    def _update_calendar_diary_marks(self):
        """更新日历标记（含月历视图与热力图）"""
        all_diaries = self.controller.get_all_diaries(limit=10000)
        diary_dates = set()
        for diary in all_diaries:
            if diary.date:
                date_part = diary.date.split(' ')[0] if ' ' in diary.date else diary.date
                diary_dates.add(date_part)
        self.calendar_panel._calendar.set_diary_dates(diary_dates)
        self._refresh_heatmap()
        logger.debug(f"更新日历标记: {len(diary_dates)} 个日期")

    def _refresh_heatmap(self):
        """刷新热力图：一次性拉全量历史，按月份导航展示当前月"""
        try:
            stats_svc = self.controller.db_manager.statistics_service
            date_range = stats_svc.get_diary_date_range()
            today = datetime.now().strftime('%Y-%m-%d')
            today_dt = datetime.strptime(today, '%Y-%m-%d')

            if not date_range or not date_range[0] or not date_range[1]:
                self.heatmap_panel._heatmap.set_data({})
                self.heatmap_panel._heatmap.set_today(today)
                self.heatmap_panel._heatmap.set_summary(0, 0)
                self.heatmap_panel._summary_label.setText("")
                return

            earliest, latest = date_range
            # 全量历史一次性拉取
            counts = stats_svc.get_diary_counts_by_date_range(earliest, latest)

            # 初始月 = max(今天, 最新日记) 所在月
            latest_dt = datetime.strptime(latest, '%Y-%m-%d')
            anchor = max(today_dt, latest_dt)
            init_year, init_month = anchor.year, anchor.month

            self.heatmap_panel._heatmap.set_data(counts)
            self.heatmap_panel._heatmap.set_today(today)
            self.heatmap_panel.set_month(init_year, init_month)
            self.heatmap_panel.set_today_enabled(
                not (init_year == today_dt.year and init_month == today_dt.month)
            )
            self._update_heatmap_summary(init_year, init_month, counts)
        except Exception as exc:
            logger.warning(f"刷新热力图失败: {exc}")
            self.heatmap_panel._heatmap.set_data({})
            self.heatmap_panel._heatmap.set_summary(0, 0)
            self.heatmap_panel._summary_label.setText("")

    def _on_heatmap_month_changed(self, year: int, month: int):
        """月份切换回调：仅刷新 summary（不重查 DB）"""
        counts = self.heatmap_panel._heatmap._counts
        self._update_heatmap_summary(year, month, counts)
        today_dt = datetime.now()
        self.heatmap_panel.set_today_enabled(
            not (year == today_dt.year and month == today_dt.month)
        )

    def _update_heatmap_summary(self, year: int, month: int,
                               counts: Dict[str, int]) -> None:
        """按月份过滤 counts，更新 summary 标签"""
        prefix = f"{year:04d}-{month:02d}-"
        month_counts = {d: n for d, n in counts.items() if d.startswith(prefix)}
        total = sum(month_counts.values())
        active = len(month_counts)
        self.heatmap_panel._heatmap.set_summary(total=total, active_days=active)
        if total == 0 and active == 0:
            self.heatmap_panel._summary_label.setText(
                _("当月暂无记录")
            )
        else:
            self.heatmap_panel._summary_label.setText(
                _("当月 {n} 篇 · {d} 天有记录").format(n=total, d=active)
            )

    def toggle_heatmap_visibility(self, checked: bool):
        """切换热力图 tab 的显隐（供菜单调用）"""
        self.show_heatmap = bool(checked)
        if hasattr(self, 'sidebar_tabs'):
            self.sidebar_tabs.setTabVisible(self.heatmap_tab_index, self.show_heatmap)
        logger.info(f"热力图显隐: {self.show_heatmap}")

    def update_status_bar(self):
        """更新状态栏"""
        stats = self.controller.get_statistics()
        daily_stats = self.controller.get_daily_stats()
        today_views = self.controller.get_today_total_views()
        self.status_bar_manager.update_statistics(
            stats, daily_stats, today_views, self.current_date_filter
        )

    def on_table_clicked(self, index):
        """表格点击事件"""
        diary = self.table_manager.get_selected_diary(index)
        if diary:
            tags_html = format_tags_html(diary.tags if hasattr(diary, 'tags') else [])
            self.detail_panel.update_content(diary, tags_html)
            self.controller.increment_view_count(diary.id)
            self.load_data()
            logger.info(f"查看日记: id={diary.id}")

    def show_context_menu(self, position):
        """显示右键菜单"""
        count = self.table_manager.get_selected_count()
        if count == 0:
            return

        handlers = {
            'view': self.view_selected,
            'edit': self.edit_selected,
            'delete': self.delete_selected,
            'batch_delete': self.batch_delete_selected,
            'batch_tag': self.batch_tag_selected,
        }

        menu = ContextMenuFactory.create_context_menu(self, count, handlers)
        if menu:
            menu.exec(self.table_view.viewport().mapToGlobal(position))
        logger.debug(f"显示右键菜单, 选中: {count} 篇")

    def new_diary(self):
        """新建日记"""
        dialog = DiaryEditDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            content = dialog.get_content()
            selected_tag_ids = dialog.get_selected_tag_ids()
            if content.strip():
                diary = self.controller.add_diary(content)
                if diary and selected_tag_ids:
                    self.controller.assign_tags_to_diary(diary.id, selected_tag_ids)
                self.load_data()
                logger.info("新建日记完成")

    def random_view(self):
        """随机查看日记"""
        diary_dict = self.controller.random_view_diary()
        if diary_dict:
            dialog = DiaryViewDialog(diary_dict, self, readonly=True)
            dialog.exec()
            self.controller.increment_view_count(diary_dict.id)
            self.load_data()
            logger.info(f"随机查看日记: id={diary_dict.id}")
        else:
            DiaryActionHelper.show_no_diary(self)

    def random_delete(self):
        """随机删除日记"""
        diary_dict = self.controller.get_diary_for_deletion()
        if not diary_dict:
            DiaryActionHelper.show_no_diary(self, "没有可删除的日记")
            return

        if DiaryActionHelper.confirm_random_delete(self, diary_dict):
            self.controller.delete_diary_by_id(diary_dict.id)
            self.load_data()
            DiaryActionHelper.show_delete_success(self, diary_dict.id)
            logger.info(f"删除日记: id={diary_dict.id}")

    def search_diary(self):
        """搜索日记"""
        dialog = SearchDialog(self.controller, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_data()

    def view_selected(self):
        """查看选中日记"""
        selected = self.table_manager.get_selected_rows()
        if not selected:
            DiaryActionHelper.show_no_selection(self)
            return

        index = selected[0]
        diary = self.table_manager.get_selected_diary(index)
        if diary:
            dialog = DiaryViewDialog(diary, self, readonly=True)
            dialog.exec()
            self.controller.increment_view_count(diary.id)
            self.load_data()

    def edit_selected(self):
        """编辑选中日记"""
        selected = self.table_manager.get_selected_rows()
        if not selected:
            DiaryActionHelper.show_no_selection(self)
            return

        index = selected[0]
        diary = self.table_manager.get_selected_diary(index)
        if diary:
            dialog = DiaryEditDialog(self, diary)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                content = dialog.get_content()
                selected_tag_ids = dialog.get_selected_tag_ids()
                if content.strip():
                    self.controller.update_diary(diary.id, content)
                    self.controller.assign_tags_to_diary(diary.id, selected_tag_ids)
                    self.load_data()

    def delete_selected(self):
        """删除选中日记"""
        selected = self.table_manager.get_selected_rows()
        if not selected:
            DiaryActionHelper.show_no_selection(self)
            return

        index = selected[0]
        diary = self.table_manager.get_selected_diary(index)
        if diary and DiaryActionHelper.confirm_delete(self, diary):
            self.controller.delete_diary_by_id(diary.id)
            self.load_data()
            DiaryActionHelper.show_delete_success(self, diary.id)

    def batch_delete_selected(self):
        """批量删除"""
        selected = self.table_manager.get_selected_rows()
        if not selected:
            return

        diaries = self.model.get_selected_diaries(selected)
        if not diaries:
            return

        count = len(diaries)
        if DiaryActionHelper.confirm_batch_delete(self, count):
            result = self.controller.batch_delete_diaries([d.id for d in diaries])
            self.load_data()
            DiaryActionHelper.show_batch_result(self, result['succeeded'], result['failed'], "删除")

    def batch_tag_selected(self):
        """批量打标签"""
        selected = self.table_manager.get_selected_rows()
        if not selected:
            return

        diaries = self.model.get_selected_diaries(selected)
        if not diaries:
            return

        dialog = BatchTagDialog(self.controller, diaries, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_tag_ids = dialog.get_selected_tag_ids()
            if selected_tag_ids is not None:
                result = self.controller.batch_assign_tags(
                    [d.id for d in diaries], list(selected_tag_ids)
                )
                self.load_data()
                DiaryActionHelper.show_batch_result(self, result['succeeded'], result['failed'], "更新")

    def toggle_theme(self):
        """切换主题"""
        self.current_theme = 'dark' if self.current_theme == 'light' else 'light'
        self.apply_theme()
        logger.info(f"切换主题: {self.current_theme}")

    def apply_theme(self):
        """应用主题"""
        theme_manager = ThemeManager()
        theme_manager.apply_theme(self, self.current_theme)
        if hasattr(self, 'heatmap_panel') and self.heatmap_panel is not None:
            self.heatmap_panel._heatmap.set_theme(self.current_theme)

    def on_language_changed(self, lang):
        """语言切换后刷新UI"""
        logger.info(f"语言切换为: {lang}")
        # 重新创建菜单和工具栏以应用新语言
        self.menu_manager.create()
        self.toolbar_manager.create()
        # 更新状态栏
        self.update_status_bar()
        # 刷新表格表头
        self.model.refresh_headers()
        logger.info("语言切换完成，UI已刷新")

    def show_column_settings(self):
        """显示列设置对话框"""
        dialog = ColumnSettingsDialog(self.column_config_manager, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # 重新应用配置到表格
            self.table_manager.apply_config()
            logger.info("列设置已更新")

    def show_statistics(self):
        """显示统计信息"""
        StatisticsDialog.show_statistics(self, self.controller)

    def run_tests(self):
        """运行单元测试"""
        if not TestDialogHelper.confirm_run_tests(self):
            return

        project_root = self.controller.db_manager.db_path.replace("\\", "/").rsplit("/data/", 1)[0]
        tests_dir = f"{project_root}/tests"

        self.status_bar_manager.show_message(_("正在运行测试..."))

        self._test_thread = TestRunnerThread(tests_dir, sys.executable)
        self._test_thread.test_finished.connect(self._on_tests_finished)
        self._test_thread.start()
        logger.info("启动测试线程")

    def _on_tests_finished(self, returncode: int, output: str):
        """测试完成回调"""
        self.status_bar_manager.clear_message()
        TestDialogHelper.show_test_result(self, returncode, output)

    def export_data(self):
        """导出数据"""
        ImportExportHelper.export_data(self, self.controller)

    def import_data(self):
        """导入数据"""
        ImportExportHelper.import_data(self, self.controller, self.load_data)

    def show_about(self):
        """显示关于对话框"""
        AboutDialog.show(self)

    def open_trash(self):
        """打开垃圾桶"""
        dialog = TrashDialog(self.controller, self)
        dialog.exec()
        self.load_data()
        logger.debug("打开垃圾桶")
