"""修复回归测试：查看次数存在性校验、备份恢复与完整性检查、健康状态。"""


def test_invalid_view_count_is_noop(initialized_temp_db):
    assert initialized_temp_db.increment_view_count(999999) is None
    row = initialized_temp_db._execute(
        "SELECT COUNT(*) AS count FROM view_log", fetch='one'
    )
    assert row['count'] == 0


def test_backup_restore_and_integrity(initialized_temp_db, tmp_path):
    initialized_temp_db.add_diary('backup-content')
    snapshot = str(tmp_path / 'diary.snapshot')
    assert initialized_temp_db.backup_database(snapshot) is True
    initialized_temp_db.add_diary('temporary-content')
    assert initialized_temp_db.restore_database(snapshot) is True
    contents = [item['content'] for item in initialized_temp_db.get_all_diaries()]
    assert contents == ['backup-content']
    assert initialized_temp_db.validate_database_integrity() is True


def test_database_health_has_recovery_state(initialized_temp_db):
    health = initialized_temp_db.get_database_health()
    assert health['integrity_ok'] is True
    assert health['recovery_ok'] is True
    assert health['pending_main'] == 0
    assert health['pending_trash'] == 0
