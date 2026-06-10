"""
热力图面板组件（带月份导航）

将 ``HeatmapCalendarWidget`` 与导航按钮、月份标签、summary 标签、
说明文字组装为完整面板，对外通过方法/属性通信，不直接耦合工厂。

外部访问约定（向后兼容旧 heatmap_panel.py 的 panel.* 访问形式）：
- panel._heatmap / panel._month_label / panel._summary_label / panel._description
- panel._btn_prev / panel._btn_next / panel._btn_today
- panel._title / panel._scroll
- panel.set_month(year, month)
- panel.set_today_enabled(bool)
- panel.refresh_month_label()
"""
import logging
import uuid
from typing import Callable, Optional

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from i18n import _
from .calendar_widget import HeatmapCalendarWidget
from .date_utils import format_month_label

logger = logging.getLogger(__name__)


class HeatmapPanel(QWidget):
    """热力图完整面板：单月视图 + 月份导航 + summary。"""

    PANEL_OBJECT_NAME = "HeatmapPanel"
    SCROLL_OBJECT_NAME = "HeatmapScroll"
    PANEL_STYLE = """
        QWidget#HeatmapPanel {
            background-color: #f8f9fa;
            border-right: 1px solid #dee2e6;
        }
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        on_date_clicked: Optional[Callable[[str], None]] = None,
        on_month_changed: Optional[Callable[[int, int], None]] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName(self.PANEL_OBJECT_NAME)
        self.setStyleSheet(self.PANEL_STYLE)

        self._on_date_clicked = on_date_clicked
        self._on_month_changed = on_month_changed

        # 控件引用（外部通过 panel._xxx 访问，保持向后兼容）
        self._title: QLabel = self._build_title()
        self._btn_prev: QPushButton
        self._btn_next: QPushButton
        self._btn_today: QPushButton
        self._month_label: QLabel
        (
            self._btn_prev,
            self._btn_next,
            self._btn_today,
            self._month_label,
        ) = self._build_nav_row()

        # 核心日历组件
        self._heatmap = HeatmapCalendarWidget(self)
        self._heatmap.set_adaptive_size(True)
        if on_date_clicked:
            self._heatmap.date_clicked.connect(on_date_clicked)

        # 滚动容器
        self._scroll = QScrollArea(self)
        self._scroll.setObjectName(self.SCROLL_OBJECT_NAME)
        self._scroll.setWidgetResizable(True)
        self._scroll.setWidget(self._heatmap)
        self._scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:horizontal { height: 8px; background: #f1f3f5; }
            QScrollBar::handle:horizontal { background: #ced4da; border-radius: 4px; }
        """)
        self._scroll.setMinimumHeight(
            self._heatmap.TOP_LABEL_HEIGHT
            + 2 * self._heatmap.OUTER_PADDING
            + 4 * self._heatmap.STRIDE
        )

        # summary / 描述
        self._summary_label = self._build_summary_label()
        self._description = self._build_description()

        # 主布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        layout.addWidget(self._title)

        nav_row = QHBoxLayout()
        nav_row.setContentsMargins(0, 0, 0, 0)
        nav_row.setSpacing(4)
        nav_row.addWidget(self._btn_prev)
        nav_row.addWidget(self._month_label, 1)
        nav_row.addWidget(self._btn_next)
        nav_row.addWidget(self._btn_today)
        layout.addLayout(nav_row)

        layout.addWidget(self._scroll, 1)
        layout.addWidget(self._summary_label)
        layout.addWidget(self._description)

        # 信号接线
        self._btn_prev.clicked.connect(self._on_prev_clicked)
        self._btn_next.clicked.connect(self._on_next_clicked)
        self._btn_today.clicked.connect(self._on_today_clicked)

        # 初始月份标签
        self.refresh_month_label()
        logger.info("热力图面板组件创建成功")

    # ------------------------------------------------------------------
    # 子控件构造（私有工厂方法）
    # ------------------------------------------------------------------
    def _build_title(self) -> QLabel:
        title = QLabel(_("🔥 写作热力图"))
        title.setStyleSheet("""
            font-weight: bold;
            font-size: 14px;
            color: #495057;
            padding: 8px;
            background-color: #e9ecef;
            border-radius: 6px;
        """)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return title

    def _build_nav_row(self):
        common_btn_style = """
            QPushButton#HeatmapNavBtn {
                font-size: 16px;
                font-weight: bold;
                color: #495057;
                background-color: #f1f3f5;
                border: 1px solid #ced4da;
                border-radius: 4px;
                padding: 0;
            }
            QPushButton#HeatmapNavBtn:hover { background-color: #dee2e6; }
            QPushButton#HeatmapNavBtn:pressed { background-color: #ced4da; }
        """

        btn_prev = QPushButton("‹")
        btn_prev.setObjectName("HeatmapNavBtn")
        btn_prev.setFixedWidth(28)
        btn_prev.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_prev.setToolTip(_("上一月"))
        btn_prev.setStyleSheet(common_btn_style)

        month_label = QLabel("")
        month_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        month_label.setStyleSheet("""
            color: #228be6;
            font-size: 12px;
            font-weight: bold;
            padding: 2px 4px;
        """)
        month_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        btn_next = QPushButton("›")
        btn_next.setObjectName("HeatmapNavBtn")
        btn_next.setFixedWidth(28)
        btn_next.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_next.setToolTip(_("下一月"))
        btn_next.setStyleSheet(common_btn_style)

        btn_today = QPushButton(_("今天"))
        btn_today.setObjectName("HeatmapTodayBtn")
        btn_today.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_today.setStyleSheet("""
            QPushButton#HeatmapTodayBtn {
                color: #495057;
                font-size: 10px;
                padding: 2px 8px;
                background-color: #e9ecef;
                border: 1px solid #ced4da;
                border-radius: 4px;
            }
            QPushButton#HeatmapTodayBtn:hover { background-color: #dee2e6; }
            QPushButton#HeatmapTodayBtn:disabled { color: #adb5bd; }
        """)
        return btn_prev, btn_next, btn_today, month_label

    def _build_summary_label(self) -> QLabel:
        label = QLabel("")
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("""
            color: #495057;
            font-size: 11px;
            padding: 2px 4px;
        """)
        return label

    def _build_description(self) -> QLabel:
        desc = QLabel(_("悬停查看 · 点击跳转 · 颜色越深当日篇数越多"))
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet("""
            color: #868e96;
            font-size: 10px;
            padding: 2px 4px;
        """)
        return desc

    # ------------------------------------------------------------------
    # 公开 API
    # ------------------------------------------------------------------
    def set_month(self, year: int, month: int) -> None:
        """切到指定月份并发出 on_month_changed 回调（如有）。"""
        self._heatmap.set_current_month(year, month)
        self.refresh_month_label()
        t = QDate.currentDate()
        self.set_today_enabled(not (year == t.year() and month == t.month()))
        if self._on_month_changed:
            try:
                self._on_month_changed(year, month)
            except Exception as exc:  # 回调异常不能拖死 UI
                logger.exception("on_month_changed 回调抛出异常: %s", exc)

    def set_today_enabled(self, enabled: bool) -> None:
        self._btn_today.setEnabled(bool(enabled))

    def refresh_month_label(self) -> None:
        m = self._heatmap.current_month()
        if m and m.isValid():
            self._month_label.setText(format_month_label(m))
        else:
            self._month_label.setText(_("暂无数据"))

    # ------------------------------------------------------------------
    # 按钮槽
    # ------------------------------------------------------------------
    def _on_prev_clicked(self) -> None:
        m = self._heatmap.current_month()
        if not m or not m.isValid():
            return
        prev = m.addMonths(-1)
        trace_id = uuid.uuid4().hex[:8]
        logger.info(
            "heatmap.nav.prev -> %04d-%02d trace_id=%s",
            prev.year(), prev.month(), trace_id,
        )
        self.set_month(prev.year(), prev.month())

    def _on_next_clicked(self) -> None:
        m = self._heatmap.current_month()
        if not m or not m.isValid():
            return
        nxt = m.addMonths(1)
        trace_id = uuid.uuid4().hex[:8]
        logger.info(
            "heatmap.nav.next -> %04d-%02d trace_id=%s",
            nxt.year(), nxt.month(), trace_id,
        )
        self.set_month(nxt.year(), nxt.month())

    def _on_today_clicked(self) -> None:
        t = QDate.currentDate()
        trace_id = uuid.uuid4().hex[:8]
        logger.info(
            "heatmap.nav.today -> %04d-%02d trace_id=%s",
            t.year(), t.month(), trace_id,
        )
        self.set_month(t.year(), t.month())
