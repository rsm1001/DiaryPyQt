import 'dart:io';

import 'package:diary_mobile/models/diary.dart';
import 'package:diary_mobile/models/diary_view_result.dart';
import 'package:diary_mobile/services/local_store.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:path/path.dart' as path;
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

void main() {
  sqfliteFfiInit();
  late Directory directory;
  late Database database;
  late LocalStore store;

  setUp(() async {
    directory = await Directory.systemTemp.createTemp('diary-stats-');
    database = await databaseFactoryFfi
        .openDatabase(path.join(directory.path, 'stats.db'));
    await LocalStore.createSchema(database, 2);
    store = LocalStore.withDatabase(database);
  });

  tearDown(() async {
    await store.close();
    await directory.delete(recursive: true);
  });

  const diary = Diary(
    id: 'existing',
    date: '2026-09-27',
    content: '缓存正文',
    contentHash: '',
    version: 1,
    tags: ['生活'],
    updatedAt: '',
    viewCount: 70,
  );
  const viewedAt = '2026-09-27T12:00:00Z';

  test('历史基线不伪装成逐日事件，同步确认不重复计数', () async {
    await store.saveDiary(diary);
    final month = DateTime(2026, 9);
    final original = await store.getDeviceViewHistory(month);
    expect(original.totalEvents, 0);
    expect(original.dailyCounts, isEmpty);
    final id = await store.recordViewLocally(diary.id, 'event-1', viewedAt);
    final pending = await store.getDeviceViewHistory(month);
    expect(pending.totalEvents, 1);
    expect(pending.pendingEvents, 1);
    expect(pending.dailyCounts.values.single, 1);
    expect((await store.getDiary(diary.id))!.viewCount, 71);
    await store.confirmView(
        id, diary.id, const DiaryViewResult(viewCount: 71, viewedAt: viewedAt));
    final synced = await store.getDeviceViewHistory(month);
    expect(synced.totalEvents, 1);
    expect(synced.pendingEvents, 0);
    expect(synced.dailyCounts, pending.dailyCounts);
    expect((await store.getDiary(diary.id))!.viewCount, 71);
  });

  test('重复事件和无效时间不改变日记、待同步队列和日期统计', () async {
    await store.saveDiary(diary);
    await store.recordViewLocally(diary.id, 'event-1', viewedAt);
    await expectLater(store.recordViewLocally(diary.id, 'event-1', viewedAt),
        throwsA(isA<DatabaseException>()));
    await expectLater(store.recordViewLocally(diary.id, 'bad-time', '无效日期'),
        throwsFormatException);
    expect((await store.getDiary(diary.id))!.viewCount, 71);
    expect(await store.getOutbox(), hasLength(1));
    expect(
        (await store.getDeviceViewHistory(DateTime(2026, 9))).totalEvents, 1);
  });

  test('离线入队和确认失败时查看事件与状态随 SQLite 事务回滚', () async {
    await store.saveDiary(diary);
    await database
        .execute("CREATE TRIGGER reject_outbox BEFORE INSERT ON outbox "
            "BEGIN SELECT RAISE(ABORT, '拒绝入队'); END");
    await expectLater(store.recordViewLocally(diary.id, 'event-1', viewedAt),
        throwsA(isA<DatabaseException>()));
    expect(
        (await store.getDeviceViewHistory(DateTime(2026, 9))).totalEvents, 0);
    expect((await store.getDiary(diary.id))!.viewCount, 70);
    await database.execute('DROP TRIGGER reject_outbox');
    final id = await store.recordViewLocally(diary.id, 'event-1', viewedAt);
    await database.execute("CREATE TRIGGER reject_ack BEFORE DELETE ON outbox "
        "BEGIN SELECT RAISE(ABORT, '拒绝出队'); END");
    await expectLater(
        store.confirmView(id, diary.id,
            const DiaryViewResult(viewCount: 71, viewedAt: viewedAt)),
        throwsA(isA<DatabaseException>()));
    final pending = await store.getDeviceViewHistory(DateTime(2026, 9));
    expect(pending.totalEvents, 1);
    expect(pending.pendingEvents, 1);
    expect(await store.getOutbox(), hasLength(1));
  });

  test('按本地日历月份查询，跨月后只展示当月事件', () async {
    await store.saveDiary(diary);
    await store.recordViewLocally(
        diary.id, 'september', '2026-09-15T12:00:00Z');
    await store.recordViewLocally(diary.id, 'october', '2026-10-15T12:00:00Z');
    final september = await store.getDeviceViewHistory(DateTime(2026, 9));
    final october = await store.getDeviceViewHistory(DateTime(2026, 10));
    expect(september.dailyCounts.values.single, 1);
    expect(october.dailyCounts.values.single, 1);
    expect(september.totalEvents, 2);
    expect(october.totalEvents, 2);
  });

  test('旧版 SQLite 升级后保留原有数据并创建查看事件表', () async {
    final legacyPath = path.join(directory.path, 'legacy.db');
    final legacy = await databaseFactoryFfi.openDatabase(legacyPath,
        options: OpenDatabaseOptions(
            version: 1,
            onCreate: (db, version) async {
              await db
                  .execute('CREATE TABLE legacy_data (value TEXT NOT NULL)');
              await db.insert('legacy_data', {'value': '原有日记'});
            }));
    await legacy.close();
    final upgraded = await databaseFactoryFfi.openDatabase(legacyPath,
        options: OpenDatabaseOptions(
            version: 2, onUpgrade: LocalStore.upgradeSchema));
    expect((await upgraded.query('legacy_data')).single['value'], '原有日记');
    expect(await upgraded.query('device_view_events'), isEmpty);
    await upgraded.close();
  });
}
