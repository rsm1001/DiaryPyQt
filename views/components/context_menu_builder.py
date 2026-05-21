"""
右键菜单构建器组件
"""
import logging
from PyQt6.QtWidgets import QMenu
from PyQt6.QtCore import QPoint

logger = logging.getLogger(__name__)


class ContextMenuBuilder:
    """右键菜单构建器"""

    def __init__(self, parent):
        """初始化菜单构建器"""
        self.parent = parent
        self._view_handler = None
        self._edit_handler = None
        self._delete_handler = None
        self._batch_delete_handler = None
        self._batch_tag_handler = None
        logger.debug("ContextMenuBuilder 初始化完成")

    def set_handlers(self, view, edit, delete, batch_delete=None, batch_tag=None):
        """设置菜单动作处理器"""
        self._view_handler = view
        self._edit_handler = edit
        self._delete_handler = delete
        self._batch_delete_handler = batch_delete
        self._batch_tag_handler = batch_tag
        logger.debug("菜单处理器已设置")

    def build_and_show(self, position: QPoint) -> bool:
        """构建并显示菜单，返回是否显示了菜单"""
        menu = QMenu(self.parent)

        selected = self.parent.table_view.selectionModel().selectedRows()
        count = len(selected)

        if count == 0:
            logger.debug("无选中行，不显示菜单")
            return False
        elif count == 1:
            menu.addAction("查看", self._view_handler)
            menu.addAction("编辑", self._edit_handler)
            menu.addAction("删除", self._delete_handler)
            logger.debug("显示单选菜单")
        else:
            menu.addAction(f"查看 ({count}篇)", self._view_handler)
            menu.addAction(f"编辑 ({count}篇)", self._edit_handler)
            menu.addSeparator()
            menu.addAction(f"批量删除 ({count}篇)", self._batch_delete_handler)
            menu.addAction(f"批量打标签 ({count}篇)", self._batch_tag_handler)
            logger.debug(f"显示批量菜单: count={count}")

        menu.exec(self.parent.table_view.viewport().mapToGlobal(position))
        return True


class ContextMenuFactory:
    """右键菜单工厂"""

    @staticmethod
    def create_context_menu(parent, selection_count: int, handlers: dict):
        """创建上下文菜单

        Args:
            parent: 父窗口
            selection_count: 选中数量
            handlers: 处理器字典，包含 view, edit, delete, batch_delete, batch_tag

        Returns:
            QMenu 实例
        """
        menu = QMenu(parent)

        if selection_count == 0:
            return None
        elif selection_count == 1:
            menu.addAction("查看", handlers.get('view'))
            menu.addAction("编辑", handlers.get('edit'))
            menu.addAction("删除", handlers.get('delete'))
            logger.debug("创建单选上下文菜单")
        else:
            menu.addAction(f"查看 ({selection_count}篇)", handlers.get('view'))
            menu.addAction(f"编辑 ({selection_count}篇)", handlers.get('edit'))
            menu.addSeparator()
            menu.addAction(f"批量删除 ({selection_count}篇)", handlers.get('batch_delete'))
            menu.addAction(f"批量打标签 ({selection_count}篇)", handlers.get('batch_tag'))
            logger.debug(f"创建批量上下文菜单: count={selection_count}")

        return menu
