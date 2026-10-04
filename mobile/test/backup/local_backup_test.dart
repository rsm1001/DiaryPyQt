import 'dart:convert';
import 'dart:io';

import 'package:diary_mobile/backup/local_backup.dart';
import 'package:diary_mobile/models/app_preferences.dart';
import 'package:diary_mobile/models/diary.dart';
import 'package:diary_mobile/playback/playback_record.dart';
import 'package:diary_mobile/playback/local_store_playback.dart';
import 'package:diary_mobile/services/app_preferences_store.dart';
import 'package:diary_mobile/services/local_store.dart';
import 'package:diary_mobile/backup/local_store_backup.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:path/path.dart' as path;
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

const diary = Diary(
    id: 'entry',
    date: '2026-10-03',
    content: '本地正文',
    contentHash: 'hash',
    version: 2,
    tags: ['工作'],
    updatedAt: '2026-10-03',
    viewCount: 4,
    lastViewedAt: '2026-10-03T01:00:00Z');

void main() {
  sqfliteFfiInit();
  late Directory temp;
  late Database db;
  late LocalStore store;
  setUp(() async {
    temp = await Directory.systemTemp.createTemp('backup-test-');
    db =
        await databaseFactoryFfi.openDatabase(path.join(temp.path, 'diary.db'));
    await LocalStore.createSchema(db, 5);
    store = LocalStore.withDatabase(db);
  });
  tearDown(() async {
    await store.close();
    await temp.delete(recursive: true);
  });

  test('本地数据库完整性检查通过，不修改日记', () async {
    await store.saveDiary(diary);
    expect(await store.checkLocalIntegrity(), isTrue);
    expect((await store.getDiary(diary.id))!.content, diary.content);
  });
  test('备份包含本地队列、冲突、播放记录和非敏感设置，不包含服务器密码', () async {
    await store.saveDiary(diary);
    await store.enqueueMutation(
        entityId: diary.id,
        action: 'update',
        baseVersion: 2,
        payload: {
          'content': '待同步',
          'tags': ['工作']
        });
    await store.saveSelectedVoice('https://server.invalid', 'voice-a');
    await store.saveServerUrl('https://server.invalid');
    final backup = await store.exportLocalBackup();
    final decoded = jsonDecode(backup.encode()) as Map<String, dynamic>;
    final data = decoded['data'] as Map<String, dynamic>;
    expect(data['diaries'], isNotEmpty);
    expect(data['outbox'], isNotEmpty);
    expect(data['settings'].toString(), isNot(contains('voice_id')));
    expect(data['settings'].toString(), isNot(contains('server_url')));
    expect(backup.encode(), isNot(contains('https://server.invalid')));
    expect(backup.encode(), isNot(contains('device-')));
    expect(backup.encode(), isNot(contains('password')));
    expect(() => LocalBackup.parse(backup.encode()), returnsNormally);
  });

  test('恢复备份保留本机界面偏好且不将其导出', () async {
    final preferences = AppPreferences.defaults.copyWith(
      themeMode: AppThemeMode.dark,
      language: AppLanguage.english,
      showDate: false,
    );
    await store.saveAppPreferences(preferences);
    await store.saveDiary(diary);
    final backup = await store.exportLocalBackup();
    expect(backup.encode(), isNot(contains('app_preferences')));
    await store.removeDiary(diary.id);

    await store.restoreLocalBackup(backup);
    expect((await store.getAppPreferences()).toJson(), preferences.toJson());
    expect((await store.getDiary(diary.id))!.content, diary.content);
    expect(await store.getOutbox(), isEmpty);
  });
  test('损坏、空文件、错误版本和缺表备份均拒绝', () async {
    expect(() => LocalBackup.parse(''), throwsFormatException);
    expect(() => LocalBackup.parse('{"backup_type":"diary_mobile_local"}'),
        throwsFormatException);
    final backup = await store.exportLocalBackup();
    final decoded = jsonDecode(backup.encode()) as Map<String, dynamic>;
    decoded['checksum'] = 'bad';
    expect(() => LocalBackup.parse(jsonEncode(decoded)), throwsFormatException);
    decoded['checksum'] = backup.checksum;
    decoded['backup_version'] = 999;
    expect(() => LocalBackup.parse(jsonEncode(decoded)), throwsFormatException);
  });

  test('恢复事务替换本地数据，失败时整体回滚', () async {
    await store.saveDiary(diary);
    await store.enqueueMutation(
        entityId: diary.id,
        action: 'update',
        baseVersion: 2,
        payload: {'content': '旧队列', 'tags': []});
    final backup = await store.exportLocalBackup();
    await store.removeDiary(diary.id);
    await store.restoreLocalBackup(backup);
    expect((await store.getDiary(diary.id))!.content, diary.content);
    expect((await store.getOutbox()).single['action'], 'update');
    final invalid = LocalBackup(
      payload: backup.payload,
      checksum: backup.checksum,
    );
    await store.restoreLocalBackup(invalid);
    expect((await store.getDiary(diary.id))!.content, diary.content);
  });

  test('恢复待审核冲突及待同步任务后仍可离线核对', () async {
    await store.saveDiary(diary);
    await store.enqueueMutation(
        entityId: diary.id,
        action: 'update',
        baseVersion: 2,
        payload: {
          'content': '本地内容',
          'tags': ['工作']
        });
    await store.recordConflict(diary.id, 'update', null);
    final backup = await store.exportLocalBackup();
    await db.delete('diary_conflicts');
    await store.restoreLocalBackup(backup);
    expect((await store.getOutbox()).single['action'], 'update');
    expect((await store.getConflicts()).single.local.content, diary.content);
    expect(await store.hasPendingLocalChanges(), isTrue);
    expect((await store.getDiary(diary.id))!.viewCount, diary.viewCount);
  });
  test('恢复失败时 SQLite 事务回滚，原日记和队列不变', () async {
    await store.saveDiary(diary);
    final backup = await store.exportLocalBackup();
    await db.execute("CREATE TRIGGER reject_backup BEFORE INSERT ON diaries "
        "BEGIN SELECT RAISE(ABORT, '拒绝恢复'); END");
    await expectLater(
        store.restoreLocalBackup(backup), throwsA(isA<DatabaseException>()));
    expect((await store.getDiary(diary.id))!.content, diary.content);
    expect(await store.getOutbox(), isEmpty);
  });

  test('服务器归属不同拒绝恢复并保留现有本地数据', () async {
    await store.saveServerUrl('https://original.invalid');
    final backup = await store.exportLocalBackup();
    await store.saveServerUrl('https://other.invalid');
    await store.saveDiary(diary);
    await expectLater(store.restoreLocalBackup(backup), throwsFormatException);
    expect((await store.getDiary(diary.id))!.content, diary.content);
  });

  test('备份设置字段不可覆盖服务器地址', () async {
    final backup = await store.exportLocalBackup();
    final decoded = jsonDecode(backup.encode()) as Map<String, dynamic>;
    final data = decoded['data'] as Map<String, dynamic>;
    (data['settings'] as List).add({'key': 'server_url', 'value': 'unsafe'});
    decoded['checksum'] = LocalBackup.buildChecksum({
      'backup_version': decoded['backup_version'],
      'created_at': decoded['created_at'],
      'server_scope': decoded['server_scope'],
      'data': data,
    });
    expect(() => LocalBackup.parse(jsonEncode(decoded)), throwsFormatException);
  });

  test('跨设备恢复播放状态时重新绑定设备身份和待同步记录', () async {
    await store.saveServerUrl('https://same.invalid');
    await store.saveDiary(diary);
    await store.savePlayback(const PlaybackRecord(
      id: 'play-1',
      deviceId: 'device-original',
      diaryId: 'entry',
      voiceId: 'voice',
      roundNumber: 1,
      positionMs: 90,
      status: 'paused',
      updatedAt: '2026-10-03T10:00:00Z',
    ));
    final backup = await store.exportLocalBackup();
    expect(backup.encode(), isNot(contains('device-original')));
    final destDb = await databaseFactoryFfi
        .openDatabase(path.join(temp.path, 'another.db'));
    await LocalStore.createSchema(destDb, 5);
    final dest = LocalStore.withDatabase(destDb);
    try {
      await dest.saveServerUrl('https://same.invalid');
      final newDeviceId = await dest.getDeviceId();
      await dest.restoreLocalBackup(backup);
      final current = await dest.getPlayback('entry', 'voice');
      expect(current!.deviceId, newDeviceId);
      final playbackTask = (await dest.getOutbox()).single;
      final payload =
          jsonDecode(playbackTask['json'] as String) as Map<String, dynamic>;
      expect(payload['device_id'], newDeviceId);
      expect((await dest.getDiary('entry'))!.viewCount, diary.viewCount);
    } finally {
      await dest.close();
    }
  });
  test('恢复后播放记录可以继续读取', () async {
    await store.savePlayback(const PlaybackRecord(
        id: 'p',
        deviceId: 'device',
        diaryId: 'entry',
        voiceId: 'voice',
        roundNumber: 2,
        positionMs: 900,
        status: 'paused',
        updatedAt: 'now'));
    final backup = await store.exportLocalBackup();
    final targetDb = await databaseFactoryFfi
        .openDatabase(path.join(temp.path, 'target.db'));
    await LocalStore.createSchema(targetDb, 5);
    final target = LocalStore.withDatabase(targetDb);
    await target.restoreLocalBackup(backup);
    expect((await target.getPlayback('entry', 'voice'))!.positionMs, 900);
    await target.close();
  });
}
