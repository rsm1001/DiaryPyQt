"""同步测试共用夹具：每个用例一个独立临时数据库。"""
import pytest

from models.enhanced_database import EnhancedDatabaseManager


@pytest.fixture
def local_db(tmp_path):
    manager = EnhancedDatabaseManager(str(tmp_path / "diary.db"))
    yield manager
    manager.close()
