"""
UI杂项动作处理器：负责主题、语言、设置、统计、导入导出、测试与关于等。
"""
import logging
import sys

from i18n import _
from utils.theme_utils import ThemeManager
from views.dialogs.column_settings_dialog import ColumnSettingsDialog
from views.dialogs.diary_action_helper import AboutDialog
from views.dialogs.import_export_helper import ImportExportHelper
from views.dialogs.statistics_dialog import StatisticsDialog
from views.dialogs.test_dialog_helper import TestDialogHelper
from views.dialogs.trash_dialog import TrashDialog

logger = logging.getLogger(__name__)


class UIActions:
    """主题、语言、设置、统计、测试、导入导出、垃圾桶等杂项动作"""

    def __init__(self, window):
        self._window = window
        self._test_thread = None
        logger.debug("UIActions初始化完成")

    # ------------------------------------------------------------------
    # 主题
    # ------------------------------------------------------------------
    def toggle_theme(self):
        """切换主题"""
        window = self._window
        window.current_theme = "dark" if window.current_theme == "light" else "light"
        self.apply_theme()
        logger.info("切换主题: %s", window.current_theme)

    def apply_theme(self):
        """应用主题"""
        window = self._window
        theme_manager = ThemeManager()
        theme_manager.apply_theme(window, window.current_theme)
        if hasattr(window, "heatmap_panel") and window.heatmap_panel is not None:
            window.heatmap_panel._heatmap.set_theme(window.current_theme)

    # ------------------------------------------------------------------
    # 语言
    # ------------------------------------------------------------------
    def on_language_changed(self, lang):
        """语言切换后刷新 UI"""
        logger.info("语言切换为: %s", lang)
        window = self._window
        window.menu_manager.create()
        window.toolbar_manager.create()
        window.update_status_bar()
        window.model.refresh_headers()
        logger.info("语言切换完成，UI已刷新")

    # ------------------------------------------------------------------
    # 列设置
    # ------------------------------------------------------------------
    def show_column_settings(self):
        """显示列设置对话框"""
        dialog = ColumnSettingsDialog(self._window.column_config_manager, self._window)
        if dialog.exec():
            self._window.table_manager.apply_config()
        logger.info("列设置已更新")

    # ------------------------------------------------------------------
    # 统计
    # ------------------------------------------------------------------
    def show_statistics(self):
        """显示统计信息"""
        StatisticsDialog.show_statistics(self._window, self._window.controller)

    # ------------------------------------------------------------------
    # 测试
    # ------------------------------------------------------------------
    def run_tests(self):
        """运行单元测试"""
        if not TestDialogHelper.confirm_run_tests(self._window):
            return

        project_root = (
            self._window.controller.db_manager.db_path
            .replace("\\", "/")
            .rsplit("/data/", 1)[0]
        )
        tests_dir = f"{project_root}/tests"
        self._window.status_bar_manager.show_message(_("正在运行测试..."))

        from views.test_runner_thread import TestRunnerThread  # 延迟导入

        self._test_thread = TestRunnerThread(tests_dir, sys.executable)
        self._test_thread.test_finished.connect(self._on_tests_finished)
        self._test_thread.start()
        logger.info("启动测试线程")

    def _on_tests_finished(self, returncode, output):
        """测试完成回调"""
        self._window.status_bar_manager.clear_message()
        TestDialogHelper.show_test_result(self._window, returncode, output)

    # ------------------------------------------------------------------
    # 导入导出
    # ------------------------------------------------------------------
    def export_data(self):
        """导出数据"""
        ImportExportHelper.export_data(self._window, self._window.controller)

    def import_data(self):
        """导入数据"""
        ImportExportHelper.import_data(
            self._window, self._window.controller, self._window.load_data
        )

    # ------------------------------------------------------------------
    # 其它对话框
    # ------------------------------------------------------------------
    def show_about(self):
        """显示关于对话框"""
        AboutDialog.show(self._window)

    def open_trash(self):
        """打开垃圾桶"""
        dialog = TrashDialog(self._window.controller, self._window)
        dialog.exec()
        self._window.load_data()
        logger.debug("打开垃圾桶")
