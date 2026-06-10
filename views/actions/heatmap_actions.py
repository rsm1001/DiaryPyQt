"""
热力图动作处理器：负责热力图数据加载、月份切换、汇总刷新与显隐切换。
"""
import logging
from datetime import datetime
from typing import Dict

from i18n import _

logger = logging.getLogger(__name__)


class HeatmapActions:
    """热力图相关动作"""

    def __init__(self, window):
        self._window = window
        logger.debug("HeatmapActions初始化完成")

    def refresh_heatmap(self):
        """刷新热力图：一次性拉全量历史，按月份导航展示当前月"""
        try:
            stats_svc = self._window.controller.db_manager.statistics_service
            date_range = stats_svc.get_diary_date_range()
            today = datetime.now().strftime("%Y-%m-%d")
            today_dt = datetime.strptime(today, "%Y-%m-%d")

            heatmap = self._window.heatmap_panel._heatmap
            summary_label = self._window.heatmap_panel._summary_label

            if not date_range or not date_range[0] or not date_range[1]:
                heatmap.set_data({})
                heatmap.set_today(today)
                heatmap.set_summary(0, 0)
                summary_label.setText("")
                return

            earliest, latest = date_range
            counts = stats_svc.get_diary_counts_by_date_range(earliest, latest)

            latest_dt = datetime.strptime(latest, "%Y-%m-%d")
            anchor = max(today_dt, latest_dt)
            init_year, init_month = anchor.year, anchor.month

            heatmap.set_data(counts)
            heatmap.set_today(today)
            self._window.heatmap_panel.set_month(init_year, init_month)
            self._window.heatmap_panel.set_today_enabled(
                not (init_year == today_dt.year and init_month == today_dt.month)
            )
            self._update_summary(init_year, init_month, counts)
        except Exception as exc:
            logger.warning("刷新热力图失败: %s", exc)
            self._window.heatmap_panel._heatmap.set_data({})
            self._window.heatmap_panel._heatmap.set_summary(0, 0)
            self._window.heatmap_panel._summary_label.setText("")

    def on_month_changed(self, year, month):
        """月份切换回调：仅刷新 summary"""
        counts = self._window.heatmap_panel._heatmap._counts
        self._update_summary(year, month, counts)
        today_dt = datetime.now()
        self._window.heatmap_panel.set_today_enabled(
            not (year == today_dt.year and month == today_dt.month)
        )

    def toggle_visibility(self, checked):
        """切换热力图 tab 的显隐"""
        self._window.show_heatmap = bool(checked)
        sidebar = getattr(self._window, "sidebar_tabs", None)
        if sidebar is not None:
            sidebar.setTabVisible(
                self._window.heatmap_tab_index, self._window.show_heatmap
            )
        logger.info("热力图显隐: %s", self._window.show_heatmap)

    def _update_summary(self, year, month, counts):
        """按月份过滤 counts，更新 summary 标签"""
        prefix = f"{year:04d}-{month:02d}-"
        month_counts = {d: n for d, n in counts.items() if d.startswith(prefix)}
        total = sum(month_counts.values())
        active = len(month_counts)
        self._window.heatmap_panel._heatmap.set_summary(
            total=total, active_days=active
        )
        if total == 0 and active == 0:
            self._window.heatmap_panel._summary_label.setText(_("当月暂无记录"))
        else:
            self._window.heatmap_panel._summary_label.setText(
                _("当月 {n} 篇 · {d} 天有记录").format(n=total, d=active)
            )
