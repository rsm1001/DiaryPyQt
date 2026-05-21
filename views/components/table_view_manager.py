"""
表格视图管理器组件
"""
import logging
from PyQt6.QtWidgets import QTableView, QHeaderView, QAbstractItemView
from PyQt6.QtCore import Qt
from models.table_models.diary_table_model import DiaryTableModel

logger = logging.getLogger(__name__)


class TableViewManager:
    """表格视图管理器"""

    def __init__(self, table_view: QTableView, model: DiaryTableModel):
        """初始化表格视图管理器"""
        self.table_view = table_view
        self.model = model
        self._setup_ui()
        logger.debug("TableViewManager 初始化完成")

    def _setup_ui(self):
        """设置表格视图UI"""
        self.table_view.setModel(self.model)

        # 设置表头
        header = self.table_view.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        self.table_view.setColumnWidth(3, 80)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)

        # 固定行高
        self.table_view.verticalHeader().setDefaultSectionSize(28)
        self.table_view.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)

        # 设置样式
        self.table_view.setStyleSheet("""
            QTableView {
                gridline-color: #d3d3d3;
                selection-background-color: #3ea6ff;
                selection-color: white;
            }
            QHeaderView::section {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #f2f2f2, stop:1 #e2e2e2);
                padding: 4px;
                border: 1px solid #d8d8d8;
                font-weight: bold;
                color: black;
            }
        """)

        # 启用鼠标悬停提示
        self.table_view.setMouseTracking(True)
        self.table_view.setToolTipDuration(999999)
        self.table_view.viewport().setStyleSheet("""
            QToolTip {
                background-color: #fffde7;
                color: #333333;
                border: 2px solid #ffc107;
                border-radius: 8px;
                padding: 12px 16px;
                font-size: 13px;
                font-family: 'Microsoft YaHei', sans-serif;
                max-width: 600px;
            }
        """)

        # 设置选择行为
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        logger.debug("表格视图 UI 设置完成")

    def get_selected_rows(self):
        """获取选中的行"""
        return self.table_view.selectionModel().selectedRows()

    def get_selected_count(self):
        """获取选中行数"""
        return len(self.table_view.selectionModel().selectedRows())

    def get_selected_diary(self, index):
        """获取选中行的日记数据"""
        if index.isValid():
            return self.model.data(index, Qt.ItemDataRole.UserRole)
        return None

    def set_item_delegate(self, column: int, delegate):
        """设置列的委托"""
        self.table_view.setItemDelegateForColumn(column, delegate)

    def set_vertical_header_mode(self, mode):
        """设置垂直表头模式"""
        self.table_view.verticalHeader().setSectionResizeMode(mode)

    def connect_clicked(self, handler):
        """连接点击信号"""
        self.table_view.clicked.connect(handler)

    def connect_context_menu(self, handler):
        """连接右键菜单信号"""
        self.table_view.customContextMenuRequested.connect(handler)

    def connect_selection_changed(self, handler):
        """连接选择变化信号"""
        self.table_view.selectionModel().selectionChanged.connect(handler)
