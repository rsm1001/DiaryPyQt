"""
主题管理器
处理PyQt应用程序的主题切换
"""
from PyQt6.QtWidgets import QApplication, QWidget, QMainWindow
from PyQt6.QtCore import Qt


class ThemeManager:
    """主题管理器"""
    
    THEMES = {
        'light': {
            'stylesheet': """
                QMainWindow, QWidget {
                    background-color: #ffffff;
                    color: #000000;
                }
                QMenuBar {
                    background-color: #f0f0f0;
                    color: #000000;
                }
                QMenuBar::item:selected {
                    background-color: #007acc;
                    color: #ffffff;
                }
                QToolBar {
                    background-color: #f0f0f0;
                    border: 1px solid #cccccc;
                }
                QTableWidget {
                    background-color: #ffffff;
                    alternate-background-color: #f9f9f9;
                    gridline-color: #cccccc;
                    color: #000000;
                }
                QTableWidget::item:selected {
                    background-color: #007acc;
                    color: #ffffff;
                }
                QHeaderView::section {
                    background-color: #f0f0f0;
                    padding: 4px;
                    border: 1px solid #cccccc;
                    font-weight: bold;
                }
                QPushButton {
                    background-color: #f0f0f0;
                    border: 1px solid #cccccc;
                    padding: 5px;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #e0e0e0;
                }
                QPushButton:pressed {
                    background-color: #d0d0d0;
                }
                QLineEdit, QTextEdit {
                    background-color: #ffffff;
                    border: 1px solid #cccccc;
                    color: #000000;
                }
                QStatusBar {
                    background-color: #f0f0f0;
                    color: #000000;
                }
                QToolTip {
                    background-color: #ffffdc;
                    color: #000000;
                    border: 1px solid #cccccc;
                }
            """
        },
        'dark': {
            'stylesheet': """
                QMainWindow, QWidget {
                    background-color: #2b2b2b;
                    color: #dcdcdc;
                }
                QMenuBar {
                    background-color: #3c3c3c;
                    color: #dcdcdc;
                }
                QMenuBar::item:selected {
                    background-color: #569cd6;
                    color: #ffffff;
                }
                QToolBar {
                    background-color: #3c3c3c;
                    border: 1px solid #2b2b2b;
                }
                QTableWidget {
                    background-color: #1e1e1e;
                    alternate-background-color: #252525;
                    gridline-color: #3c3c3c;
                    color: #dcdcdc;
                }
                QTableWidget::item:selected {
                    background-color: #569cd6;
                    color: #ffffff;
                }
                QHeaderView::section {
                    background-color: #3c3c3c;
                    padding: 4px;
                    border: 1px solid #2b2b2b;
                    color: #dcdcdc;
                    font-weight: bold;
                }
                QPushButton {
                    background-color: #3c3c3c;
                    border: 1px solid #555555;
                    color: #dcdcdc;
                    padding: 5px;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #4a4a4a;
                }
                QPushButton:pressed {
                    background-color: #5a5a5a;
                }
                QLineEdit, QTextEdit {
                    background-color: #3c3c3c;
                    border: 1px solid #555555;
                    color: #dcdcdc;
                }
                QStatusBar {
                    background-color: #3c3c3c;
                    color: #dcdcdc;
                }
                QToolTip {
                    background-color: #363636;
                    color: #ffffff;
                    border: 1px solid #555555;
                }
            """
        }
    }
    
    def apply_theme(self, widget: QWidget, theme_name: str = 'light'):
        """
        应用主题到指定组件及其子组件
        
        Args:
            widget: 目标组件
            theme_name: 主题名称 ('light' 或 'dark')
        """
        if theme_name not in self.THEMES:
            theme_name = 'light'
        
        stylesheet = self.THEMES[theme_name]['stylesheet']
        widget.setStyleSheet(stylesheet)
        
        # 递归应用到所有子组件
        for child in widget.findChildren(QWidget):
            child.setStyleSheet(stylesheet)
    
    def get_available_themes(self):
        """获取可用主题列表"""
        return list(self.THEMES.keys())


def apply_theme_to_app(app: QApplication, theme_name: str = 'light'):
    """
    应用主题到整个应用程序
    
    Args:
        app: QApplication实例
        theme_name: 主题名称
    """
    theme_manager = ThemeManager()
    # 对于应用程序级别，我们只需要设置全局样式表
    if theme_name in theme_manager.THEMES:
        app.setStyleSheet(theme_manager.THEMES[theme_name]['stylesheet'])