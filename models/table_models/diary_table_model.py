"""
日记表格模型 - PyQt6版本
从 main_window.py 解耦出来的独立模型
"""
from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PyQt6.QtGui import QFont
from models.entities.diary import Diary


class DiaryTableModel(QAbstractTableModel):
    """日记表格模型 - 从MainWindow解耦出来的独立模型"""

    def __init__(self, diaries=None, parent=None):
        super().__init__(parent)
        self.diaries = diaries or []
        self.headers = ['ID', '日期', '查看次数', '标签', '内容预览']

    def rowCount(self, parent=QModelIndex()):
        return len(self.diaries)

    def columnCount(self, parent=QModelIndex()):
        return len(self.headers)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self.diaries):
            return None

        diary = self.diaries[index.row()]

        if role == Qt.ItemDataRole.DisplayRole:
            col = index.column()
            if col == 0:  # ID
                return str(diary.id)
            elif col == 1:  # 日期
                return diary.date
            elif col == 2:  # 查看次数
                return str(diary.view_count)
            elif col == 3:  # 标签
                if hasattr(diary, 'tags') and diary.tags:
                    # 只显示标签名称，用逗号分隔
                    return ", ".join([tag['name'] for tag in diary.tags])
                return "无标签"  # 委托会将其渲染为短横线
            elif col == 4:  # 内容预览
                content = diary.content
                return content[:50] + "..." if len(content) > 50 else content
        elif role == Qt.ItemDataRole.UserRole:
            return diary
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            # 设置对齐方式：ID、查看次数居中，日期居中，内容左对齐
            col = index.column()
            if col in [0, 2]:  # ID 和 查看次数 居中
                return Qt.AlignmentFlag.AlignCenter
            elif col in [1, 3]:  # 日期和标签 居中
                return Qt.AlignmentFlag.AlignCenter
            elif col in [4]:  # 内容预览 左对齐
                return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        elif role == Qt.ItemDataRole.FontRole:
            # 设置字体，使表格更美观
            font = QFont()
            if index.column() in [3, 4]:  # 标签和内容预览列使用较小字体
                font.setPointSize(9)
            else:
                font.setPointSize(10)
            return font

        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.headers[section]
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