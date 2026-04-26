"""
标签委托 - 在表格中绘制彩色标签胶囊（紧凑单行版）
"""
from PyQt6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem, QStyle
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter


class TagDelegate(QStyledItemDelegate):
    """标签列自定义委托 - 绘制彩色胶囊标签（紧凑单行排列）"""
    
    # 预设配色方案（柔和色调）
    COLORS = [
        ('#e3f2fd', '#1976d2'),  # 蓝
        ('#f3e5f5', '#7b1fa2'),  # 紫
        ('#e8f5e9', '#388e3c'),  # 绿
        ('#fff3e0', '#f57c00'),  # 橙
        ('#fce4ec', '#c2185b'),  # 粉
        ('#e0f2f1', '#00796b'),  # 青
        ('#f5f5f5', '#616161'),  # 灰
        ('#e8eaf6', '#3f51b5'),  # 靛蓝
    ]
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tag_spacing = 4  # 减小标签间距
        self.tag_padding_h = 6  # 减小水平内边距
        self.tag_height = 16  # 减小标签高度
        self.font_size = 10  # 减小字体大小
    
    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        """自定义绘制标签 - 单行紧凑排列"""
        # 获取标签数据
        tags_str = index.data(Qt.ItemDataRole.DisplayRole)
        if not tags_str or tags_str == "无标签":
            # 绘制短横线表示无标签，居中显示
            painter.save()
            painter.setPen(QColor('#ccc'))
            rect = option.rect
            center_y = rect.top() + rect.height() // 2
            center_x = rect.left() + rect.width() // 2
            # 短横线，固定长度20像素，居中
            painter.drawLine(center_x - 10, center_y, center_x + 10, center_y)
            painter.restore()
            return
        
        # 解析标签
        tags = [t.strip() for t in tags_str.split(',') if t.strip()]
        if not tags:
            super().paint(painter, option, index)
            return
        
        # 保存画家状态
        painter.save()
        
        # 设置渲染提示
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 计算绘制区域
        rect = option.rect.adjusted(4, 0, -4, 0)  # 只留左右边距
        
        # 设置字体
        font = QFont()
        font.setPointSize(self.font_size)
        painter.setFont(font)
        font_metrics = QFontMetrics(font)
        
        # 计算所有标签的总宽度，用于居中
        total_tags_width = 0
        tag_widths = []
        for tag in tags:
            text_width = font_metrics.horizontalAdvance(tag)
            tag_width = text_width + self.tag_padding_h * 2
            tag_widths.append(tag_width)
            total_tags_width += tag_width
        total_tags_width += self.tag_spacing * (len(tags) - 1)  # 加上间距
        
        # 计算起始X坐标（居中）
        x = rect.left() + (rect.width() - total_tags_width) // 2
        y = rect.top() + (rect.height() - self.tag_height) // 2
        
        # 绘制每个标签
        for i, tag in enumerate(tags):
            # 计算标签宽度
            text_width = font_metrics.horizontalAdvance(tag)
            tag_width = text_width + self.tag_padding_h * 2
            
            # 检查是否超出边界，超出则直接截断不绘制
            if x + tag_width > rect.right():
                break
            
            # 获取颜色
            bg_color, text_color = self.COLORS[i % len(self.COLORS)]
            
            # 绘制圆角矩形背景
            painter.setBrush(QColor(bg_color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(x, y, tag_width, self.tag_height, 8, 8)
            
            # 绘制文字
            painter.setPen(QColor(text_color))
            painter.drawText(x, y, tag_width, self.tag_height,
                           Qt.AlignmentFlag.AlignCenter, tag)
            
            # 移动X坐标
            x += tag_width + self.tag_spacing
        
        # 恢复画家状态
        painter.restore()
    
    def sizeHint(self, option: QStyleOptionViewItem, index):
        """返回建议大小 - 根据内容自适应，至少显示一个完整标签"""
        tags_str = index.data(Qt.ItemDataRole.DisplayRole)
        
        font = QFont()
        font.setPointSize(self.font_size)
        font_metrics = QFontMetrics(font)
        
        # 无标签时返回最小宽度
        if not tags_str or tags_str == "无标签":
            return QSize(50, 24)
        
        # 有标签时计算所需宽度
        tags = [t.strip() for t in tags_str.split(',') if t.strip()]
        if not tags:
            return QSize(50, 24)
        
        # 计算第一个标签的宽度（确保至少能显示一个）
        first_tag_width = font_metrics.horizontalAdvance(tags[0]) + self.tag_padding_h * 2 + 8
        
        # 计算所有标签的总宽度
        total_width = 8  # 左右边距
        for i, tag in enumerate(tags):
            text_width = font_metrics.horizontalAdvance(tag)
            total_width += text_width + self.tag_padding_h * 2
            if i < len(tags) - 1:
                total_width += self.tag_spacing
        
        # 取最大值：确保至少显示一个标签，同时限制最大宽度
        final_width = max(first_tag_width, min(total_width, 200))
        
        return QSize(int(final_width), 24)
