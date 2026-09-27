"""
热力图日历核心组件（单月视图）

行为约定（与项目历史版本保持一致）：
- 顶部 7 列分别为周一到周日（按中文 / 英文显示）
- _grid_start = 当月 1 日所在周的周一
- _grid_end   = 当月最后一日所在周的周日
- _weeks      = 4-6（当月占据的行数）
- 当月格子：色阶（按日记数）+ 角标日期数字 + 今天描边
- 非当月格子：留空不画（与真实月历一致）
- 点击任意一格发射 date_clicked(date_str) 信号

外部仅通过本类暴露的 ``set_*`` / ``current_month`` / ``sizeHint`` 等方法通信，
不与上层 ``HeatmapPanel`` 直接耦合。
"""
import logging
import uuid
from typing import Dict, Optional

from PyQt6.QtCore import Qt, QDate, QRect, QSize, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QSizePolicy, QWidget

from i18n import _
from .constants import (
    BG_DARK,
    BG_LIGHT,
    DAY_LABELS_CN,
    DAY_LABELS_EN,
    DEFAULT_LAYOUT,
    HeatmapLayout,
    LEVELS_DARK,
    LEVELS_LIGHT,
    TEXT_DARK,
    TEXT_LIGHT,
    level_for_count,
)
from .date_utils import is_chinese_locale, snap_to_monday, snap_to_sunday

logger = logging.getLogger(__name__)


