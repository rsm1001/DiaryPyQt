"""
主窗口菜单栏组件
"""
from PyQt6.QtWidgets import QMainWindow, QMenuBar
from PyQt6.QtGui import QAction


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
        file_menu = menubar.addMenu('文件')
        
        export_action = QAction('导出数据...', self.main_window)
        export_action.triggered.connect(self.main_window.export_data)
        file_menu.addAction(export_action)
        
        import_action = QAction('导入数据...', self.main_window)
        import_action.triggered.connect(self.main_window.import_data)
        file_menu.addAction(import_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction('退出', self.main_window)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.triggered.connect(self.main_window.close)
        file_menu.addAction(exit_action)
    
    def _create_edit_menu(self, menubar: QMenuBar):
        """创建编辑菜单"""
        edit_menu = menubar.addMenu('编辑')
        
        new_action = QAction('新建日记', self.main_window)
        new_action.setShortcut('Ctrl+N')
        new_action.triggered.connect(self.main_window.new_diary)
        edit_menu.addAction(new_action)
        
        edit_menu.addSeparator()
        
        search_action = QAction('搜索', self.main_window)
        search_action.setShortcut('Ctrl+F')
        search_action.triggered.connect(self.main_window.search_diary)
        edit_menu.addAction(search_action)
    
    def _create_view_menu(self, menubar: QMenuBar):
        """创建视图菜单"""
        view_menu = menubar.addMenu('视图')
        
        theme_action = QAction('切换主题', self.main_window)
        theme_action.triggered.connect(self.main_window.toggle_theme)
        view_menu.addAction(theme_action)
    
    def _create_tools_menu(self, menubar: QMenuBar):
        """创建工具菜单"""
        tools_menu = menubar.addMenu('工具')
        
        stats_action = QAction('统计信息', self.main_window)
        stats_action.triggered.connect(self.main_window.show_statistics)
        tools_menu.addAction(stats_action)
    
    def _create_help_menu(self, menubar: QMenuBar):
        """创建帮助菜单"""
        help_menu = menubar.addMenu('帮助')
        
        about_action = QAction('关于', self.main_window)
        about_action.triggered.connect(self.main_window.show_about)
        help_menu.addAction(about_action)
