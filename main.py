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
from utils.themes import apply_theme_to_app
from models.enhanced_database import EnhancedDatabaseManager


def main():
    """主函数 - 使用本地数据库"""
    # 使用项目目录中的数据文件夹
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "diary.db")
    
    # 检查数据库是否存在
    if not os.path.exists(db_path):
        print(f"错误: 数据库文件不存在: {db_path}")
        print("请确保数据库文件存在于 data/ 目录中")
        return
    else:
        print(f"正在使用本地数据库: {db_path}")
    
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
    
    # 创建并显示主窗口，使用本地数据库
    window = MainWindow(db_path=db_path)
    window.show()
    
    # 启动应用程序
    sys.exit(app.exec())


if __name__ == "__main__":
    main()