from pathlib import Path

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


def test_sync_menu_entries_are_available(qapp, tmp_path, monkeypatch):
    # 隔离真实同步状态：测试不能读到用户机器上已建立的映射
    monkeypatch.setenv("DIARY_SYNC_STATE_PATH", str(tmp_path / "sync-state.json"))
    monkeypatch.setenv("DIARY_CONTENT_SYNC_ENABLED", "0")
    window = MainWindow(db_path=str(tmp_path / "desktop.db"))
    actions = [action.text() for menu in window.menuBar().findChildren(type(window.menuBar().actions()[0].menu()))
               for action in menu.actions()]
    assert any("自动同步" in action for action in actions)
    assert any("同步" in action for action in actions)
    window.close()


def test_sync_status_page_requires_confirmed_mapping(qapp):
    dialog = SyncReviewDialog()
    dialog.set_status({"mapped": False, "entries": 0, "cursor": 0, "conflicts": []})
    assert not dialog.scan_button.isEnabled()
    assert not dialog.sync_button.isEnabled()
    assert not dialog.views_button.isEnabled()

    dialog.set_status({"mapped": True, "entries": 303, "cursor": 300, "conflicts": []})
    assert dialog.scan_button.isEnabled()
    assert dialog.sync_button.isEnabled()
    assert dialog.views_button.isEnabled()
    dialog.close()


def test_sync_status_page_only_maps_on_complete_match(qapp):
    dialog = SyncReviewDialog()
    dialog.set_status({"mapped": False, "entries": 0, "cursor": 0, "conflicts": []})
    dialog.set_precheck({"local": 2, "matched": 1, "local_only": 1,
                         "remote_only": 0, "ambiguous": 0, "mapped": False})
    assert not dialog.map_button.isEnabled()

    dialog.set_precheck({"local": 2, "matched": 2, "local_only": 0,
                         "remote_only": 0, "ambiguous": 0, "mapped": False})
    assert dialog.map_button.isEnabled()

    # 已建立映射后不再提供手工配对入口
    dialog.set_status({"mapped": True, "entries": 2, "cursor": 0, "conflicts": []})
    assert not dialog.map_button.isEnabled()
    dialog.close()


def test_sync_status_page_lists_conflicts(qapp):
    dialog = SyncReviewDialog()
    dialog.set_status({
        "mapped": True, "entries": 1, "cursor": 5,
        "conflicts": [{
            "id": "c1", "kind": "local_overwritten", "at": "2026-09-29T00:00:00Z", "local_id": 7,
            "local_payload": {"content": "本地旧稿"},
            "remote_payload": {"content": "服务器新稿"},
            "note": "服务器较新",
        }],
    })
    assert dialog.conflict_list.count() == 1
    assert "本地被服务器版本覆盖" in dialog.conflict_list.item(0).text()
    assert "待处理冲突 1 条" in dialog.conflict_hint.text()
    dialog.close()


def test_sync_status_page_without_conflicts_hides_the_list(qapp):
    dialog = SyncReviewDialog()
    dialog.set_status({"mapped": True, "entries": 3, "cursor": 9, "conflicts": [],
                       "last_sync_stats": {"pushed": 2}})
    assert dialog.conflict_list.count() == 0
    assert "pushed 2" in dialog.summary.text()
    dialog.close()
