"""
主窗口工具栏组件
"""
from PyQt6.QtWidgets import QToolBar, QMainWindow
from PyQt6.QtGui import QAction, QIcon


class MainToolBar:
    """主窗口工具栏管理器"""
    
    def __init__(self, main_window: QMainWindow):
        """
        初始化工具栏管理器
        
        Args:
            main_window: 主窗口实例，用于添加工具栏和连接信号
        """
        self.main_window = main_window
        self.toolbar = None
        # 动作引用，供外部访问
        self.new_action = None
        self.random_action = None
        self.random_delete_action = None
        self.search_action = None
        self.theme_action = None
        self.stats_action = None
        self.refresh_action = None
    
    def create(self) -> QToolBar:
        """
        创建并返回工具栏
        
        Returns:
            创建好的工具栏实例
        """
        self.toolbar = self.main_window.addToolBar('Main')
        
        # 新建日记
        self.new_action = QAction(QIcon(), '新建日记', self.main_window)
        self.new_action.setShortcut('Ctrl+N')
        self.new_action.triggered.connect(self.main_window.new_diary)
        self.toolbar.addAction(self.new_action)
        
        # 随机查看
        self.random_action = QAction(QIcon(), '随机查看', self.main_window)
        self.random_action.setShortcut('Ctrl+R')
        self.random_action.triggered.connect(self.main_window.random_view)
        self.toolbar.addAction(self.random_action)
        
        # 随机删除
        self.random_delete_action = QAction(QIcon(), '随机删除', self.main_window)
        self.random_delete_action.triggered.connect(self.main_window.random_delete)
        self.toolbar.addAction(self.random_delete_action)
        
        # 搜索
        self.search_action = QAction(QIcon(), '搜索', self.main_window)
        self.search_action.setShortcut('Ctrl+F')
        self.search_action.triggered.connect(self.main_window.search_diary)
        self.toolbar.addAction(self.search_action)
        
        # 切换主题
        self.theme_action = QAction(QIcon(), '切换主题', self.main_window)
        self.theme_action.triggered.connect(self.main_window.toggle_theme)
        self.toolbar.addAction(self.theme_action)
        
        # 统计
        self.stats_action = QAction(QIcon(), '统计', self.main_window)
        self.stats_action.triggered.connect(self.main_window.show_statistics)
        self.toolbar.addAction(self.stats_action)
        
        # 刷新
        self.refresh_action = QAction(QIcon(), '刷新', self.main_window)
        self.refresh_action.setShortcut('F5')
        self.refresh_action.triggered.connect(self.main_window.load_data)
        self.toolbar.addAction(self.refresh_action)
        
        return self.toolbar
