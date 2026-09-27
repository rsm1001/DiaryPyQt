"""UI 组件模块。"""

from .menus.context_menu_builder import ContextMenuBuilder, ContextMenuFactory
from .panels.detail_panel import DetailPanel
from .tables.table_view_manager import TableViewManager
from .window_chrome.menu_bar import MainMenuBar
from .window_chrome.status_bar_manager import StatusBarManager
from .window_chrome.toolbar import MainToolBar

__all__ = [
    'MainToolBar',
    'MainMenuBar',
    'DetailPanel',
    'StatusBarManager',
    'TableViewManager',
    'ContextMenuBuilder',
    'ContextMenuFactory',
]
