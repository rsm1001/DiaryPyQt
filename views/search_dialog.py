"""
搜索对话框 - 从主窗口中解耦出来的独立模块

- 自定义 ``HighlightSnippetDelegate`` 把每行画成"标题 + 命中摘要"两行富文本
  （关键词用 ``<span style="...">...</span>`` 标黄）
- 底部"摘要预览" ``QTextBrowser`` 在选中结果时把整篇日记标黄
- 通过 ``utils.text_tokenizer`` 做多语种分词，高亮器用
  ``utils.text_highlighter`` 构造 HTML 片段
"""

from html import escape
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QSplitter,
                            QWidget, QListWidget, QListWidgetItem, QLabel,
                            QLineEdit, QPushButton, QGroupBox,
                            QMessageBox, QApplication, QTextBrowser,
                            QStyledItemDelegate, QStyle)
from PyQt6.QtCore import Qt, QSize, QRectF
from PyQt6.QtGui import QTextDocument
from views.dialogs.base_dialog import CenteredDialogMixin, ContextMenuMixin

from i18n import _
from utils.text_highlighter import build_snippet, highlight_text, count_hits


# 高亮摘要的整体 HTML 样式（标题 + 摘要两行）
# 选中态由委托按 option.state 动态覆盖颜色
TITLE_STYLE = 'color:#666;font-size:11px;font-weight:bold;'
BODY_STYLE = 'color:#222;font-size:12px;'
TITLE_STYLE_SEL = 'color:#e0e0e0;font-size:11px;font-weight:bold;'
BODY_STYLE_SEL = 'color:#ffffff;font-size:12px;'

# 行高上下内边距（与委托 / setSizeHint 同步）
ROW_VERTICAL_PADDING = 10


def _row_html_for_diary(diary, tags, tokens):
    """
    把单条日记渲染成委托可消费的 HTML（含命中数 + 摘要）。
    """
    tags_str = ""
    if tags:
        tags_str = " [{}]".format(', '.join([tag['name'] for tag in tags]))
    if tokens:
        hits = count_hits(diary.content, tokens)
        snippet_html = build_snippet(diary.content, tokens)
    else:
        hits = 0
        snippet_html = ""

    title_html = (
        '<div style="TITLE">[{}] {} (查看: {}){} · 命中 {} 处</div>'.format(
            diary.id, diary.date, diary.view_count, tags_str, hits,
        )
    )
    if snippet_html:
        body_html = '<div style="BODY">{}</div>'.format(snippet_html)
    else:
        preview = escape(diary.content[:80])
        suffix = '…' if len(diary.content) > 80 else ''
        body_html = '<div style="BODY">{}{}</div>'.format(preview, suffix)
    return title_html + body_html


def _strip_style(html: str, marker: str) -> str:
    """从 ``<div style="MARKER">`` 中把 marker 整体替换为空（保留引号外结构）"""
    return html.replace('style="{}"'.format(marker), 'style=""')


def _html_height(html: str, font, width: int) -> int:
    """
    给定 HTML / 字体 / 容器宽度，返回 QTextDocument 渲染所需的高度。
    """
    doc = QTextDocument()
    doc.setDefaultFont(font)
    doc.setHtml(html)
    doc.setTextWidth(max(1, width - 16))
    return int(doc.documentLayout().documentSize().height()) + ROW_VERTICAL_PADDING


# ---------------------------------------------------------------------------
# 自定义委托：两行富文本（标题 + 高亮摘要）
# ---------------------------------------------------------------------------

