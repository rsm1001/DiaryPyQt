import 'dart:io';

import 'package:diary_mobile/models/diary.dart';
import 'package:diary_mobile/playback/playback_record.dart';
import 'package:diary_mobile/services/diary_api.dart';
import 'package:diary_mobile/services/local_store.dart';
import 'package:diary_mobile/services/sync_manager.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:path/path.dart' as path;
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

class _PlaybackApi extends DiaryApi {
  _PlaybackApi() : super(baseUrl: '');
  final sent = <PlaybackRecord>[];
  bool offline = false;
  final remote = <String, PlaybackRecord>{};
  @override
  Future<PlaybackRecord> savePlayback(PlaybackRecord record) async {
    if (offline) throw const DiaryApiException('网络中断', network: true);
    remote['${record.diaryId}|${record.voiceId}'] = record;
    sent.add(record);
    return record;
  }

  @override
  Future<List<PlaybackRecord>> fetchPlaybackRecords({
    String? deviceId,
    String? diaryId,
    String? voiceId,
  }) async =>
      remote.values
          .where((record) =>
              (deviceId == null || record.deviceId == deviceId) &&
              (diaryId == null || record.diaryId == diaryId) &&
              (voiceId == null || record.voiceId == voiceId))
          .toList();
}

const diary = Diary(
    id: 'diary',
    date: '2026-09-27',
    content: '正文',
    contentHash: 'hash',
    version: 1,
    tags: [],
    updatedAt: '',
    viewCount: 5);

void main() {
  sqfliteFfiInit();
  late Directory temp;
  late LocalStore store;
  late _PlaybackApi api;
  late SyncManager sync;
  setUp(() async {
    temp = await Directory.systemTemp.createTemp('playback-test-');
    final db = await databaseFactoryFfi
        .openDatabase(path.join(temp.path, 'db.sqlite'));
    await LocalStore.createSchema(db, 5);
    store = LocalStore.withDatabase(db);
    api = _PlaybackApi();
    sync = SyncManager(api: api, store: store);
  });
  tearDown(() async {
    await store.close();
    api.dispose();
    await temp.delete(recursive: true);
  });

  test('本地记录按日记和语音幂等覆盖，断网进入待同步队列', () async {
    final first = await sync.savePlaybackRecord(
        diaryId: diary.id,
        voiceId: 'voice',
        roundNumber: 1,
        positionMs: 100,
        status: 'playing');
    final second = await sync.savePlaybackRecord(
        diaryId: diary.id,
        voiceId: 'voice',
        roundNumber: 1,
        positionMs: 500,
        status: 'paused');
    expect(first.deviceId, second.deviceId);
    expect((await store.getPlayback(diary.id, 'voice'))!.positionMs, 500);
    expect((await store.getOutbox()).single['action'], 'playback');
    expect(
        (await store.getOutbox()).single['json'] as String, contains('paused'));
    expect((await store.getDiary(diary.id)), isNull);
  });

  test('联网补交同一播放记录不增加查看次数，服务器记录可查询', () async {
    await store.saveDiary(diary);
    final record = await sync.savePlaybackRecord(
        diaryId: diary.id,
        voiceId: 'voice',
        roundNumber: 2,
        positionMs: 900,
        status: 'paused');
    api.offline = true;
    await expectLater(sync.flushPending(), throwsA(isA<DiaryApiException>()));
    expect(await store.getOutbox(), hasLength(1));
    api.offline = false;
    await sync.flushPending();
    await sync.flushPending();
    expect(await store.getOutbox(), isEmpty);
    expect(api.sent.map((item) => item.positionMs), [900]);
    final remote = await sync.remotePlayback(diary.id, 'voice');
    expect(remote!.roundNumber, 2);
    expect(remote.positionMs, 900);
    expect((await store.getDiary(diary.id))!.viewCount, 5);
    expect(record.status, 'paused');
  });

  test('播放状态可区分暂停、等待、完成和跳过', () async {
    for (final status in ['paused', 'waiting', 'completed', 'skipped']) {
      await sync.savePlaybackRecord(
          diaryId: diary.id,
          voiceId: status,
          roundNumber: 1,
          positionMs: 10,
          status: status);
    }
    final records = await store.getPlaybacks();
    expect(records.map((record) => record.status).toSet(),
        {'paused', 'waiting', 'completed', 'skipped'});
    expect(records.every((record) => record.diaryId == diary.id), isTrue);
  });

  test('旧数据库升级创建播放记录表并保留日记', () async {
    final oldPath = path.join(temp.path, 'old.db');
    final oldDb = await databaseFactoryFfi.openDatabase(oldPath,
        options: OpenDatabaseOptions(
            version: 4,
            onCreate: (db, version) async {
              await db.execute(
                  'CREATE TABLE diaries (id TEXT PRIMARY KEY, json TEXT NOT NULL, version INTEGER NOT NULL, content_hash TEXT NOT NULL)');
              await db.execute(
                  'CREATE TABLE sync_state (key TEXT PRIMARY KEY, value TEXT NOT NULL)');
              await db.insert('diaries', {
                'id': diary.id,
                'json': '{}',
                'version': 1,
                'content_hash': ''
              });
            }));
    await oldDb.close();
    final upgraded = await databaseFactoryFfi.openDatabase(oldPath,
        options: OpenDatabaseOptions(
            version: 5, onUpgrade: LocalStore.upgradeSchema));
    expect(await upgraded.query('playback_records'), isEmpty);
    await upgraded.close();
  });
}
