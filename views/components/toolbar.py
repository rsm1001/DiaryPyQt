"""
主窗口工具栏组件
"""
from PyQt6.QtWidgets import QToolBar, QMainWindow
from PyQt6.QtGui import QAction, QIcon

from i18n import _


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
        # 尝试获取已有的工具栏
        self.toolbar = self.main_window.findChild(QToolBar, 'MainToolBar')
        if self.toolbar is None:
            self.toolbar = self.main_window.addToolBar(_('Main'))
            self.toolbar.setObjectName('MainToolBar')
        else:
            # 清除现有动作
            self.toolbar.clear()

        # 新建日记
        self.new_action = QAction(QIcon(), _('新建日记'), self.main_window)
        self.new_action.setShortcut('Ctrl+N')
        self.new_action.triggered.connect(self.main_window.new_diary)
        self.toolbar.addAction(self.new_action)
        
        # 随机查看
        self.random_action = QAction(QIcon(), _('随机查看'), self.main_window)
        self.random_action.setShortcut('Ctrl+R')
        self.random_action.triggered.connect(self.main_window.random_view)
        self.toolbar.addAction(self.random_action)
        
        # 随机删除
        self.random_delete_action = QAction(QIcon(), _('随机删除'), self.main_window)
        self.random_delete_action.triggered.connect(self.main_window.random_delete)
        self.toolbar.addAction(self.random_delete_action)
        
        # 搜索
        self.search_action = QAction(QIcon(), _('搜索'), self.main_window)
        self.search_action.setShortcut('Ctrl+F')
        self.search_action.triggered.connect(self.main_window.search_diary)
        self.toolbar.addAction(self.search_action)
        
        # 切换主题
        self.theme_action = QAction(QIcon(), _('切换主题'), self.main_window)
        self.theme_action.triggered.connect(self.main_window.toggle_theme)
        self.toolbar.addAction(self.theme_action)
        
        # 统计
        self.stats_action = QAction(QIcon(), _('统计'), self.main_window)
        self.stats_action.triggered.connect(self.main_window.show_statistics)
        self.toolbar.addAction(self.stats_action)
        
        # 刷新
        self.refresh_action = QAction(QIcon(), _('刷新'), self.main_window)
        self.refresh_action.setShortcut('F5')
        self.refresh_action.triggered.connect(self.main_window.load_data)
        self.toolbar.addAction(self.refresh_action)
        
        # 垃圾桶
        self.trash_action = QAction(QIcon(), _('垃圾桶'), self.main_window)
        self.trash_action.setShortcut('Ctrl+T')
        self.trash_action.triggered.connect(self.main_window.open_trash)
        self.toolbar.addAction(self.trash_action)

        self.toolbar.addSeparator()

        # 运行测试
        self.test_action = QAction(QIcon(), _('运行测试'), self.main_window)
        self.test_action.setShortcut('Ctrl+Shift+T')
        self.test_action.setToolTip('运行日记管理系统的单元测试和集成测试（统计、权重计算、日记筛选等核心业务逻辑）')
        self.test_action.triggered.connect(self.main_window.run_tests)
        self.toolbar.addAction(self.test_action)

        self.toolbar.addSeparator()

        # 批量删除
        self.batch_delete_action = QAction(QIcon(), _('批量删除'), self.main_window)
        self.batch_delete_action.setEnabled(False)
        self.batch_delete_action.triggered.connect(self.main_window.batch_delete_selected)
        self.toolbar.addAction(self.batch_delete_action)

        # 批量打标签
        self.batch_tag_action = QAction(QIcon(), _('批量打标签'), self.main_window)
        self.batch_tag_action.setEnabled(False)
        self.batch_tag_action.triggered.connect(self.main_window.batch_tag_selected)
        self.toolbar.addAction(self.batch_tag_action)

        return self.toolbar

    def set_batch_actions_enabled(self, enabled: bool):
        """批量操作按钮启用/禁用状态"""
        self.batch_delete_action.setEnabled(enabled)
        self.batch_tag_action.setEnabled(enabled)
