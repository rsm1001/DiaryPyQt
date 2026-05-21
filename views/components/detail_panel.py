"""
详情面板组件 - 显示日记详情
"""
import logging
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt

logger = logging.getLogger(__name__)


class DetailPanel(QWidget):
    """日记详情面板组件"""

    def __init__(self, parent=None):
        """初始化详情面板"""
        super().__init__(parent)
        self._setup_ui()
        logger.debug("DetailPanel 初始化完成")

    def _setup_ui(self):
        """设置UI组件"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        self.detail_label = QLabel("请选择一篇日记查看详情")
        self.detail_label.setWordWrap(True)
        self.detail_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.detail_label.setContentsMargins(10, 10, 10, 10)
        self.detail_label.setStyleSheet("""
            QLabel {
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 8px;
            }
        """)
        layout.addWidget(self.detail_label)
        logger.debug("详情面板 UI 设置完成")

    def update_content(self, diary, tags_html: str = ""):
        """更新详情内容"""
        if diary:
            content = f"<b>ID:</b> {diary.id}<br>" \
                     f"<b>日期:</b> {diary.date}<br>" \
                     f"<b>查看次数:</b> {diary.view_count}<br>" \
                     f"<b>标签:</b> {tags_html}<br><br>" \
                     f"<b>内容:</b><br>{diary.content}"
            self.detail_label.setText(content)
            logger.info(f"更新详情面板: diary_id={diary.id}")
        else:
            self.detail_label.setText("请选择一篇日记查看详情")
            logger.debug("清空详情面板")

    def set_max_height(self, max_height: int, min_height: int = 80):
        """设置面板高度限制"""
        self.setMaximumHeight(max_height)
        self.setMinimumHeight(min_height)
