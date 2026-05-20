"""
日历面板组件模块

提供日历侧边栏组件，包含隐藏非当月日期的日历控件
"""
import logging
from typing import Optional, Callable

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QPushButton,
                             QFrame, QCalendarWidget)
from PyQt6.QtCore import Qt, QDate, pyqtSignal, QRect
from PyQt6.QtGui import QPainter, QFont, QBrush, QPen, QColor

logger = logging.getLogger(__name__)


class HiddenMonthCalendar(QCalendarWidget):
    """隐藏非当月日期的日历控件，支持标记有日记的日期"""

    # 日期选择信号，传递日期字符串 "yyyy-MM-dd"
    date_selected = pyqtSignal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._diary_dates: set = set()
        self._on_date_select_callback: Optional[Callable[[str], None]] = None
        self.clicked.connect(self._handle_date_click)

    def set_diary_dates(self, dates: set) -> None:
        """设置有日记的日期集合

        Args:
            dates: 日期字符串集合，格式 "yyyy-MM-dd"
        """
        self._diary_dates = dates
        self.update()
        logger.debug(f"日历标记更新，共 {len(dates)} 个有日记的日期")

    def set_date_select_callback(self, callback: Callable[[str], None]) -> None:
        """设置日期选择回调函数

        Args:
            callback: 日期选择时调用的回调函数，参数为日期字符串
        """
        self._on_date_select_callback = callback

    def _handle_date_click(self, date: QDate) -> None:
        """处理日期点击事件"""
        date_str = date.toString("yyyy-MM-dd")
        self.date_selected.emit(date_str)
        if self._on_date_select_callback:
            self._on_date_select_callback(date_str)
        logger.info(f"日期选中: {date_str}")

    def paintCell(self, painter: QPainter, rect: QRect, date: QDate) -> None:
        """重写绘制单元格，只显示当月日期，有日记的日期高亮"""
        current_year = self.yearShown()
        current_month = self.monthShown()
        if date.year() != current_year or date.month() != current_month:
            painter.fillRect(rect, self.palette().base())
            return

        date_str = date.toString("yyyy-MM-dd")
        has_diary = date_str in self._diary_dates

        if has_diary:
            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            # 绘制背景圆
            circle_rect = rect.adjusted(4, 4, -4, -4)
            painter.setBrush(QBrush(QColor(77, 171, 247, 40)))
            painter.setPen(QPen(QColor(77, 171, 247), 1.5))
            painter.drawEllipse(circle_rect)

            # 绘制数字
            painter.setPen(QColor(33, 110, 232))
            painter.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(date.day()))
            painter.restore()
        else:
            super().paintCell(painter, rect, date)


class CalendarPanelFactory:
    """日历面板工厂类，用于创建日历面板组件"""

    @staticmethod
    def create_calendar_panel(
            parent: QWidget,
            on_date_selected: Optional[Callable[[str], None]] = None,
            on_show_all: Optional[Callable[[], None]] = None
    ) -> QWidget:
        """创建日历面板

        Args:
            parent: 父窗口
            on_date_selected: 日期选择回调函数
            on_show_all: 显示全部日记回调函数

        Returns:
            日历面板组件
        """
        panel = QWidget()
        panel.setMaximumWidth(280)
        panel.setMinimumWidth(220)
        panel.setObjectName("CalendarPanel")
        panel.setStyleSheet("""
            QWidget#CalendarPanel {
                background-color: #f8f9fa;
                border-right: 1px solid #dee2e6;
            }
        """)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # 标题
        title = QLabel("📅 日历查询")
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

        # 日历组件
        calendar = HiddenMonthCalendar()
        calendar.setGridVisible(False)
        calendar.setStyleSheet("""
            QCalendarWidget {
                background-color: white;
                border: 1px solid #dee2e6;
                border-radius: 8px;
            }
            QCalendarWidget QToolButton {
                background-color: transparent;
                color: #495057;
                font-weight: bold;
                padding: 5px;
                border-radius: 4px;
            }
            QCalendarWidget QToolButton:hover {
                background-color: #e9ecef;
            }
            QCalendarWidget QMenu {
                background-color: white;
                border: 1px solid #dee2e6;
            }
            QCalendarWidget QSpinBox {
                background-color: white;
            }
            QCalendarWidget QAbstractItemView {
                background-color: white;
                selection-background-color: #4dabf7;
                selection-color: white;
                border: none;
            }
            QCalendarWidget QAbstractItemView::item {
                padding: 4px;
                border-radius: 4px;
            }
            QCalendarWidget QAbstractItemView::item:hover {
                background-color: #e7f5ff;
            }
            QCalendarWidget QTableView {
                border: none;
            }
            QCalendarWidget QTableView::section {
                background-color: #f1f3f5;
                font-weight: bold;
                color: #495057;
            }
        """)

        if on_date_selected:
            calendar.set_date_select_callback(on_date_selected)

        layout.addWidget(calendar)

        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("background-color: #dee2e6;")
        layout.addWidget(line)

        # 当前选中日期标签
        date_filter_label = QLabel("全部日记")
        date_filter_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        date_filter_label.setObjectName("dateFilterLabel")
        date_filter_label.setStyleSheet("""
            color: #868e96;
            font-size: 12px;
            padding: 6px;
        """)
        layout.addWidget(date_filter_label)

        # 显示全部按钮
        show_all_btn = QPushButton("显示全部日记")
        show_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #4dabf7;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 16px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #339af0;
            }
            QPushButton:pressed {
                background-color: #228be6;
            }
        """)
        if on_show_all:
            show_all_btn.clicked.connect(on_show_all)
        layout.addWidget(show_all_btn)

        layout.addStretch()

        # 存储日历组件引用用于外部访问
        panel._calendar = calendar
        panel._date_filter_label = date_filter_label

        logger.info("日历面板组件创建成功")
        return panel
