import 'dart:convert';
import 'dart:io';

import 'package:path/path.dart' as path;
import 'package:path_provider/path_provider.dart';
import 'package:sqflite/sqflite.dart';

import '../models/audio_asset.dart';
import '../models/diary.dart';
import '../models/diary_view_result.dart';
import '../statistics/device_view_repository.dart';
import '../voice/voice_cache_repository.dart';
import 'random_selector.dart';

class LocalStore {
  LocalStore();

  LocalStore.withDatabase(Database database) : _database = database;

  Database? _database;

  Future<Database> get database async {
    if (_database != null) return _database!;
    final directory = await getApplicationDocumentsDirectory();
    _database = await openDatabase(
      path.join(directory.path, 'diary_mobile.db'),
      version: 3,
      onUpgrade: upgradeSchema,
      onCreate: createSchema,
    );
    return _database!;
  }

  static Future<void> upgradeSchema(
      Database db, int oldVersion, int newVersion) async {
    if (oldVersion < 2) await DeviceViewRepository.createSchema(db);
    if (oldVersion < 3) await VoiceCacheRepository.upgradeSchema(db);
  }

  static Future<void> createSchema(Database db, int version) async {
    await db.execute(
        'CREATE TABLE diaries (id TEXT PRIMARY KEY, json TEXT NOT NULL, version INTEGER NOT NULL, content_hash TEXT NOT NULL)');
    await VoiceCacheRepository.createSchema(db);
    await db.execute(
        'CREATE TABLE sync_state (key TEXT PRIMARY KEY, value TEXT NOT NULL)');
    await db.execute(
        'CREATE TABLE outbox (id INTEGER PRIMARY KEY AUTOINCREMENT, entity_id TEXT NOT NULL, action TEXT NOT NULL, base_version INTEGER, json TEXT NOT NULL)');
    await DeviceViewRepository.createSchema(db);
  }

  Future<List<Diary>> getDiaries() async {
    final rows = await (await database).query('diaries', orderBy: 'json DESC');
    return rows
        .map((row) => Diary.fromJson(_decode(row['json']! as String)))
        .where((diary) => diary.deletedAt == null)
        .toList(growable: false);
  }

  Future<DeviceViewHistory> getDeviceViewHistory(DateTime month) async =>
      DeviceViewRepository(await database).month(month);

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

  Future<int> importDiaries(List<Diary> imports) async {
    final db = await database;
    return db.transaction((transaction) async {
      final rows = await transaction.query('diaries', columns: ['json']);
      final keys = rows.map((row) {
        final diary = Diary.fromJson(_decode(row['json'] as String));
        return jsonEncode([diary.date.trim(), diary.content.trim()]);
      }).toSet();
      var imported = 0;
      for (final diary in imports) {
        if (!keys.add(jsonEncode([diary.date.trim(), diary.content.trim()]))) {
          continue;
        }
        await transaction.insert('diaries', {
          'id': diary.id,
          'json': _encode(diary.toJson()),
          'version': diary.version,
          'content_hash': diary.contentHash,
        });
        await transaction.insert('outbox', {
          'entity_id': diary.id,
          'action': 'create',
          'base_version': null,
          'json': _encode({
            'date': diary.date,
            'content': diary.content,
            'tags': diary.tags,
          }),
        });
        imported++;
      }
      return imported;
    });
  }

  Future<void> saveRemoteDiary(Diary diary) async {
    final db = await database;
    await db.transaction((transaction) async {
      var updated = diary;
      final pendingViews = await transaction.query('outbox',
          columns: ['id'],
          where: 'entity_id = ? AND action = ?',
          whereArgs: [diary.id, 'view'],
          limit: 1);
      if (pendingViews.isNotEmpty) {
        final rows = await transaction.query('diaries',
            where: 'id = ?', whereArgs: [diary.id], limit: 1);
        if (rows.isNotEmpty) {
          final local = Diary.fromJson(_decode(rows.first['json'] as String));
          final localTime = DateTime.tryParse(local.lastViewedAt ?? '');
          final remoteTime = DateTime.tryParse(diary.lastViewedAt ?? '');
          final lastViewedAt = localTime != null &&
                  (remoteTime == null || localTime.isAfter(remoteTime))
              ? local.lastViewedAt
              : diary.lastViewedAt;
          updated = diary.copyWith(
              viewCount: local.viewCount > diary.viewCount
                  ? local.viewCount
                  : diary.viewCount,
              lastViewedAt: lastViewedAt);
        }
      }
      await transaction.insert(
          'diaries',
          {
            'id': updated.id,
            'json': _encode(updated.toJson()),
            'version': updated.version,
            'content_hash': updated.contentHash,
          },
          conflictAlgorithm: ConflictAlgorithm.replace);
    });
  }

