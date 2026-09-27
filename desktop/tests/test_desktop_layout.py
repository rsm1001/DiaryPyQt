from pathlib import Path
from PyQt6.QtWidgets import QApplication

from desktop import main as desktop_main
from models.config.db_config import DatabaseConfig
from views.main_window import MainWindow
from views.sync_review import SyncReviewDialog


def test_desktop_entry_reuses_original_database_path():
    repository_root = Path(desktop_main.__file__).resolve().parents[1]
    expected = repository_root / "data" / "diary.db"
    assert Path(DatabaseConfig()._get_default_db_path()).resolve() == expected.resolve()
    assert (repository_root / "main.py").is_file()
    assert (repository_root / "desktop" / "views" / "main_window.py").is_file()
    assert (repository_root / "desktop" / "tests" / "unit").is_dir()


def test_sync_review_action_is_available(qapp, tmp_path):
    window = MainWindow(db_path=str(tmp_path / "desktop.db"))
    actions = [action.text() for menu in window.menuBar().findChildren(type(window.menuBar().actions()[0].menu()))
               for action in menu.actions()]
    assert any("同步审核" in action for action in actions)
    window.close()


def test_view_sync_requires_confirmed_mapping(qapp):
    dialog = SyncReviewDialog()
    dialog.set_result({"local": 2, "matched": 1, "local_only": 1,
                       "remote_only": 0, "ambiguous": 0, "mapped": False})
    assert not dialog.views_button.isEnabled()
    assert not dialog.map_button.isEnabled()
    dialog.set_result({"local": 2, "matched": 2, "local_only": 0,
                       "remote_only": 0, "ambiguous": 0, "mapped": True})
    assert dialog.views_button.isEnabled()
    dialog.close()
