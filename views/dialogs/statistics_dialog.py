"""
统计信息对话框
"""
import logging
from PyQt6.QtWidgets import QMessageBox

logger = logging.getLogger(__name__)


class StatisticsDialog:
    """统计信息对话框助手"""

    @staticmethod
    def show_statistics(parent, controller):
        """显示统计信息对话框

        Args:
            parent: 父窗口
            controller: 日记控制器
        """
        logger.debug("显示统计信息对话框")
        stats = controller.get_statistics()
        daily_stats = controller.get_daily_stats()

        if stats['total'] == 0:
            QMessageBox.information(parent, "统计", "暂无日记")
            return

        most_viewed = stats['most_viewed']
        least_viewed = stats['least_viewed']

        stats_text = StatisticsDialog._build_stats_text(stats, daily_stats, most_viewed, least_viewed)

        QMessageBox.information(parent, "统计信息", stats_text)
        logger.debug("统计信息对话框已显示")

    @staticmethod
    def _build_stats_text(stats: dict, daily_stats: dict, most_viewed: dict, least_viewed: dict) -> str:
        """构建统计信息文本"""
        most_viewed_content = StatisticsDialog._format_content(most_viewed)
        least_viewed_content = StatisticsDialog._format_content(least_viewed)

        return f"""统计信息：
总计日记数：{stats['total']}
总查看次数：{stats['total_views']}
平均查看次数：{stats['avg_views']}
昨日查看总数：{daily_stats['yesterday_total_views']}
历史最佳单日：{daily_stats['all_time_max_single_views']} ({daily_stats['all_time_max_date'] or 'N/A'})

最多查看的日记：
ID: {most_viewed['id'] if most_viewed else 'N/A'}
查看次数: {most_viewed['view_count'] if most_viewed else 'N/A'}
内容: {most_viewed_content}

最少查看的日记：
ID: {least_viewed['id'] if least_viewed else 'N/A'}
查看次数: {least_viewed['view_count'] if least_viewed else 'N/A'}
内容: {least_viewed_content}"""

    @staticmethod
    def _format_content(diary_info: dict) -> str:
        """格式化日记内容摘要"""
        if not diary_info:
            return 'N/A'
        content = diary_info.get('content', '')
        if len(content) > 30:
            return content[:30] + '...'
        return content or 'N/A'


class StatisticsDialogFactory:
    """统计对话框工厂"""

    @staticmethod
    def create_and_show(parent, controller):
        """创建并显示统计对话框"""
        logger.info("创建统计对话框")
        StatisticsDialog.show_statistics(parent, controller)
