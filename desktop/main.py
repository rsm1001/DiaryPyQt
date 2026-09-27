"""PyQt 日记管理程序入口，兼容从项目根目录或 desktop 目录运行。"""
import logging
import sys
from pathlib import Path
from uuid import uuid4

from PyQt6.QtWidgets import QApplication

project_root = Path(__file__).resolve().parents[1]
desktop_root = Path(__file__).resolve().parent
for module_root in (project_root, desktop_root):
    if str(module_root) not in sys.path:
        sys.path.insert(0, str(module_root))

from config.config import get_db_path
from config.logging_config import setup_logging
from i18n import init_i18n
from models.enhanced_database import EnhancedDatabaseManager
from views.main_window import MainWindow

logger = logging.getLogger(__name__)


def main() -> int:
    """启动原有 PyQt 界面并继续使用原有本地日记数据库。"""
    setup_logging()
    request_id = str(uuid4())
    language = init_i18n()
    db_path = get_db_path()
    if not Path(db_path).is_file():
        logger.warning("本地日记库不存在，将创建新数据库", extra={"request_id": request_id, "db_path": db_path})
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    manager = EnhancedDatabaseManager(db_path)
    try:
        stats = manager.get_statistics()
        logger.info("桌面日记库加载完成", extra={"request_id": request_id,
                                         "language": language, "total": stats["total"]})
    finally:
        manager.close()

    app = QApplication(sys.argv)
    app.setApplicationName("Diary Management System - PyQt Version")
    app.setApplicationVersion("1.0")
    app.setOrganizationName("Assistant")
    window = MainWindow(db_path=db_path)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
