"""
日记表格模型 - PyQt6版本
从 main_window.py 解耦出来的独立模型
支持动态列配置
"""
from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PyQt6.QtGui import QFont
from models.entities.diary import Diary


class DiaryTableModel(QAbstractTableModel):
    """日记表格模型 - 支持动态列配置"""

    # 列 ID 到 data() 中数据获取逻辑的映射
    COLUMN_DATA_MAP = {
        'id': lambda diary: str(diary.id),
        'date': lambda diary: diary.date,
        'views': lambda diary: str(diary.view_count),
        'tags': lambda diary: ", ".join([tag['name'] for tag in diary.tags]) if (hasattr(diary, 'tags') and diary.tags) else "无标签",
        'preview': lambda diary: diary.content[:50] + "..." if len(diary.content) > 50 else diary.content,
    }

    def __init__(self, config_manager=None, diaries=None, parent=None):
        """
        初始化日记表格模型

        Args:
            config_manager: 列配置管理器，用于动态获取列配置
            diaries: 初始日记列表
            parent: 父对象
        """
        super().__init__(parent)
        self.config_manager = config_manager
        self.diaries = diaries or []

    @property
    def headers(self):
        """获取当前可见列的表头列表"""
        if self.config_manager:
            return self.config_manager.get_headers()
        return ['ID', '日期', '查看次数', '标签', '内容预览']

    def rowCount(self, parent=QModelIndex()):
        return len(self.diaries)

    def columnCount(self, parent=QModelIndex()):
        if self.config_manager:
            return self.config_manager.get_column_count()
        return 5

    def _get_col_id_by_visual_index(self, visual_index):
        """根据视觉索引获取列 ID"""
        if self.config_manager:
            return self.config_manager.get_col_id_by_visual_index(visual_index)
        # 默认列 ID 列表
        default_ids = ['id', 'date', 'views', 'tags', 'preview']
        if 0 <= visual_index < len(default_ids):
            return default_ids[visual_index]
        return None

    def _get_alignment(self, col_id):
        """获取列对齐方式"""
        # ID、查看次数居中，日期居中，标签居中，内容左对齐
        center_cols = {'id', 'views', 'date', 'tags'}
        if col_id in center_cols:
            return Qt.AlignmentFlag.AlignCenter
        return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self.diaries):
            return None

        diary = self.diaries[index.row()]
        col_id = self._get_col_id_by_visual_index(index.column())

        if role == Qt.ItemDataRole.DisplayRole:
            if col_id and col_id in self.COLUMN_DATA_MAP:
                return self.COLUMN_DATA_MAP[col_id](diary)
        elif role == Qt.ItemDataRole.UserRole:
            return diary
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if col_id:
                return self._get_alignment(col_id)
        elif role == Qt.ItemDataRole.ToolTipRole:
            # 鼠标悬停时显示日记完整内容（不计入查看次数）
            return diary.content
        elif role == Qt.ItemDataRole.FontRole:
            font = QFont()
            if col_id in {'tags', 'preview'}:
                font.setPointSize(9)
            else:
                font.setPointSize(10)
            return font

        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            headers = self.headers
            if 0 <= section < len(headers):
                return headers[section]
        elif role == Qt.ItemDataRole.TextAlignmentRole and orientation == Qt.Orientation.Horizontal:
            return Qt.AlignmentFlag.AlignCenter
        return None

    def update_data(self, diaries):
        """更新数据"""
        self.beginResetModel()
        self.diaries = diaries
        self.endResetModel()

    def get_diary_at_row(self, row):
        """获取指定行的日记对象"""
        if 0 <= row < len(self.diaries):
            return self.diaries[row]
        return None

    def get_selected_diaries(self, selected_rows):
        """获取选中行的日记对象列表"""
        selected_diaries = []
        for index in selected_rows:
            if index.isValid():
                diary = self.get_diary_at_row(index.row())
                if diary:
                    selected_diaries.append(diary)
        return selected_diaries

    def refresh_headers(self):
        """刷新表头（当配置改变时调用）"""
        self.headerDataChanged.emit(Qt.Orientation.Horizontal, 0, self.columnCount() - 1)