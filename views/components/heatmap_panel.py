"""
热力图日历面板组件

按日聚合日记数量，使用 QPainter 绘制日历式热力图：
- 行 = 周，列 = 星期（Mon..Sun，顶部有星期表头）
- 一次只显示 1 个月（4-6 行 × 7 列）
- 非当月格子留空不画（与真实日历一致）
- 鼠标悬停查看日期统计，点击日期跳转到当日列表
"""
import logging
from typing import Optional, Callable, Dict, Tuple

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSizePolicy,
                             QScrollArea, QPushButton)
from PyQt6.QtCore import Qt, QDate, QRect, pyqtSignal, QSize
from PyQt6.QtGui import QPainter, QFont, QBrush, QColor, QPen

from i18n import _

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 色阶定义（与项目强调色 #4dabf7 / #339af0 保持一致）
# ---------------------------------------------------------------------------
LEVELS_LIGHT = {
    0: '#ebedf0',
    1: '#d0ebff',
    2: '#74c0fc',
    3: '#339af0',
    4: '#1971c2',
}

LEVELS_DARK = {
    0: '#2b2b2b',
    1: '#1c3a5e',
    2: '#2a5a8a',
    3: '#3a8edb',
    4: '#74c0fc',
}

BG_LIGHT = '#f8f9fa'
BG_DARK = '#1e1e1e'
TEXT_LIGHT = '#495057'
TEXT_DARK = '#dcdcdc'

DAY_LABELS_CN = ['一', '二', '三', '四', '五', '六', '日']
DAY_LABELS_EN = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']


def _level_for_count(count: int) -> int:
    """根据日记数量返回色阶等级（0-4）"""
    if count <= 0:
        return 0
    if count == 1:
        return 1
    if count <= 3:
        return 2
    if count <= 6:
        return 3
    return 4


def _snap_to_monday(date: QDate) -> QDate:
    """向前回退到所在周的周一（PyQt dayOfWeek: 1=Mon..7=Sun）"""
    return date.addDays(-(date.dayOfWeek() - 1))


def _snap_to_sunday(date: QDate) -> QDate:
    """向后推进到所在周的周日"""
    delta = (7 - date.dayOfWeek()) % 7
    return date.addDays(delta)


def _current_locale_is_chinese() -> bool:
    """通过 i18n 状态判断当前语言是否中文，用于月/日标签"""
    try:
        from i18n import get_current_language
        return get_current_language() == 'zh_CN'
    except Exception:
        return True


def _format_month_label(qdate: QDate) -> str:
    """格式化月份标题：中文 "2026 年 6 月"，英文 "Jun 2026" """
    is_zh = _current_locale_is_chinese()
    if is_zh:
        return f"{qdate.year()} 年 {qdate.month()} 月"
    en = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
          'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    return f"{en[qdate.month() - 1]} {qdate.year()}"