class HighlightSnippetDelegate(QStyledItemDelegate):
    """
    把每个 QListWidgetItem 画成两行富文本：

    - 第 1 行：``[id] date · 命中 N 处``
    - 第 2 行：高亮摘要（关键词用黄色高亮 + 省略号上下文窗口）

    HTML 颜色占位符 ``TITLE`` / ``BODY`` 在 paint 时按选中态替换为具体颜色。
    ``sizeHint`` 根据 item 的 HTML 真算高度，避免溢出。
    """

    def sizeHint(self, option, index):
        raw = index.data(Qt.ItemDataRole.DisplayRole) or ''
        width = option.rect.width() if option.rect.width() > 0 else 400
        h = _html_height(raw, option.font, width)
        return QSize(width, max(40, h))

    def paint(self, painter, option, index):
        painter.save()
        # 关键：先按行高裁剪，防止 QTextDocument 溢出到下一行
        painter.setClipRect(option.rect)

        is_sel = bool(option.state & QStyle.StateFlag.State_Selected)
        if is_sel:
            painter.fillRect(option.rect, option.palette.highlight())

        raw = index.data(Qt.ItemDataRole.DisplayRole) or ''
        title = TITLE_STYLE_SEL if is_sel else TITLE_STYLE
        body = BODY_STYLE_SEL if is_sel else BODY_STYLE
        # 把模板里的 TITLE / BODY 占位符替换成最终样式
        html = raw.replace('style="TITLE"', 'style="{}"'.format(title))
        html = html.replace('style="BODY"', 'style="{}"'.format(body))

        doc = QTextDocument()
        doc.setDefaultFont(option.font)
        doc.setHtml(html)

        text_rect = QRectF(
            option.rect.x() + 8,
            option.rect.y() + 5,
            max(1, option.rect.width() - 16),
            max(1, option.rect.height() - ROW_VERTICAL_PADDING),
        )
        doc.setTextWidth(text_rect.width())
        painter.translate(text_rect.x(), text_rect.y())
        doc.drawContents(painter)
        painter.restore()


# ---------------------------------------------------------------------------
# 搜索对话框
# ---------------------------------------------------------------------------

