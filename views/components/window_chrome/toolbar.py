"""
主窗口工具栏组件
"""
from PyQt6.QtWidgets import QToolBar, QMainWindow, QMenu, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QDialog, QLabel, QLayout
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtCore import Qt

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
        self.random_filter_action = None  # 新增：随机查看筛选按钮
        self.random_delete_action = None
        self.search_action = None
        self.theme_action = None
        self.stats_action = None
        self.refresh_action = None
        self._random_filter_menu = None  # 筛选弹窗
        self._filter_tag_widget = None  # 标签筛选组件（由 TagFilterWidget 管理）
    
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

        # 随机查看筛选
        self._create_random_filter_button()
        self.toolbar.addAction(self.random_filter_action)

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

    def _create_random_filter_button(self):
        """创建随机查看筛选按钮"""
        self.random_filter_action = QAction(QIcon(), _('☐ 筛选'), self.main_window)
        self.random_filter_action.setToolTip(_('随机查看筛选'))
        self.random_filter_action.triggered.connect(self._show_random_filter_menu)

    def _show_random_filter_menu(self, pos=None):
        """显示随机查看筛选弹窗"""
        # 复用已有的筛选弹窗
        if not hasattr(self, '_random_filter_dialog') or self._random_filter_dialog is None:
            self._random_filter_dialog = QDialog(self.main_window)
            self._random_filter_dialog.setWindowTitle(_('随机查看筛选'))
            self._random_filter_dialog.setModal(True)
            self._random_filter_dialog.setMinimumWidth(280)
            self._build_random_filter_content(self._random_filter_dialog)

        self._random_filter_dialog.show()
        self._random_filter_dialog.activateWindow()

    def _build_random_filter_content(self, dialog):
        """构建随机查看筛选弹窗内容"""
        from views.components.filters.tag_filter_panel import TagFilterPanel

        # 清除旧内容
        old_layout = dialog.layout()
        if old_layout:
            QLayout().deleteLater()
        dialog.setLayout(QVBoxLayout())

        main_layout = dialog.layout()
        main_layout.setContentsMargins(10, 10, 10, 10)

        # 标签筛选组件
        self._filter_tag_widget = TagFilterPanel(
            controller=self.main_window.controller,
            initial_tag_ids=self.main_window.random_filter_manager.get_selected_tag_ids()
        )
        main_layout.addWidget(self._filter_tag_widget)

        # 按钮区域
        btn_layout = QHBoxLayout()

        clear_btn = QPushButton(_('清除筛选'))
        clear_btn.clicked.connect(self._clear_random_filter)
        btn_layout.addWidget(clear_btn)

        confirm_btn = QPushButton(_('确定'))
        confirm_btn.clicked.connect(lambda: self._apply_random_filter(dialog))
        btn_layout.addWidget(confirm_btn)

        cancel_btn = QPushButton(_('取消'))
        cancel_btn.clicked.connect(dialog.hide)
        btn_layout.addWidget(cancel_btn)

        main_layout.addLayout(btn_layout)

    def _load_filter_tags(self):
        """加载所有标签到筛选弹窗（委托给 TagFilterWidget）"""
        if hasattr(self, '_filter_tag_widget') and self._filter_tag_widget:
            self._filter_tag_widget.load_tags()
            self._filter_tag_widget.set_selected_tag_ids(
                self.main_window.random_filter_manager.get_selected_tag_ids()
            )

    def _apply_random_filter(self, dialog):
        """应用随机查看筛选设置"""
        selected_ids = list(self._filter_tag_widget.get_selected_tag_ids())
        self.main_window.random_filter_manager.set_selected_tag_ids(selected_ids)
        self._update_filter_action_text()
        dialog.hide()

    def _clear_random_filter(self):
        """清除随机查看筛选"""
        self.main_window.random_filter_manager.clear()
        if hasattr(self, '_filter_tag_widget') and self._filter_tag_widget:
            self._filter_tag_widget.set_selected_tag_ids([])
        self._update_filter_action_text()

    def _update_filter_action_text(self):
        """更新筛选按钮文本和提示"""
        selected_ids = self.main_window.random_filter_manager.get_selected_tag_ids()
        if selected_ids:
            # 获取选中的标签名称
            all_tags = self.main_window.controller.get_all_tags()
            tag_map = {t['id']: t['name'] for t in all_tags}
            selected_names = [tag_map.get(tid, str(tid)) for tid in selected_ids]
            self.random_filter_action.setText(_('☑ 筛选'))
            self.random_filter_action.setToolTip(
                _('随机查看筛选中: %s') % ', '.join(selected_names)
            )
        else:
            self.random_filter_action.setText(_('☐ 筛选'))
            self.random_filter_action.setToolTip(_('随机查看筛选'))

    def set_batch_actions_enabled(self, enabled: bool):
        """批量操作按钮启用/禁用状态"""
        self.batch_delete_action.setEnabled(enabled)
        self.batch_tag_action.setEnabled(enabled)
