"""
状态栏管理器组件
"""
import logging
from PyQt6.QtWidgets import QStatusBar

from i18n import _

logger = logging.getLogger(__name__)


class StatusBarManager:
    """状态栏管理器"""

    def __init__(self, status_bar: QStatusBar):
        """初始化状态栏管理器"""
        self.status_bar = status_bar
        logger.debug("StatusBarManager 初始化完成")

    def update_statistics(self, stats: dict, daily_stats: dict, today_views: int,
                          date_filter: str = None):
        """更新状态栏统计信息"""
        filter_info = f" | {_('日期过滤')}: {date_filter}" if date_filter else ""
        message = (
            f"{_('总计')}: {stats['total']} {_('篇日记')} | "
            f"{_('总查看次数')}: {stats['total_views']} | "
            f"{_('平均查看次数')}: {stats['avg_views']} | "
            f"{_('今日查看')}: {today_views} | "
            f"{_('昨日查看')}: {daily_stats['yesterday_total_views']} | "
            f"{_('历史最佳')}: {daily_stats['all_time_max_single_views']}{filter_info}"
        )
        self.status_bar.showMessage(message)
        logger.debug(f"状态栏更新: total={stats['total']}, today_views={today_views}")

    def show_message(self, message: str):
        """显示临时消息"""
        self.status_bar.showMessage(message)
        logger.debug(f"状态栏消息: {message}")

    def clear_message(self):
        """清除状态栏消息"""
        self.status_bar.clearMessage()
        logger.debug("状态栏消息已清除")
