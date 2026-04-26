"""
流式布局 - 类似CSS flex-wrap的Qt布局
标签自动从左到右排列，宽度不足时自动换行
"""
from PyQt6.QtWidgets import QLayout, QLayoutItem
from PyQt6.QtCore import Qt, QPoint, QRect, QSize


class FlowLayout(QLayout):
    """流式布局 - 子控件从左到右流动，自动换行"""
    
    def __init__(self, parent=None, margin=0, spacing=-1):
        super().__init__(parent)
        
        if parent is not None:
            self.setContentsMargins(margin, margin, margin, margin)
        
        self.setSpacing(spacing)
        self.item_list = []
    
    def __del__(self):
        """析构时清理"""
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)
    
    def addItem(self, item):
        """添加布局项"""
        self.item_list.append(item)
    
    def count(self):
        """返回子项数量"""
        return len(self.item_list)
    
    def itemAt(self, index):
        """获取指定索引的项"""
        if 0 <= index < len(self.item_list):
            return self.item_list[index]
        return None
    
    def takeAt(self, index):
        """移除并返回指定索引的项"""
        if 0 <= index < len(self.item_list):
            return self.item_list.pop(index)
        return None
    
    def expandingDirections(self):
        """返回扩展方向"""
        return Qt.Orientation(0)
    
    def hasHeightForWidth(self):
        """是否根据宽度计算高度"""
        return True
    
    def heightForWidth(self, width):
        """根据给定宽度计算所需高度"""
        height = self._do_layout(QRect(0, 0, width, 0), True)
        return height
    
    def setGeometry(self, rect):
        """设置布局几何"""
        super().setGeometry(rect)
        self._do_layout(rect, False)
    
    def sizeHint(self):
        """返回建议大小"""
        return self.minimumSize()
    
    def minimumSize(self):
        """返回最小大小"""
        size = QSize()
        
        for item in self.item_list:
            size = size.expandedTo(item.minimumSize())
        
        margin = self.contentsMargins()
        size += QSize(margin.left() + margin.right(), margin.top() + margin.bottom())
        return size
    
    def _do_layout(self, rect, test_only=False):
        """执行布局计算"""
        x = rect.x()
        y = rect.y()
        line_height = 0
        
        # 获取边距
        margins = self.contentsMargins()
        x += margins.left()
        y += margins.top()
        
        available_width = rect.width() - margins.left() - margins.right()
        
        for item in self.item_list:
            widget = item.widget()
            space_x = self.spacing() + widget.style().layoutSpacing(
                widget.sizePolicy().controlType(),
                widget.sizePolicy().controlType(),
                Qt.Orientation.Horizontal
            )
            space_y = self.spacing() + widget.style().layoutSpacing(
                widget.sizePolicy().controlType(),
                widget.sizePolicy().controlType(),
                Qt.Orientation.Vertical
            )
            
            item_size = item.sizeHint()
            
            # 检查是否需要换行
            if x + item_size.width() > rect.x() + rect.width() - margins.right() and line_height > 0:
                x = rect.x() + margins.left()
                y += line_height + space_y
                line_height = 0
            
            # 设置控件位置
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item_size))
            
            x += item_size.width() + space_x
            line_height = max(line_height, item_size.height())
        
        # 返回总高度
        return y + line_height + margins.bottom() - rect.y()
