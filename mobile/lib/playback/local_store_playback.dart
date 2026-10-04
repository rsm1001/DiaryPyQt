import 'dart:convert';

import 'package:sqflite/sqflite.dart';

import '../playback/playback_record.dart';
import '../services/local_store.dart';

extension LocalStorePlayback on LocalStore {
  Future<String> getDeviceId() async {
    final rows = await (await database).query('sync_state',
        columns: ['value'],
        where: 'key = ?',
        whereArgs: ['device_id'],
        limit: 1);
    if (rows.isNotEmpty) return rows.single['value'] as String;
    final value = 'device-${DateTime.now().microsecondsSinceEpoch}';
    await (await database).insert(
        'sync_state', {'key': 'device_id', 'value': value},
        conflictAlgorithm: ConflictAlgorithm.ignore);
    return value;
  }

  Future<PlaybackRecord?> getPlayback(String diaryId, String voiceId) async {
    final rows = await (await database).query('playback_records',
        where: 'diary_id = ? AND voice_id = ?',
        whereArgs: [diaryId, voiceId],
        limit: 1);
    return rows.isEmpty ? null : PlaybackRecord.fromJson(rows.single);
  }

  Future<List<PlaybackRecord>> getPlaybacks() async {
    final rows = await (await database)
        .query('playback_records', orderBy: 'updated_at DESC');
    return rows.map(PlaybackRecord.fromJson).toList(growable: false);
  }

  Future<void> savePlayback(PlaybackRecord record, {bool queue = true}) async {
    final db = await database;
    await db.transaction((transaction) async {
      await transaction.insert('playback_records', record.toJson(),
          conflictAlgorithm: ConflictAlgorithm.replace);
      if (queue) {
        final entityId = 'playback:${record.diaryId}:${record.voiceId}';
        await transaction.delete('outbox',
            where: 'entity_id = ? AND action = ?',
            whereArgs: [entityId, 'playback']);
        await transaction.insert(
            'outbox',
            {
              'entity_id': entityId,
              'action': 'playback',
              'base_version': null,
              'json': jsonEncode(record.toJson()),
            },
            conflictAlgorithm: ConflictAlgorithm.replace);
      }
    });
  }
}
