"""
数据库配置管理器
集中管理数据库相关的配置，避免硬编码路径
"""
import os
from pathlib import Path


class DatabaseConfig:
    """数据库配置类"""
    
    def __init__(self):
        # 从环境变量获取数据库路径，如果没有则使用默认路径
        self.db_path = os.environ.get(
            'DIARY_DB_PATH', 
            self._get_default_db_path()
        )
    
    def _get_default_db_path(self) -> str:
        """获取默认数据库路径"""
        # 获取项目根目录（向上三级到达项目根目录）
        project_root = Path(__file__).parent.parent.parent
        # 使用项目根目录下的data文件夹
        default_path = project_root / "data" / "diary.db"
        # 确保目录存在
        default_path.parent.mkdir(parents=True, exist_ok=True)
        return str(default_path)
    
    def get_db_path(self) -> str:
        """获取数据库路径"""
        return self.db_path
    
    def set_db_path(self, path: str):
        """设置数据库路径"""
        self.db_path = path


# 全局配置实例
_db_config = None


def get_db_config() -> DatabaseConfig:
    """获取数据库配置实例"""
    global _db_config
    if _db_config is None:
        _db_config = DatabaseConfig()
    return _db_config