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

    def __init__(self, table_view: QTableView, model: DiaryTableModel, config_manager=None):
        """初始化表格视图管理器"""
        self.table_view = table_view
        self.model = model
        self.config_manager = config_manager
        self._setup_ui()
        logger.debug("TableViewManager 初始化完成")

    def _setup_ui(self):
        """设置表格视图UI"""
        self.table_view.setModel(self.model)

        # 应用列配置
        if self.config_manager:
            self._apply_column_settings()

        # 设置默认样式（备用）
        self._set_default_styles()

        # 设置选择行为
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        logger.debug("表格视图 UI 设置完成")

    def _set_default_styles(self):
        """设置默认样式"""
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

        self.table_view.verticalHeader().setDefaultSectionSize(28)
        self.table_view.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)

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

    def _apply_column_settings(self):
        """根据配置应用列设置：隐藏/显示、宽度"""
        if not self.config_manager:
            return

        config = self.config_manager.get_config()

        for col_config in config:
            col_id = col_config['id']
            visible = col_config['visible']
            width = col_config['width']

            # 获取该列在模型中的视觉索引
            visible_columns = self.config_manager.get_visible_columns()
            visual_index = -1
            for i, vc in enumerate(visible_columns):
                if vc['id'] == col_id:
                    visual_index = i
                    break

            if visual_index >= 0:
                self.table_view.setColumnHidden(visual_index, not visible)
                self.table_view.setColumnWidth(visual_index, width)

        # 设置最后一列为 stretch
        header = self.table_view.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)

        # ID 和日期列 resizeToContents，标签列固定宽度，内容预览列 stretch
        for i, vc in enumerate(visible_columns):
            if vc['id'] in ('id', 'date', 'views', 'tags'):
                # 已经被 setColumnWidth 设置了，这里保持 Interactive
                pass
            elif vc['id'] == 'preview':
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)

        header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)

    def apply_config(self):
        """应用配置到表格视图（外部调用）"""
        if not self.config_manager:
            return

        # 刷新模型表头
        self.model.refresh_headers()

        # 重新应用列设置
        self._apply_column_settings()

        logger.debug("列配置已应用到表格视图")

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

    def set_tag_delegate_by_id(self, delegate):
        """根据列 ID 设置标签委托（自动查找当前视觉索引）"""
        if not self.config_manager:
            return
        visible = self.config_manager.get_visible_columns()
        for i, vc in enumerate(visible):
            if vc['id'] == 'tags':
                self.table_view.setItemDelegateForColumn(i, delegate)
                logger.debug(f"标签委托已设置到视觉索引 {i}")
                return

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
