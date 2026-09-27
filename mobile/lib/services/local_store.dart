import 'dart:convert';
import 'dart:io';

import 'package:path/path.dart' as path;
import 'package:path_provider/path_provider.dart';
import 'package:sqflite/sqflite.dart';

import '../models/audio_asset.dart';
import '../models/diary.dart';
import '../models/diary_view_result.dart';
import 'random_selector.dart';

class LocalStore {
  Database? _database;

  Future<Database> get database async {
    if (_database != null) return _database!;
    final directory = await getApplicationDocumentsDirectory();
    _database = await openDatabase(
      path.join(directory.path, 'diary_mobile.db'),
      version: 1,
      onCreate: (db, _) async {
        await db.execute(
            'CREATE TABLE diaries (id TEXT PRIMARY KEY, json TEXT NOT NULL, version INTEGER NOT NULL, content_hash TEXT NOT NULL)');
        await db.execute(
            'CREATE TABLE audio_cache (diary_id TEXT NOT NULL, voice_id TEXT NOT NULL, content_hash TEXT NOT NULL, file_hash TEXT NOT NULL, duration_ms INTEGER NOT NULL, file_path TEXT NOT NULL, json TEXT NOT NULL, PRIMARY KEY (diary_id, voice_id))');
        await db.execute(
            'CREATE TABLE sync_state (key TEXT PRIMARY KEY, value TEXT NOT NULL)');
        await db.execute(
            'CREATE TABLE outbox (id INTEGER PRIMARY KEY AUTOINCREMENT, entity_id TEXT NOT NULL, action TEXT NOT NULL, base_version INTEGER, json TEXT NOT NULL)');
      },
    );
    return _database!;
  }

  Future<List<Diary>> getDiaries() async {
    final rows = await (await database).query('diaries', orderBy: 'json DESC');
    return rows
        .map((row) => Diary.fromJson(_decode(row['json']! as String)))
        .where((diary) => diary.deletedAt == null)
        .toList(growable: false);
  }

  Future<Diary?> getDiary(String id) async {
    final rows = await (await database).query(
      'diaries',
      where: 'id = ?',
      whereArgs: [id],
      limit: 1,
    );
    if (rows.isEmpty) return null;
    return Diary.fromJson(_decode(rows.first['json']! as String));
  }

