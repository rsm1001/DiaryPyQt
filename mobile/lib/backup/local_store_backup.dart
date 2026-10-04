import '../services/local_store.dart';
import 'local_backup.dart';

extension LocalStoreBackup on LocalStore {
  Future<bool> checkLocalIntegrity() async {
    final result = await (await database).rawQuery('PRAGMA integrity_check');
    final foreignKeys =
        await (await database).rawQuery('PRAGMA foreign_key_check');
    return result.isNotEmpty &&
        result.first.values.first == 'ok' &&
        foreignKeys.isEmpty;
  }

  Future<LocalBackup> exportLocalBackup() async =>
      LocalBackupRepository(await database).exportBackup();

  Future<bool> hasPendingLocalChanges() async {
    final db = await database;
    final outbox = await db.query('outbox', columns: ['id'], limit: 1);
    final conflicts =
        await db.query('diary_conflicts', columns: ['diary_id'], limit: 1);
    return outbox.isNotEmpty || conflicts.isNotEmpty;
  }

  Future<Map<String, int>> restoreLocalBackup(LocalBackup backup) async =>
      LocalBackupRepository(await database).restore(backup);
}
