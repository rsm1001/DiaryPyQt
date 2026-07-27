"""
详情面板组件 - 显示日记详情
"""
import logging
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt

from i18n import _

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

        self.detail_label = QLabel(_("请选择一篇日记查看详情"))
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
            content_html = self._format_content(diary.content)
            content = "<b>ID:</b> {}<br>" \
                     "<b>日期:</b> {}<br>" \
                     "<b>查看次数:</b> {}<br>" \
                     "<b>标签:</b> {}<br><br>" \
                     "<b>内容:</b><br>{}".format(
                         diary.id, diary.date, diary.view_count, tags_html, content_html
                     )
            self.detail_label.setText(content)
            logger.info("更新详情面板: diary_id={}".format(diary.id))
        else:
            self.detail_label.setText(_("请选择一篇日记查看详情"))
            logger.debug("清空详情面板")

    def set_diary(self, diary, tokens=None, tags_html: str = ""):
        """
        显式入口：支持关键词高亮。

        - ``tokens`` 非空时整篇 ``content`` 走 ``highlight_text`` 标黄
        - 日常表格点击不传 tokens，走 ``update_content`` 原路径
        """
        if diary is None:
            self._last_tokens = []
            return self.update_content(None)
        self._last_tokens = list(tokens) if tokens else []
        self.update_content(diary, tags_html=tags_html)

    def highlight_with_tokens(self, tokens):
        """由外部（搜索跳转时）调用，更新当前选中的 diary 渲染"""
        self._last_tokens = list(tokens) if tokens else []
        self.update()

    def _format_content(self, content: str) -> str:
        """根据 ``_last_tokens`` 决定是否走高亮 HTML"""
        tokens = getattr(self, '_last_tokens', None) or []
        if not tokens:
            return content
        from utils.text_highlighter import highlight_text
        return highlight_text(content, tokens)

    def set_max_height(self, max_height: int, min_height: int = 80):
        """设置面板高度限制"""
        self.setMaximumHeight(max_height)
        self.setMinimumHeight(min_height)