  Future<void> replaceLocalId(
      String temporaryId, Diary created, int outboxId) async {
    final db = await database;
    await db.transaction((transaction) async {
      final rows = await transaction.query('diaries',
          where: 'id = ?', whereArgs: [temporaryId], limit: 1);
      if (rows.isEmpty) throw StateError('待同步的本地日记不存在');
      final local = Diary.fromJson(_decode(rows.first['json'] as String));
      final merged = created.copyWith(
          viewCount: local.viewCount, lastViewedAt: local.lastViewedAt);
      await transaction
          .delete('diaries', where: 'id = ?', whereArgs: [temporaryId]);
      await transaction.insert(
          'diaries',
          {
            'id': created.id,
            'json': _encode(merged.toJson()),
            'version': created.version,
            'content_hash': created.contentHash,
          },
          conflictAlgorithm: ConflictAlgorithm.replace);
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
      await DeviceViewRepository.record(transaction, eventId, viewedAt);
      final id = await transaction.insert('outbox', {
        'entity_id': diaryId,
        'action': 'view',
        'base_version': diary.version,
        'json': _encode({'event_id': eventId, 'viewed_at': viewedAt}),
      });
      await transaction.update(
        'diaries',
        {
          'json': _encode(diary
              .copyWith(viewCount: diary.viewCount + 1, lastViewedAt: viewedAt)
              .toJson())
        },
        where: 'id = ?',
        whereArgs: [diaryId],
      );
      return id;
    });
  }

  Future<void> ensureViewPayload(
      int id, String eventId, String viewedAt) async {
    final db = await database;
    await db.update(
        'outbox',
        {
          'json': _encode({'event_id': eventId, 'viewed_at': viewedAt})
        },
        where: 'id = ? AND action = ? AND json = ?',
        whereArgs: [id, 'view', _encode(const {})]);
  }

  Future<void> confirmView(
      int id, String diaryId, DiaryViewResult result) async {
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
        await transaction.update(
            'diaries',
            {
              'json': _encode(diary
                  .copyWith(
                      viewCount: diary.viewCount > result.viewCount
                          ? diary.viewCount
                          : result.viewCount,
                      lastViewedAt: latest)
                  .toJson()),
            },
            where: 'id = ?',
            whereArgs: [diaryId]);
      }
      final pending = await transaction.query('outbox',
          columns: ['json'],
          where: 'id = ? AND action = ?',
          whereArgs: [id, 'view'],
          limit: 1);
      if (pending.isNotEmpty) {
        final eventId = _decode(pending.first['json'] as String)['event_id'];
        if (eventId is String) {
          await DeviceViewRepository.markSynced(transaction, eventId);
        }
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
          String diaryId, String voiceId, String contentHash) async =>
      VoiceCacheRepository(await database).get(diaryId, voiceId, contentHash);

  Future<void> saveAudio(AudioAsset asset, String filePath) async =>
      VoiceCacheRepository(await database).save(asset, filePath);

  Future<String?> defaultVoice(String serverUrl) async =>
      VoiceCacheRepository(await database).defaultVoice(serverUrl);

  Future<void> saveDefaultVoice(String serverUrl, String voiceId) async =>
      VoiceCacheRepository(await database).saveDefaultVoice(serverUrl, voiceId);
  Future<String?> selectedVoice(String serverUrl) async =>
      VoiceCacheRepository(await database).selectedVoice(serverUrl);

  Future<void> saveSelectedVoice(String serverUrl, String voiceId) async =>
      VoiceCacheRepository(await database)
          .saveSelectedVoice(serverUrl, voiceId);
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
