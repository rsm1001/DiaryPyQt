"""
热力图面板工厂

采用静态工厂方法 ``HeatmapPanelFactory.create_heatmap_panel``，
把 ``HeatmapPanel`` 的构造与依赖（回调、主题、字体）解耦：

- 调用方无需了解面板内部子控件细节
- 后续如需新增面板变体（如暗色专用版、紧凑版），
  只需在本工厂新增一个静态方法，不影响其它模块
- 与 ``HeatmapPanel`` 本身解耦，单元测试可在无 GUI 下构造并验证

典型用法：

    panel = HeatmapPanelFactory.create_heatmap_panel(
        parent=main_window,
        on_date_clicked=lambda d: refresh_for(d),
        on_month_changed=lambda y, m: rebuild_heatmap(y, m),
    )
    main_window.heatmap_panel = panel
"""
import logging
from typing import Callable, Optional

from PyQt6.QtWidgets import QWidget

from .panel import HeatmapPanel

logger = logging.getLogger(__name__)


class HeatmapPanelFactory:
    """热力图面板静态工厂。"""

    @staticmethod
    def create_heatmap_panel(
        parent: Optional[QWidget] = None,
        on_date_clicked: Optional[Callable[[str], None]] = None,
        on_month_changed: Optional[Callable[[int, int], None]] = None,
    ) -> HeatmapPanel:
        """
        创建并配置一个完整热力图面板。

        Args:
            parent: 父窗口
            on_date_clicked: 格子点击回调，参数为 "yyyy-MM-dd" 字符串
            on_month_changed: 月份切换回调，参数为 (year, month)

        Returns:
            ``HeatmapPanel`` 实例。
        """
        logger.debug(
            "HeatmapPanelFactory.create_heatmap_panel 触发 "
            "(has_date_cb=%s, has_month_cb=%s)",
            on_date_clicked is not None,
            on_month_changed is not None,
        )
        return HeatmapPanel(
            parent=parent,
            on_date_clicked=on_date_clicked,
            on_month_changed=on_month_changed,
        )