class SearchDialog(QDialog, CenteredDialogMixin, ContextMenuMixin):
    """搜索对话框 - 从主窗口解耦出来的功能"""

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.current_results = []  # 当前显示的结果
        self._current_item = None  # 当前右键点击的项
        self._current_tokens = []  # 当前搜索的 token 列表（供高亮用）
        self._snippet_delegate = HighlightSnippetDelegate(self)  # 用于 setSizeHint
        self.init_ui()
        self.load_tags()  # 加载标签

    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle(_("搜索日记"))
        # 设置窗口大小
        self.resize(820, 560)

        # 设置窗口居中于父窗口
        self.center_on_parent()

        layout = QVBoxLayout()

        # 创建水平分割器，左右分栏
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧面板：搜索和标签
        left_panel = QWidget()
        left_layout = QVBoxLayout()

        # 搜索输入区域
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel(_("关键词:")))
        self.keyword_input = QLineEdit()
        self.keyword_input.returnPressed.connect(self.perform_search)
        search_layout.addWidget(self.keyword_input)

        self.search_btn = QPushButton(_("搜索"))
        self.search_btn.clicked.connect(self.perform_search)
        search_layout.addWidget(self.search_btn)

        left_layout.addLayout(search_layout)

        # 标签区域
        tags_group = QGroupBox(_("标签"))
        tags_layout = QVBoxLayout()

        # 标签列表
        self.tags_list = QListWidget()
        self.tags_list.setMaximumWidth(200)
        self.tags_list.itemClicked.connect(self.on_tag_clicked)
        tags_layout.addWidget(self.tags_list)

        # 标签操作按钮
        tag_button_layout = QHBoxLayout()

        self.refresh_tags_btn = QPushButton(_("刷新标签"))
        self.refresh_tags_btn.clicked.connect(self.load_tags)
        tag_button_layout.addWidget(self.refresh_tags_btn)

        self.clear_filter_btn = QPushButton(_("清除筛选"))
        self.clear_filter_btn.clicked.connect(self.clear_filter)
        tag_button_layout.addWidget(self.clear_filter_btn)

        self.delete_unused_tags_btn = QPushButton(_("删除未用标签"))
        self.delete_unused_tags_btn.clicked.connect(self.delete_unused_tags)
        tag_button_layout.addWidget(self.delete_unused_tags_btn)

        tags_layout.addLayout(tag_button_layout)

        tags_group.setLayout(tags_layout)
        left_layout.addWidget(tags_group)

        left_panel.setLayout(left_layout)
        splitter.addWidget(left_panel)

        # 右侧面板：搜索结果
        right_panel = QWidget()
        right_layout = QVBoxLayout()

        # 结果标题
        self.result_title = QLabel(_("搜索结果"))
        self.result_title.setStyleSheet("font-weight: bold; font-size: 12px;")
        right_layout.addWidget(self.result_title)

        # 结果列表（带自定义委托）
        self.results_list = QListWidget()
        self.results_list.setItemDelegate(self._snippet_delegate)
        self.results_list.setUniformItemSizes(False)
        self.results_list.currentItemChanged.connect(self._on_current_changed)
        right_layout.addWidget(self.results_list, 3)

        # 摘要预览区（选中结果时显示整篇标黄）
        preview_label = QLabel(_("命中预览"))
        preview_label.setStyleSheet("font-size: 11px; color: #666;")
        right_layout.addWidget(preview_label)

        self.preview_browser = QTextBrowser()
        self.preview_browser.setMaximumHeight(180)
        self.preview_browser.setOpenExternalLinks(False)
        right_layout.addWidget(self.preview_browser, 1)

        # 结果计数
        self.result_count_label = QLabel(_("共 0 条结果"))
        self.result_count_label.setStyleSheet("font-size: 10px; color: gray;")
        right_layout.addWidget(self.result_count_label)

        right_panel.setLayout(right_layout)
        splitter.addWidget(right_panel)

        # 设置分割器比例
        splitter.setSizes([250, 570])

        layout.addWidget(splitter)

        # 按钮区域
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.ok_btn = QPushButton(_("确定"))
        self.ok_btn.clicked.connect(self.accept)
        self.cancel_btn = QPushButton(_("取消"))
        self.cancel_btn.clicked.connect(self.reject)

        button_layout.addWidget(self.ok_btn)
        button_layout.addWidget(self.cancel_btn)
        button_layout.addStretch()

        layout.addLayout(button_layout)

        self.setLayout(layout)

        # 焦点
        self.keyword_input.setFocus()

        # 右键菜单
        self.setup_context_menu_for_list(self.results_list)

    def _on_result_item_clicked(self, item):
        self._current_item = item

    def _on_current_changed(self, current, _previous):
        """选中项变化时刷新摘要预览"""
        if current is None:
            self.preview_browser.clear()
            return
        diary = current.data(Qt.ItemDataRole.UserRole)
        if not diary:
            self.preview_browser.clear()
            return
        if self._current_tokens:
            html = highlight_text(diary.content, self._current_tokens)
        else:
            # 标签筛选 / 全部日记路径：无高亮，纯转义
            html = '<pre style="white-space:pre-wrap;font-family:inherit;">{}</pre>'.format(
                escape(diary.content)
            )
        self.preview_browser.setHtml(html)

    def center_on_parent(self):
        parent = self.parentWidget()
        if parent:
            parent_geo = parent.geometry()
            x = parent_geo.x() + (parent_geo.width() - self.width()) // 2
            y = parent_geo.y() + (parent_geo.height() - self.height()) // 2
            screen_geo = QApplication.primaryScreen().geometry()
            x = max(0, min(x, screen_geo.width() - self.width()))
            y = max(0, min(y, screen_geo.height() - self.height()))
            self.move(x, y)
        else:
            screen_geo = QApplication.primaryScreen().geometry()
            x = (screen_geo.width() - self.width()) // 2
            y = (screen_geo.height() - self.height()) // 2
            self.move(screen_geo.x() + x, screen_geo.y() + y)

    def load_tags(self):
        self.tags_list.clear()
        tags = self.controller.get_all_tags()
        for tag in tags:
            item = QListWidgetItem("#{}".format(tag['name']))
            item.setData(Qt.ItemDataRole.UserRole, tag)
            self.tags_list.addItem(item)
        if not tags:
            self.tags_list.addItem(QListWidgetItem(_("暂无标签")))

    def on_tag_clicked(self, item):
        tag_data = item.data(Qt.ItemDataRole.UserRole)
        if tag_data:
            tag_id = tag_data['id']
            diaries = self.controller.get_diaries_by_tag_id(tag_id)
            # 标签筛选走"无关键词"路径
            self._current_tokens = []
            self.display_results(diaries, "标签: #{}".format(tag_data['name']))

    def perform_search(self):
        """执行关键词搜索"""
        keyword = self.keyword_input.text().strip()
        if not keyword:
            self._current_tokens = []
            diaries = self.controller.get_all_diaries(limit=50)
            self.display_results(diaries, _("全部日记"))
            return

        # 缓存 token 供高亮用
        from utils.text_tokenizer import tokenize
        self._current_tokens = tokenize(keyword)
        results = self.controller.search_by_keyword(keyword)
        self.display_results(results, "关键词: '{}'".format(keyword))

    def display_results(self, diaries, search_type):
        """显示搜索结果"""
        self.results_list.clear()
        self.preview_browser.clear()
        self.current_results = diaries

        # 提前算一次容器宽度（一次 addItem 期间 viewport 宽度是稳定的）
        list_w = max(1, self.results_list.viewport().width() - 4)
        font = self.results_list.font()

        for diary in diaries:
            tags = self.controller.get_tags_by_diary_id(diary.id)
            html = _row_html_for_diary(diary, tags, self._current_tokens)
            item = QListWidgetItem(html)
            item.setData(Qt.ItemDataRole.UserRole, diary)
            # 关键：给 item 设真正需要的高度，否则 QListWidget 用默认行高，委托画超出去
            hint_h = _html_height(html, font, list_w)
            item.setSizeHint(QSize(list_w, max(48, hint_h)))
            self.results_list.addItem(item)

        count = len(diaries)
        self.result_count_label.setText(_("共 {} 条结果 - {}".format(count, search_type)))

        if not diaries:
            self.results_list.addItem(_("没有找到匹配的日记"))

    def clear_filter(self):
        self.keyword_input.clear()
        self._current_tokens = []
        diaries = self.controller.get_all_diaries(limit=50)
        self.display_results(diaries, "全部日记")

    def delete_unused_tags(self):
        unused_tags = self.controller.get_unused_tags()
        if not unused_tags:
            QMessageBox.information(self, _("提示"), _("没有未被使用的标签，无需删除。"))
            return

        unused_tag_names = [tag['name'] for tag in unused_tags]
        tag_list_str = "\n".join(unused_tag_names)

        reply = QMessageBox.question(
            self,
            _("确认删除未使用标签"),
            _("以下标签未被任何日记使用，是否删除？\n\n{}\n\n确认删除吗？".format(tag_list_str)),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            deleted_count = 0
            failed_count = 0

            for tag in unused_tags:
                try:
                    success = self.controller.delete_tag_by_id(tag['id'])
                    if success:
                        deleted_count += 1
                    else:
                        failed_count += 1
                except Exception as e:
                    failed_count += 1
                    print("删除标签失败: {}".format(e))

            QMessageBox.information(
                self, _("删除结果"),
                _("删除完成！\n成功删除: {} 个\n失败: {} 个".format(deleted_count, failed_count))
            )
            self.load_tags()

    def _remove_result_item(self, item):
        if item and item.listWidget():
            row = item.listWidget().row(item)
            item.listWidget().takeItem(row)
            if item in self.current_results:
                self.current_results.remove(item)
            self.result_count_label.setText(_("共 {} 条结果".format(len(self.current_results))))

    def _refresh_search_results(self):
        keyword = self.keyword_input.text().strip()
        if keyword:
            from utils.text_tokenizer import tokenize
            self._current_tokens = tokenize(keyword)
            results = self.controller.search_by_keyword(keyword)
            self.display_results(results, "关键词: '{}'".format(keyword))
        else:
            self._current_tokens = []
            results = self.controller.get_all_diaries(limit=50)
            self.display_results(results, "全部日记")

