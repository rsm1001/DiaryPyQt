"""
主窗口菜单栏组件
"""
from PyQt6.QtWidgets import QMainWindow, QMenuBar, QMenu
from PyQt6.QtGui import QAction

from i18n import _, set_language, get_current_language, get_language_name, get_available_languages


class MainMenuBar:
    """主窗口菜单栏管理器"""
    
    def __init__(self, main_window: QMainWindow):
        """
        初始化菜单栏管理器
        
        Args:
            main_window: 主窗口实例，用于添加菜单和连接信号
        """
        self.main_window = main_window
    
    def create(self) -> QMenuBar:
        """
        创建并返回菜单栏

        Returns:
            创建好的菜单栏实例
        """
        menubar = self.main_window.menuBar()

        # 清除现有菜单（语言切换时需要重建）
        menubar.clear()

        # 文件菜单
        self._create_file_menu(menubar)

        # 编辑菜单
        self._create_edit_menu(menubar)

        # 视图菜单
        self._create_view_menu(menubar)

        # 工具菜单
        self._create_tools_menu(menubar)

        # 帮助菜单
        self._create_help_menu(menubar)

        return menubar
    
    def _create_file_menu(self, menubar: QMenuBar):
        """创建文件菜单"""
        file_menu = menubar.addMenu(_('文件'))
        
        export_action = QAction(_('导出数据...'), self.main_window)
        export_action.triggered.connect(self.main_window.export_data)
        file_menu.addAction(export_action)
        
        import_action = QAction(_('导入数据...'), self.main_window)
        import_action.triggered.connect(self.main_window.import_data)
        file_menu.addAction(import_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction(_('退出'), self.main_window)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.triggered.connect(self.main_window.close)
        file_menu.addAction(exit_action)
    
    def _create_edit_menu(self, menubar: QMenuBar):
        """创建编辑菜单"""
        edit_menu = menubar.addMenu(_('编辑'))
        
        new_action = QAction(_('新建日记'), self.main_window)
        new_action.setShortcut('Ctrl+N')
        new_action.triggered.connect(self.main_window.new_diary)
        edit_menu.addAction(new_action)
        
        edit_menu.addSeparator()
        
        search_action = QAction(_('搜索'), self.main_window)
        search_action.setShortcut('Ctrl+F')
        search_action.triggered.connect(self.main_window.search_diary)
        edit_menu.addAction(search_action)
    
    def _create_view_menu(self, menubar: QMenuBar):
        """创建视图菜单"""
        view_menu = menubar.addMenu(_('视图'))

        theme_action = QAction(_('切换主题'), self.main_window)
        theme_action.triggered.connect(self.main_window.toggle_theme)
        view_menu.addAction(theme_action)

        view_menu.addSeparator()

        # 语言子菜单
        language_menu = QMenu(_('语言'), self.main_window)
        view_menu.addMenu(language_menu)

        current_lang = get_current_language()
        for lang in get_available_languages():
            action = QAction(get_language_name(lang), self.main_window, checkable=True)
            action.setChecked(lang == current_lang)
            action.triggered.connect(lambda checked, l=lang: self._on_language_changed(l))
            language_menu.addAction(action)

        view_menu.addSeparator()

        column_action = QAction(_('自定义列表列...'), self.main_window)
        column_action.triggered.connect(self.main_window.show_column_settings)
        view_menu.addAction(column_action)

    def _on_language_changed(self, lang):
        """语言切换处理"""
        set_language(lang)
        # 通知主窗口需要刷新UI
        if hasattr(self.main_window, 'on_language_changed'):
            self.main_window.on_language_changed(lang)
    
    def _create_tools_menu(self, menubar: QMenuBar):
        """创建工具菜单"""
        tools_menu = menubar.addMenu(_('工具'))

        stats_action = QAction(_('统计信息'), self.main_window)
        stats_action.triggered.connect(self.main_window.show_statistics)
        tools_menu.addAction(stats_action)

        tools_menu.addSeparator()

        run_tests_action = QAction(_('运行测试'), self.main_window)
        run_tests_action.setShortcut('Ctrl+Shift+T')
        run_tests_action.triggered.connect(self.main_window.run_tests)
        tools_menu.addAction(run_tests_action)

        tools_menu.addSeparator()

        trash_action = QAction(_('垃圾桶'), self.main_window)
        trash_action.setShortcut('Ctrl+T')
        trash_action.triggered.connect(self.main_window.open_trash)
        tools_menu.addAction(trash_action)
    
    def _create_help_menu(self, menubar: QMenuBar):
        """创建帮助菜单"""
        help_menu = menubar.addMenu(_('帮助'))
        
        about_action = QAction(_('关于'), self.main_window)
        about_action.triggered.connect(self.main_window.show_about)
        help_menu.addAction(about_action)