class HeatmapCalendarWidget(QWidget):
    """
    热力图日历核心组件：单月日历式视图（行=周，列=星期）。

    渲染规则：
    - 顶部 7 列分别为周一到周日（按中文/英文显示）
    - _grid_start = 当月 1 日所在周的周一
    - _grid_end   = 当月最后一日所在周的周日
    - _weeks      = 4-6（当月占据的行数）
    - 当月格子：色阶（按日记数）+ 角标日期数字 + 今天描边
    - 非当月格子：留空不画（与真实月历一致）
    - 点击任意一格发射 date_clicked(date_str) 信号
    """

    date_clicked = pyqtSignal(str)

    CELL_SIZE = 12
    CELL_PADDING = 2
    STRIDE = 14
    TOP_LABEL_HEIGHT = 20
    OUTER_PADDING = 6

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._counts: Dict[str, int] = {}
        self._current_month: Optional[QDate] = None
        self._grid_start: Optional[QDate] = None
        self._grid_end: Optional[QDate] = None
        self._weeks = 0
        self._theme = 'light'
        self._today: Optional[QDate] = None
        self._adaptive_size = False
        self._cell_size = self.CELL_SIZE
        self._stride = self.STRIDE
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(self.TOP_LABEL_HEIGHT + 2 * self.OUTER_PADDING
                              + 4 * self.STRIDE)

    def set_adaptive_size(self, enabled: bool) -> None:
        """启用后，cell 尺寸随可用宽度自动缩放（单月视图推荐启用）。"""
        self._adaptive_size = bool(enabled)
        self._recompute_stride()
        self.updateGeometry()
        self.update()

    def _recompute_stride(self) -> None:
        """根据当前宽度重算 cell 尺寸（按 7 列等分可用宽度）。"""
        if not self._adaptive_size:
            self._cell_size = self.CELL_SIZE
            self._stride = self.STRIDE
            return
        if self._weeks <= 0:
            self._cell_size = self.CELL_SIZE
            self._stride = self.STRIDE
            return
        avail = max(0, self.width() - 2 * self.OUTER_PADDING)
        if avail <= 0:
            return
        # 7 列等分；上限 35（实测 QCalendarWidget 在 280px 侧栏下的列宽就是 35px）
        target_stride = max(12, min(35, avail // 7))
        self._stride = int(target_stride)
        self._cell_size = max(8, self._stride - 2)

    # ----- 公开 API -----

    def set_theme(self, theme_name: str) -> None:
        if theme_name not in ('light', 'dark'):
            theme_name = 'light'
        if theme_name != self._theme:
            self._theme = theme_name
            self.update()

    def set_today(self, today_str: Optional[str]) -> None:
        if not today_str:
            self._today = None
        else:
            self._today = QDate.fromString(today_str, "yyyy-MM-dd")
        self.update()

    def set_summary(self, total: int, active_days: int) -> None:
        self._summary_total = max(0, int(total))
        self._summary_active = max(0, int(active_days))
        self.update()

    def set_data(self, counts: Dict[str, int]) -> None:
        """装载按日聚合的全部历史 counts。key 为 "yyyy-MM-dd" 字符串。"""
        self._counts = dict(counts or {})
        self.update()

    def set_current_month(self, year: int, month: int) -> None:
        """切换到指定月份，按 Mon-first 重新计算 4-6 行 × 7 列网格。"""
        m = QDate(year, month, 1)
        if not m.isValid():
            self._current_month = None
            self._grid_start = None
            self._grid_end = None
            self._weeks = 0
            self._recompute_stride()
            self.updateGeometry()
            self.update()
            return
        self._current_month = m
        month_last = m.addMonths(1).addDays(-1)
        # 开头空几格：1 号是星期几，就空 (dayOfWeek - 1) 格
        self._grid_start = _snap_to_monday(m)
        # 结尾空几格：末日到周日差几天
        self._grid_end = _snap_to_sunday(month_last)
        self._weeks = max(1, (self._grid_start.daysTo(self._grid_end) // 7) + 1)
        self._recompute_stride()
        self.updateGeometry()
        self.update()
        logger.debug(
            f"热力图切月: {year}-{month:02d}, weeks={self._weeks}, "
            f"grid={self._grid_start.toString('yyyy-MM-dd')}"
            f"..{self._grid_end.toString('yyyy-MM-dd')}"
        )

    def current_month(self) -> Optional[QDate]:
        return self._current_month

    def sizeHint(self) -> QSize:
        width = 2 * self.OUTER_PADDING + 7 * self._stride
        height = (self.TOP_LABEL_HEIGHT + 2 * self.OUTER_PADDING
                  + self._weeks * self._stride)
        return QSize(width, height)

    def minimumSizeHint(self) -> QSize:
        width = 2 * self.OUTER_PADDING + 7 * self._stride
        height = (self.TOP_LABEL_HEIGHT + 2 * self.OUTER_PADDING
                  + self._weeks * self._stride)
        return QSize(width, height)

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        if self._adaptive_size:
            self._recompute_stride()
        super().resizeEvent(event)

    def showEvent(self, event) -> None:  # noqa: N802 - Qt API
        if self._adaptive_size:
            self._recompute_stride()
            self.updateGeometry()
            self.update()
        super().showEvent(event)

    # ----- 绘制 -----

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        bg = BG_DARK if self._theme == 'dark' else BG_LIGHT
        text_color = TEXT_DARK if self._theme == 'dark' else TEXT_LIGHT
        levels = LEVELS_DARK if self._theme == 'dark' else LEVELS_LIGHT

        painter.fillRect(self.rect(), QColor(bg))
        painter.setPen(QColor(text_color))

        if self._grid_start is None or self._weeks <= 0:
            painter.setFont(QFont("Microsoft YaHei", 9))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                             _("暂无数据"))
            return

        weekday_labels = (DAY_LABELS_CN if _current_locale_is_chinese()
                          else DAY_LABELS_EN)

        # 顶部星期表头（一 二 三 四 五 六 日）
        header_font = QFont("Microsoft YaHei", 8)
        painter.setFont(header_font)
        for col_idx, label in enumerate(weekday_labels):
            text_rect = QRect(
                self.OUTER_PADDING + col_idx * self._stride,
                2,
                self._stride,
                self.TOP_LABEL_HEIGHT - 2,
            )
            painter.drawText(text_rect,
                             Qt.AlignmentFlag.AlignCenter, label)

        # 主体：行 = 周，列 = 星期
        month_first = self._current_month
        month_last = self._current_month.addMonths(1).addDays(-1)
        today_border_color = QColor(text_color)
        show_day_number = self._cell_size >= 24
        day_num_font = QFont("Microsoft YaHei", 9)
        day_num_font.setPointSize(9)

        cell_font = QFont("Microsoft YaHei", 7)
        painter.setFont(cell_font)

        for week_idx in range(self._weeks):
            for day_idx in range(7):
                current_date = self._grid_start.addDays(week_idx * 7 + day_idx)
                in_month = (current_date >= month_first
                            and current_date <= month_last)
                if not in_month:
                    # 非当月：留空不画（真实日历风格）
                    continue

                date_str = current_date.toString("yyyy-MM-dd")
                count = self._counts.get(date_str, 0)
                level = _level_for_count(count)

                x = self.OUTER_PADDING + day_idx * self._stride
                y = (self.TOP_LABEL_HEIGHT + self.OUTER_PADDING
                     + week_idx * self._stride)

                color = QColor(levels[level])
                painter.setBrush(QBrush(color))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(
                    QRect(x, y, self._cell_size, self._cell_size), 2, 2
                )

                # 日期角标（居中绘制，避免 baseline 定位时被顶出格子）
                if show_day_number:
                    text_rect = QRect(
                        x + 1, y + 1,
                        self._cell_size - 2, self._cell_size - 2,
                    )
                    painter.setPen(QColor(text_color))
                    painter.setFont(day_num_font)
                    painter.drawText(
                        text_rect,
                        Qt.AlignmentFlag.AlignCenter,
                        str(current_date.day()),
                    )
                    painter.setFont(cell_font)

                # 今天描边
                if (self._today is not None
                        and current_date == self._today):
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.setPen(QPen(today_border_color, 1.5))
                    painter.drawRoundedRect(
                        QRect(x - 1, y - 1,
                              self._cell_size + 2, self._cell_size + 2),
                        3, 3
                    )

        painter.end()

    # ----- 鼠标交互 -----

    def _cell_from_pos(self, x: int, y: int) -> Optional[QDate]:
        if self._grid_start is None or self._weeks <= 0:
            return None
        rel_x = x - self.OUTER_PADDING
        rel_y = y - self.TOP_LABEL_HEIGHT - self.OUTER_PADDING
        if rel_x < 0 or rel_y < 0:
            return None
        col = rel_x // self._stride  # 0..6 = Mon..Sun
        row = rel_y // self._stride  # 0.._weeks-1
        if col < 0 or col >= 7 or row < 0 or row >= self._weeks:
            return None
        return self._grid_start.addDays(row * 7 + col)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 - Qt API
        pos = event.position()
        target = self._cell_from_pos(int(pos.x()), int(pos.y()))
        if target is None:
            self.setToolTip("")
            return
        date_str = target.toString("yyyy-MM-dd")
        count = self._counts.get(date_str, 0)
        if count <= 0:
            self.setToolTip(f"{date_str}\n{_('无日记')}")
        else:
            self.setToolTip(f"{date_str}\n{count} {_('篇')}")

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt API
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position()
        target = self._cell_from_pos(int(pos.x()), int(pos.y()))
        if target is None:
            return
        self.date_clicked.emit(target.toString("yyyy-MM-dd"))
        logger.info(f"热力图日期选中: {target.toString('yyyy-MM-dd')}")

    def leaveEvent(self, event) -> None:  # noqa: N802 - Qt API
        self.setToolTip("")
        super().leaveEvent(event)


class HeatmapPanelFactory:
    """热力图面板工厂类：单月视图 + 月份导航"""

    @staticmethod
    def create_heatmap_panel(
            parent: QWidget,
            on_date_clicked: Optional[Callable[[str], None]] = None,
            on_month_changed: Optional[Callable[[int, int], None]] = None,
    ) -> QWidget:
        """
        创建热力图面板（单月日历式视图 + 月份导航）。

        Args:
            parent: 父窗口
            on_date_clicked: 格子点击回调，参数为 "yyyy-MM-dd" 字符串
            on_month_changed: 月份切换回调，参数为 (year, month)

        Returns:
            面板组件，外部可通过 panel._heatmap 访问核心控件。
        """
        panel = QWidget()
        panel.setObjectName("HeatmapPanel")
        panel.setStyleSheet("""
            QWidget#HeatmapPanel {
                background-color: #f8f9fa;
                border-right: 1px solid #dee2e6;
            }
        """)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # 标题
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
        layout.addWidget(title)

        # 月份导航行：[‹]  [YYYY 年 M 月]  [›]  [今天]
        nav_row = QHBoxLayout()
        nav_row.setContentsMargins(0, 0, 0, 0)
        nav_row.setSpacing(4)

        btn_prev = QPushButton("‹")
        btn_prev.setObjectName("HeatmapNavBtn")
        btn_prev.setFixedWidth(28)
        btn_prev.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_prev.setToolTip(_("上一月"))

        month_label = QLabel("")
        month_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        month_label.setStyleSheet("""
            color: #228be6;
            font-size: 12px;
            font-weight: bold;
            padding: 2px 4px;
        """)
        month_label.setSizePolicy(QSizePolicy.Policy.Expanding,
                                  QSizePolicy.Policy.Preferred)

        btn_next = QPushButton("›")
        btn_next.setObjectName("HeatmapNavBtn")
        btn_next.setFixedWidth(28)
        btn_next.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_next.setToolTip(_("下一月"))

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
        btn_prev.setStyleSheet(common_btn_style)
        btn_next.setStyleSheet(common_btn_style)

        nav_row.addWidget(btn_prev)
        nav_row.addWidget(month_label, 1)
        nav_row.addWidget(btn_next)
        nav_row.addWidget(btn_today)
        layout.addLayout(nav_row)

        # 热力图主体：日历式单月（行=周，列=星期）
        heatmap = HeatmapCalendarWidget()
        if on_date_clicked:
            heatmap.date_clicked.connect(on_date_clicked)
        # 默认开自适应：cell 按 7 列等分侧栏可用宽度
        heatmap.set_adaptive_size(True)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(heatmap)
        scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:horizontal { height: 8px; background: #f1f3f5; }
            QScrollBar::handle:horizontal { background: #ced4da; border-radius: 4px; }
        """)
        scroll.setMinimumHeight(heatmap.TOP_LABEL_HEIGHT
                                + 2 * heatmap.OUTER_PADDING
                                + 4 * heatmap.STRIDE)
        layout.addWidget(scroll, 1)

        # 汇总
        summary_label = QLabel("")
        summary_label.setWordWrap(True)
        summary_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        summary_label.setStyleSheet("""
            color: #495057;
            font-size: 11px;
            padding: 2px 4px;
        """)
        layout.addWidget(summary_label)

        # 说明
        desc = QLabel(_("悬停查看 · 点击跳转 · 颜色越深当日篇数越多"))
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet("""
            color: #868e96;
            font-size: 10px;
            padding: 2px 4px;
        """)
        layout.addWidget(desc)

        panel._heatmap = heatmap
        panel._scroll = scroll
        panel._title = title
        panel._month_label = month_label
        panel._summary_label = summary_label
        panel._description = desc
        panel._btn_prev = btn_prev
        panel._btn_next = btn_next
        panel._btn_today = btn_today

        def refresh_month_label():
            m = heatmap.current_month()
            if m and m.isValid():
                month_label.setText(_format_month_label(m))
            else:
                month_label.setText(_("暂无数据"))

        def navigate_to(year: int, month: int):
            heatmap.set_current_month(year, month)
            refresh_month_label()
            t = QDate.currentDate()
            btn_today.setEnabled(not (year == t.year() and month == t.month()))
            if on_month_changed:
                on_month_changed(year, month)

        def go_prev():
            m = heatmap.current_month()
            if not m or not m.isValid():
                return
            prev = m.addMonths(-1)
            navigate_to(prev.year(), prev.month())

        def go_next():
            m = heatmap.current_month()
            if not m or not m.isValid():
                return
            nxt = m.addMonths(1)
            navigate_to(nxt.year(), nxt.month())

        def go_today():
            t = QDate.currentDate()
            navigate_to(t.year(), t.month())

        btn_prev.clicked.connect(go_prev)
        btn_next.clicked.connect(go_next)
        btn_today.clicked.connect(go_today)

        def set_month(year: int, month: int):
            navigate_to(year, month)

        def set_today_enabled(enabled: bool):
            btn_today.setEnabled(bool(enabled))

        panel.set_month = set_month
        panel.set_today_enabled = set_today_enabled
        panel.refresh_month_label = refresh_month_label

        refresh_month_label()
        logger.info("热力图面板组件创建成功")
        return panel
