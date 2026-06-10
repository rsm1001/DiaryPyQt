"""
视图动作子包：按职责拆分主窗口中的事件处理逻辑。

将原 MainWindow 中的方法按业务域（日记、侧栏日历、热力图、UI/杂项）
拆分为独立的 handler 类，通过 ActionFactory 统一装配，从而降低
MainWindow 的耦合度与体积。
"""

from views.actions.calendar_actions import CalendarActions
from views.actions.diary_actions import DiaryActions
from views.actions.factory import ActionFactory
from views.actions.heatmap_actions import HeatmapActions
from views.actions.ui_actions import UIActions

__all__ = [
    "ActionFactory",
    "CalendarActions",
    "DiaryActions",
    "HeatmapActions",
    "UIActions",
]