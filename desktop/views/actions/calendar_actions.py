"""
侧栏日历动作处理器：负责月历视图日期筛选与日历标记刷新。
"""
import logging

from i18n import _

logger = logging.getLogger(__name__)


class CalendarActions:
    """侧栏日历视图相关动作"""

    def __init__(self, window):
        self._window = window
        logger.debug("CalendarActions初始化完成")

    def on_date_selected(self, date_str):
        """日历日期选择事件"""
        self._window.current_date_filter = date_str
        diaries = self._window.controller.get_diaries_by_date(date_str)
        self._window.model.update_data(diaries)
        label = self._window.calendar_panel._date_filter_label
        label.setText(f"📆 {date_str}")
        label.setStyleSheet(
            "color: #228be6; font-size:12px; padding:6px; font-weight: bold;"
        )
        self._window.update_status_bar()
        logger.info("日期过滤: %s", date_str)

    def show_all_diaries(self):
        """显示全部日记"""
        self._window.current_date_filter = None
        self._window.load_data()
        label = self._window.calendar_panel._date_filter_label
        label.setText(_("全部日记"))
        label.setStyleSheet(
            "color: #868e96; font-size:12px; padding:6px;"
        )
        logger.debug("显示全部日记")

    def on_sidebar_tab_changed(self, index):
        """侧栏 tab切换：切到月历视图时清除日期筛选"""
        if index == getattr(self._window, "calendar_tab_index", -1):
            self.show_all_diaries()

    def refresh_calendar_marks(self):
        """刷新月历与热力图的日记标记"""
        all_diaries = self._window.controller.get_all_diaries(limit=10000)
        diary_dates = set()
        for diary in all_diaries:
            if diary.date:
                date_part = diary.date.split(" ")[0] if " " in diary.date else diary.date
                diary_dates.add(date_part)
        self._window.calendar_panel._calendar.set_diary_dates(diary_dates)
        self._window._refresh_heatmap()
        logger.debug("更新日历标记: %d 个日期", len(diary_dates))