class HeatmapCalendarWidget(QWidget):
    """单月日历式热力图组件。"""

    # 日期点击信号：参数为 "yyyy-MM-dd" 字符串
    date_clicked = pyqtSignal(str)

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        layout: Optional[HeatmapLayout] = None,
    ) -> None:
        super().__init__(parent)
        # 暴露类级常量（保持向后兼容：原代码使用 HeatmapCalendarWidget.CELL_SIZE 等）
        layout = layout or DEFAULT_LAYOUT
        self.CELL_SIZE: int = layout.cell_size
        self.CELL_PADDING: int = layout.cell_padding
        self.STRIDE: int = layout.stride
        self.TOP_LABEL_HEIGHT: int = layout.top_label_height
        self.OUTER_PADDING: int = layout.outer_padding
        self._layout = layout

        # 渲染数据
        self._counts: Dict[str, int] = {}
        self._current_month: Optional[QDate] = None
        self._grid_start: Optional[QDate] = None
        self._grid_end: Optional[QDate] = None
        self._weeks: int = 0
        self._theme: str = 'light'
        self._today: Optional[QDate] = None
        self._adaptive_size: bool = False
        self._cell_size: int = self.CELL_SIZE
        self._stride: int = self.STRIDE

        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(
            self.TOP_LABEL_HEIGHT + 2 * self.OUTER_PADDING + 4 * self._stride
        )
        logger.debug("HeatmapCalendarWidget 初始化完成 [layout=%s]", layout)

    # ------------------------------------------------------------------
    # 自适应尺寸
    # ------------------------------------------------------------------
    def set_adaptive_size(self, enabled: bool) -> None:
        """启用后，cell 尺寸随可用宽度自动缩放（单月视图推荐启用）。"""
        self._adaptive_size = bool(enabled)
        self._recompute_stride()
        self.updateGeometry()
        self.update()

    def _recompute_stride(self) -> None:
        """根据当前宽度重算 cell 尺寸（按 7 列等分可用宽度）。"""
        if not self._adaptive_size or self._weeks <= 0:
            self._cell_size = self.CELL_SIZE
            self._stride = self.STRIDE
            return
        avail = max(0, self.width() - 2 * self.OUTER_PADDING)
        if avail <= 0:
            return
        # 7 列等分；clamp 到 [min_stride, max_stride]
        target_stride = max(
            self._layout.min_stride,
            min(self._layout.max_stride, avail // 7),
        )
        self._stride = int(target_stride)
        self._cell_size = max(self._layout.min_cell_size, self._stride - 2)

    # ------------------------------------------------------------------
    # 公开 API
    # ------------------------------------------------------------------
    def set_theme(self, theme_name: str) -> None:
        """切换主题（'light' / 'dark'），未知值回退为 'light'。"""
        normalized = theme_name if theme_name in ('light', 'dark') else 'light'
        if normalized != self._theme:
            self._theme = normalized
            self.update()
            logger.debug("热力图主题切换: %s", self._theme)

    def set_today(self, today_str: Optional[str]) -> None:
        """设置今日高亮；传 None 清除。"""
        if not today_str:
            self._today = None
        else:
            self._today = QDate.fromString(today_str, "yyyy-MM-dd")
        self.update()

    def set_summary(self, total: int, active_days: int) -> None:
        """更新底部 summary 用的数据（仅在主控件内缓存）。"""
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
        self._grid_start = snap_to_monday(m)
        # 结尾空几格：末日到周日差几天
        self._grid_end = snap_to_sunday(month_last)
        self._weeks = max(1, (self._grid_start.daysTo(self._grid_end) // 7) + 1)
        self._recompute_stride()
        self.updateGeometry()
        self.update()
        logger.debug(
            "热力图切月: %04d-%02d, weeks=%d, grid=%s..%s",
            year, month, self._weeks,
            self._grid_start.toString('yyyy-MM-dd'),
            self._grid_end.toString('yyyy-MM-dd'),
        )

    def current_month(self) -> Optional[QDate]:
        return self._current_month

    # ------------------------------------------------------------------
    # 尺寸与事件
    # ------------------------------------------------------------------
    def sizeHint(self) -> QSize:  # noqa: N802 - Qt API
        width = 2 * self.OUTER_PADDING + 7 * self._stride
        height = (
            self.TOP_LABEL_HEIGHT
            + 2 * self.OUTER_PADDING
            + self._weeks * self._stride
        )
        return QSize(width, height)

    def minimumSizeHint(self) -> QSize:  # noqa: N802 - Qt API
        width = 2 * self.OUTER_PADDING + 7 * self._stride
        height = (
            self.TOP_LABEL_HEIGHT
            + 2 * self.OUTER_PADDING
            + self._weeks * self._stride
        )
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

    # ------------------------------------------------------------------
    # 绘制
    # ------------------------------------------------------------------
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
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                _("暂无数据"),
            )
            return

        weekday_labels = (
            DAY_LABELS_CN if is_chinese_locale() else DAY_LABELS_EN
        )

        # 顶部星期表头
        header_font = QFont("Microsoft YaHei", 8)
        painter.setFont(header_font)
        for col_idx, label in enumerate(weekday_labels):
            text_rect = QRect(
                self.OUTER_PADDING + col_idx * self._stride,
                2,
                self._stride,
                self.TOP_LABEL_HEIGHT - 2,
            )
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, label)

        # 主体：行=周，列=星期
        month_first = self._current_month
        month_last = self._current_month.addMonths(1).addDays(-1)
        today_border_color = QColor(text_color)
        show_day_number = (
            self._cell_size >= self._layout.day_number_cell_threshold
        )
        day_num_font = QFont("Microsoft YaHei", 9)

        cell_font = QFont("Microsoft YaHei", 7)
        painter.setFont(cell_font)

        for week_idx in range(self._weeks):
            for day_idx in range(7):
                current_date = self._grid_start.addDays(week_idx * 7 + day_idx)
                in_month = (
                    current_date >= month_first
                    and current_date <= month_last
                )
                if not in_month:
                    # 非当月：留空不画
                    continue

                date_str = current_date.toString("yyyy-MM-dd")
                count = self._counts.get(date_str, 0)
                level = level_for_count(count)

                x = self.OUTER_PADDING + day_idx * self._stride
                y = (
                    self.TOP_LABEL_HEIGHT
                    + self.OUTER_PADDING
                    + week_idx * self._stride
                )

                color = QColor(levels[level])
                painter.setBrush(QBrush(color))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(
                    QRect(x, y, self._cell_size, self._cell_size), 2, 2
                )

                # 日期角标
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
                if (
                    self._today is not None
                    and current_date == self._today
                ):
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.setPen(QPen(today_border_color, 1.5))
                    painter.drawRoundedRect(
                        QRect(
                            x - 1, y - 1,
                            self._cell_size + 2, self._cell_size + 2,
                        ),
                        3, 3,
                    )

        painter.end()

    # ------------------------------------------------------------------
    # 鼠标交互
    # ------------------------------------------------------------------
    def _cell_from_pos(self, x: int, y: int) -> Optional[QDate]:
        """将屏幕坐标映射为对应 QDate（用于点击与 hover）。"""
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
        date_str = target.toString("yyyy-MM-dd")
        # 关键交互位置记录结构化日志 + 短 trace id 方便排查
        trace_id = uuid.uuid4().hex[:8]
        logger.info(
            "heatmap.click date=%s count=%s trace_id=%s",
            date_str, self._counts.get(date_str, 0), trace_id,
        )
        self.date_clicked.emit(date_str)

    def leaveEvent(self, event) -> None:  # noqa: N802 - Qt API
        self.setToolTip("")
        super().leaveEvent(event)
