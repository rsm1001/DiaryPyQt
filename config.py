"""
配置管理
"""
import os


# 数据库配置
DB_PATH = os.environ.get('DIARY_DB_PATH', 'DiaryServer/diary_data/diary.db')

# 应用程序配置
APP_NAME = "Diary Management System - PyQt Version"
APP_VERSION = "1.0"
DEFAULT_THEME = "light"  # 默认主题

# 界面配置
MAIN_WINDOW_SIZE = (1000, 700)  # 主窗口默认尺寸
TABLE_ROW_HEIGHT = 30  # 表格行高

# 限制配置
RANDOM_LIMIT = 25  # 随机查看和删除操作的限制数量
MOST_VIEWED_LIMIT = 25
SEARCH_RESULT_LIMIT = 18  # 搜索结果限制

# 数据库配置
ENABLE_WAL = True
CACHE_SIZE = 10000

# 文件路径配置
DEFAULT_EXPORT_PATH = "./exports"
DEFAULT_IMPORT_PATH = "./imports"