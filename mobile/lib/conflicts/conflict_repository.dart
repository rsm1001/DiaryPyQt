import 'dart:convert';

import 'package:sqflite/sqflite.dart';

import '../models/diary.dart';
import 'diary_conflict.dart';

class ConflictRepository {
  const ConflictRepository(this.db);
  final Database db;

  static Future<void> createSchema(DatabaseExecutor executor) async {
    await executor.execute('CREATE TABLE IF NOT EXISTS diary_conflicts ('
        'diary_id TEXT PRIMARY KEY, action TEXT NOT NULL, remote_json TEXT)');
  }

  Future<void> record(String diaryId, String action, Diary? remote) async {
    await db.insert(
        'diary_conflicts',
        {
          'diary_id': diaryId,
          'action': action,
          'remote_json': remote == null ? null : jsonEncode(remote.toJson()),
        },
        conflictAlgorithm: ConflictAlgorithm.replace);
  }

  Future<bool> contains(String diaryId) async {
    final rows = await db.query('diary_conflicts',
        columns: ['diary_id'],
        where: 'diary_id = ?',
        whereArgs: [diaryId],
        limit: 1);
    return rows.isNotEmpty;
  }

  Future<List<DiaryConflict>> list() async {
    final records = await db.query('diary_conflicts', orderBy: 'diary_id ASC');
    final conflicts = <DiaryConflict>[];
    for (final record in records) {
      final id = record['diary_id'] as String;
      final diaries = await db.query('diaries',
          columns: ['json'], where: 'id = ?', whereArgs: [id], limit: 1);
      final pending = await db.query('outbox',
          columns: ['action'],
          where: 'entity_id = ? AND action != ?',
          whereArgs: [id, 'view'],
          limit: 1);
      if (diaries.isEmpty || pending.isEmpty) continue;
      final raw = record['remote_json'] as String?;
      conflicts.add(DiaryConflict(
        diaryId: id,
        action: pending.first['action'] as String,
        local: Diary.fromJson(jsonDecode(diaries.first['json'] as String)),
        remote: raw == null ? null : Diary.fromJson(jsonDecode(raw)),
      ));
    }
    return conflicts;
  }

  Future<void> resolve(DiaryConflict expected, Diary remote,
      {required bool keepLocal}) async {
    await db.transaction((transaction) async {
      final records = await transaction.query('diary_conflicts',
          where: 'diary_id = ?', whereArgs: [expected.diaryId], limit: 1);
      final pending = await transaction.query('outbox',
          where: 'entity_id = ? AND action != ?',
          whereArgs: [expected.diaryId, 'view'],
          limit: 1);
      final cached = await transaction.query('diaries',
          where: 'id = ?', whereArgs: [expected.diaryId], limit: 1);
      if (records.isEmpty ||
          pending.isEmpty ||
          cached.isEmpty ||
          expected.remote == null ||
          remote.id != expected.diaryId ||
          remote.version != expected.remote!.version ||
          remote.contentHash != expected.remote!.contentHash ||
          (remote.deletedAt != null &&
              keepLocal &&
              expected.action != 'restore') ||
          (remote.deletedAt == null &&
              keepLocal &&
              expected.action == 'restore')) {
        throw StateError('服务器版本已变化，需重新核对冲突');
      }
      final local = Diary.fromJson(jsonDecode(cached.single['json'] as String));
      if (local.contentHash != expected.local.contentHash ||
          local.content != expected.local.content ||
          local.updatedAt != expected.local.updatedAt ||
          local.tags.join('\u0000') != expected.local.tags.join('\u0000') ||
          pending.single['action'] != expected.action) {
        throw StateError('本地内容已变化，需重新核对冲突');
      }
      final next = keepLocal
          ? rebaseLocalDiary(local, remote)
          : preserveLocalViews(local, remote);
      await transaction.update(
          'diaries',
          {
            'json': jsonEncode(next.toJson()),
            'content_hash': next.contentHash,
            'version': next.version,
          },
          where: 'id = ?',
          whereArgs: [next.id]);
      if (keepLocal) {
        await transaction.update('outbox', {'base_version': remote.version},
            where: 'id = ?', whereArgs: [pending.single['id']]);
      } else {
        await transaction.delete('outbox',
            where: 'id = ?', whereArgs: [pending.single['id']]);
      }
      await transaction.delete('diary_conflicts',
          where: 'diary_id = ?', whereArgs: [expected.diaryId]);
    });
  }
}