  Future<void> saveDiary(Diary diary) async {
    await (await database).insert(
      'diaries',
      {
        'id': diary.id,
        'json': _encode(diary.toJson()),
        'version': diary.version,
        'content_hash': diary.contentHash,
      },
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  Future<void> replaceLocalId(String temporaryId, Diary created, int outboxId) async {
    final db = await database;
    await db.transaction((transaction) async {
      final rows = await transaction.query('diaries',
          where: 'id = ?', whereArgs: [temporaryId], limit: 1);
      if (rows.isEmpty) throw StateError('待同步的本地日记不存在');
      final local = Diary.fromJson(_decode(rows.first['json'] as String));
      final merged = created.copyWith(
          viewCount: local.viewCount, lastViewedAt: local.lastViewedAt);
      await transaction.delete('diaries',
          where: 'id = ?', whereArgs: [temporaryId]);
      await transaction.insert('diaries', {
        'id': created.id,
        'json': _encode(merged.toJson()),
        'version': created.version,
        'content_hash': created.contentHash,
      }, conflictAlgorithm: ConflictAlgorithm.replace);
      await transaction.update('outbox', {'entity_id': created.id},
          where: 'entity_id = ?', whereArgs: [temporaryId]);
      await transaction.delete('outbox',
          where: 'id = ? AND action = ?', whereArgs: [outboxId, 'create']);
    });
  }

  Future<void> replaceDiaries(List<Diary> diaries) async {
    final db = await database;
    await db.transaction((transaction) async {
      final pending = await transaction.query('outbox', columns: ['entity_id']);
      final pendingIds =
          pending.map((row) => row['entity_id'] as String).toSet();
      final cached = await transaction.query('diaries', columns: ['id']);
      for (final row in cached) {
        if (!pendingIds.contains(row['id'])) {
          await transaction
              .delete('diaries', where: 'id = ?', whereArgs: [row['id']]);
        }
      }
      for (final diary in diaries) {
        if (pendingIds.contains(diary.id)) continue;
        await transaction.insert(
          'diaries',
          {
            'id': diary.id,
            'json': _encode(diary.toJson()),
            'version': diary.version,
            'content_hash': diary.contentHash,
          },
          conflictAlgorithm: ConflictAlgorithm.replace,
        );
      }
    });
  }

  Future<List<Map<String, dynamic>>> getOutbox() async {
    final rows = await (await database).query('outbox', orderBy: 'id ASC');
    return rows
        .map((row) => Map<String, dynamic>.from(row))
        .toList(growable: false);
  }

  Future<void> enqueueMutation({
    required String entityId,
    required String action,
    required int? baseVersion,
    required Map<String, dynamic> payload,
  }) async {
    final db = await database;
    await db.transaction((transaction) async {
      final existing = await transaction.query(
        'outbox',
        where: 'entity_id = ? AND action != ?',
        whereArgs: [entityId, 'view'],
        orderBy: 'id ASC',
        limit: 1,
      );
      if (existing.isNotEmpty) {
        final row = existing.first;
        final previousAction = row['action'] as String;
        if (action == 'delete' && previousAction == 'create') {
          await transaction
              .delete('outbox', where: 'entity_id = ?', whereArgs: [entityId]);
          await transaction
              .delete('diaries', where: 'id = ?', whereArgs: [entityId]);
          return;
        }
        var nextAction = action;
        var nextPayload = payload;
        if (previousAction == 'create' && action == 'update') {
          nextAction = 'create';
          final previousPayload = _decode(row['json']! as String);
          nextPayload = {...previousPayload, ...payload};
        }
        await transaction.update(
          'outbox',
          {
            'action': nextAction,
            'base_version': row['base_version'] ?? baseVersion,
            'json': _encode(nextPayload),
          },
          where: 'id = ?',
          whereArgs: [row['id']],
        );
        return;
      }
      await transaction.insert('outbox', {
        'entity_id': entityId,
        'action': action,
        'base_version': baseVersion,
        'json': _encode(payload),
      });
    });
  }

  Future<int> recordViewLocally(
      String diaryId, String eventId, String viewedAt) async {
    final db = await database;
    return db.transaction((transaction) async {
      final rows = await transaction.query('diaries',
          where: 'id = ?', whereArgs: [diaryId], limit: 1);
      if (rows.isEmpty) throw StateError('本地日记不存在，无法记录查看');
      final diary = Diary.fromJson(_decode(rows.first['json'] as String));
      final id = await transaction.insert('outbox', {
        'entity_id': diaryId,
        'action': 'view',
        'base_version': diary.version,
        'json': _encode({'event_id': eventId, 'viewed_at': viewedAt}),
      });
      await transaction.update(
        'diaries',
        {'json': _encode(diary.copyWith(
            viewCount: diary.viewCount + 1, lastViewedAt: viewedAt).toJson())},
        where: 'id = ?',
        whereArgs: [diaryId],
      );
      return id;
    });
  }

  Future<void> ensureViewPayload(int id, String eventId, String viewedAt) async {
    final db = await database;
    await db.update('outbox',
        {'json': _encode({'event_id': eventId, 'viewed_at': viewedAt})},
        where: 'id = ? AND action = ? AND json = ?',
        whereArgs: [id, 'view', _encode(const {})]);
  }

  Future<void> confirmView(int id, String diaryId, DiaryViewResult result) async {
    final db = await database;
    await db.transaction((transaction) async {
      final rows = await transaction.query('diaries',
          where: 'id = ?', whereArgs: [diaryId], limit: 1);
      if (rows.isNotEmpty) {
        final diary = Diary.fromJson(_decode(rows.first['json'] as String));
        final last = diary.lastViewedAt;
        final latest = last != null &&
                DateTime.parse(last).isAfter(DateTime.parse(result.viewedAt))
            ? last
            : result.viewedAt;
        await transaction.update('diaries', {
          'json': _encode(diary.copyWith(
              viewCount: diary.viewCount > result.viewCount
                  ? diary.viewCount
                  : result.viewCount,
              lastViewedAt: latest).toJson()),
        }, where: 'id = ?', whereArgs: [diaryId]);
      }
      await transaction.delete('outbox', where: 'id = ?', whereArgs: [id]);
    });
  }

  Future<void> removeDiary(String id) async {
    await (await database).delete('diaries', where: 'id = ?', whereArgs: [id]);
  }

  Future<void> acknowledgeMutation(int id) async {
    await (await database).delete('outbox', where: 'id = ?', whereArgs: [id]);
  }

  Future<AudioAsset?> getAudio(
      String diaryId, String voiceId, String contentHash) async {
    final rows = await (await database).query('audio_cache',
        where: voiceId.isEmpty
            ? 'diary_id = ? AND content_hash = ?'
            : 'diary_id = ? AND voice_id = ? AND content_hash = ?',
        whereArgs: voiceId.isEmpty
            ? [diaryId, contentHash]
            : [diaryId, voiceId, contentHash],
        orderBy: 'rowid DESC',
        limit: 1);
    if (rows.isEmpty) return null;
    final row = rows.first;
    final filePath = row['file_path']! as String;
    if (!await File(filePath).exists()) return null;
    return AudioAsset.fromJson(_decode(row['json']! as String), '')
        .copyWith(localPath: filePath);
  }

  Future<void> saveAudio(AudioAsset asset, String filePath) async {
    final db = await database;
    await db.insert(
        'audio_cache',
        {
          'diary_id': asset.diaryId,
          'voice_id': asset.voiceId,
          'content_hash': asset.contentHash,
          'file_hash': asset.fileHash,
          'duration_ms': asset.durationMs,
          'file_path': filePath,
          'json': _encode({
            'id': asset.id,
            'diary_id': asset.diaryId,
            'voice_id': asset.voiceId,
            'content_hash': asset.contentHash,
            'file_hash': asset.fileHash,
            'duration_ms': asset.durationMs,
            'download_url': asset.downloadUrl
          }),
        },
        conflictAlgorithm: ConflictAlgorithm.replace);
  }

  Future<String> audioDirectory() async {
    final directory = await getApplicationDocumentsDirectory();
    final audioDirectory = Directory(path.join(directory.path, 'audio'));
    await audioDirectory.create(recursive: true);
    return audioDirectory.path;
  }

  Future<int> getCursor() async {
    final rows = await (await database)
        .query('sync_state', where: 'key = ?', whereArgs: ['cursor'], limit: 1);
    return rows.isEmpty ? 0 : int.tryParse(rows.first['value']! as String) ?? 0;
  }

  Future<void> saveCursor(int cursor) async {
    await (await database).insert(
        'sync_state', {'key': 'cursor', 'value': '$cursor'},
        conflictAlgorithm: ConflictAlgorithm.replace);
  }

  Future<Map<String, RandomUsage>> getRandomUsage() async {
    final rows = await (await database).query(
      'sync_state',
      where: 'key = ?',
      whereArgs: ['random_usage'],
      limit: 1,
    );
    if (rows.isEmpty) return const {};
    final raw =
        Map<String, dynamic>.from(_decode(rows.first['value']! as String));
    return {
      for (final entry in raw.entries)
        entry.key:
            RandomUsage.fromJson(Map<String, dynamic>.from(entry.value as Map)),
    };
  }

  Future<void> recordRandomSelection(String diaryId, {DateTime? now}) async {
    final usage = withRandomSelectionRecorded(
        await getRandomUsage(), diaryId, now ?? DateTime.now());
    await (await database).insert(
      'sync_state',
      {
        'key': 'random_usage',
        'value': _encode({
          for (final entry in usage.entries) entry.key: entry.value.toJson(),
        }),
      },
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  Future<String?> getServerUrl() async {
    final rows = await (await database).query('sync_state',
        where: 'key = ?', whereArgs: ['server_url'], limit: 1);
    return rows.isEmpty ? null : rows.first['value']! as String;
  }

  Future<void> saveServerUrl(String url) async {
    await (await database).insert(
        'sync_state', {'key': 'server_url', 'value': url},
        conflictAlgorithm: ConflictAlgorithm.replace);
  }

  Future<void> close() async => _database?.close();

  static Map<String, dynamic> _decode(String value) =>
      Map<String, dynamic>.from(jsonDecode(value) as Map);
  static String _encode(Map<String, dynamic> value) => jsonEncode(value);
}
