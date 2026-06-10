"""
动作处理器工厂：统一装配所有视图动作 handler。

通过工厂模式封装四个动作处理器的创建过程，对外只暴露
``ActionFactory`` 一个聚合入口，便于后续扩展与替换。
"""
import logging

from views.actions.calendar_actions import CalendarActions
from views.actions.diary_actions import DiaryActions
from views.actions.heatmap_actions import HeatmapActions
from views.actions.ui_actions import UIActions

logger = logging.getLogger(__name__)


class ActionFactory:
    """动作处理器聚合工厂"""

    def __init__(self, window):
        self._window = window
        self.diary = DiaryActions(window)
        self.calendar = CalendarActions(window)
        self.heatmap = HeatmapActions(window)
        self.ui = UIActions(window)
        logger.debug(
            "ActionFactory 初始化完成: diary=%s calendar=%s heatmap=%s ui=%s",
            self.diary.__class__.__name__,
            self.calendar.__class__.__name__,
            self.heatmap.__class__.__name__,
            self.ui.__class__.__name__,
        )

    @classmethod
    def create(cls, window):
        """工厂方法：创建并返回动作处理器聚合实例"""
        logger.info("创建 ActionFactory 实例")
        return cls(window)
