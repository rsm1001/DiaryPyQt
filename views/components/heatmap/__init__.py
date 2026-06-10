"""
热力图子包（解耦后的模块化实现）

提供日记写作热力图的全部 UI 组件，按职责垂直切分为：
- constants    ：色阶、星期标签、尺寸常量
- date_utils   ：日期吸附、月份标签格式化、i18n 辅助
- calendar_widget：单月日历核心绘图组件
- panel        ：带月份导航按钮的完整面板
- factory      ：面板工厂（静态构造器）

外部通过 ``views.components.heatmap`` 包路径访问公共 API，
保持与原 ``views.components.heatmap_panel`` 模块同等的对外接口。
"""
from .constants import (
    LEVELS_LIGHT,
    LEVELS_DARK,
    BG_LIGHT,
    BG_DARK,
    TEXT_LIGHT,
    TEXT_DARK,
    DAY_LABELS_CN,
    DAY_LABELS_EN,
    level_for_count,
    HeatmapLayout,
)
from .date_utils import (
    snap_to_monday,
    snap_to_sunday,
    format_month_label,
    is_chinese_locale,
)
from .calendar_widget import HeatmapCalendarWidget
from .panel import HeatmapPanel
from .factory import HeatmapPanelFactory

__all__ = [
    # 常量与工具
    "LEVELS_LIGHT",
    "LEVELS_DARK",
    "BG_LIGHT",
    "BG_DARK",
    "TEXT_LIGHT",
    "TEXT_DARK",
    "DAY_LABELS_CN",
    "DAY_LABELS_EN",
    "HeatmapLayout",
    "level_for_count",
    "snap_to_monday",
    "snap_to_sunday",
    "format_month_label",
    "is_chinese_locale",
    # 组件
    "HeatmapCalendarWidget",
    "HeatmapPanel",
    "HeatmapPanelFactory",
]
