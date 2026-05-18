"""
日记管理系统 - PyQt版本
最终主程序入口 - 使用本地数据库
"""
import sys
import os
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QMessageBox

# 添加项目根目录到Python路径，以便正确导入模块
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from views.main_window import MainWindow
from utils.theme_utils import apply_theme_to_app
from models.enhanced_database import EnhancedDatabaseManager
from config.config import get_db_path
from config.logging_config import setup_logging


def main():
    """主函数 - 使用本地数据库"""
    # 初始化统一日志配置
    setup_logging()

    # 使用配置管理器获取数据库路径
    db_path = get_db_path()
    
    # 检查数据库是否存在
    if not os.path.exists(db_path):
        print(f"错误: 数据库文件不存在: {db_path}")
        print("请确保数据库文件存在于该路径中")
        # 尝试创建数据库目录
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        print(f"已创建数据库目录: {os.path.dirname(db_path)}")
    else:
        print(f"正在使用数据库: {db_path}")
    
    # 验证数据库
    db_manager = EnhancedDatabaseManager(db_path)
    stats = db_manager.get_statistics()
    print(f"数据库统计: {stats['total']} 篇日记")
    db_manager.close()
    
    app = QApplication(sys.argv)
    
    # 设置应用程序属性
    app.setApplicationName("Diary Management System - PyQt Version")
    app.setApplicationVersion("1.0")
    app.setOrganizationName("Assistant")
    
    # 创建并显示主窗口，使用配置的数据库路径
    window = MainWindow(db_path=db_path)
    window.show()
    
    # 启动应用程序
    sys.exit(app.exec())


if __name__ == "__main__":
    main()