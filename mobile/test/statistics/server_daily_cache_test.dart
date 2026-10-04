import 'dart:convert';
import 'dart:io';

import 'package:diary_mobile/models/server_daily_statistics.dart';
import 'package:diary_mobile/services/local_store.dart';
import 'package:diary_mobile/statistics/server_daily_cache.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:path/path.dart' as path;
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

void main() {
  sqfliteFfiInit();
  late Directory directory;
  late LocalStore store;
  late ServerDailyCache cache;
  final start = DateTime(2026, 9, 1);
  final end = DateTime(2026, 9, 30);
  const daily = ServerDailyStatistics(
    startDate: '2026-09-01',
    endDate: '2026-09-30',
    totalEvents: 3,
    activeDays: 1,
    dailyCounts: {'2026-09-02': 3},
    yesterdayDate: '2026-10-03',
    yesterdayTotalViews: 1,
    bestDayDate: '2026-09-02',
    bestDayViews: 3,
  );

  setUp(() async {
    directory = await Directory.systemTemp.createTemp('daily-cache-');
    final database = await databaseFactoryFfi
        .openDatabase(path.join(directory.path, 'diary.db'));
    await LocalStore.createSchema(database, 5);
    store = LocalStore.withDatabase(database);
    cache = ServerDailyCache(store);
  });
  tearDown(() async {
    await store.close();
    await directory.delete(recursive: true);
  });

  test('cache persists real daily history by server and range across restart',
      () async {
    final fetchedAt = DateTime.utc(2026, 10, 4, 8);
    await cache.save('https://first.invalid', start, end, daily,
        fetchedAt: fetchedAt);
    final settings = await (await store.database)
        .query('sync_state', columns: ['key', 'value']);
    expect(settings.single['key'], isNot(contains('first.invalid')));
    expect(settings.single['value'], isNot(contains('first.invalid')));
    await store.close();
    final reopened = await databaseFactoryFfi
        .openDatabase(path.join(directory.path, 'diary.db'));
    store = LocalStore.withDatabase(reopened);
    cache = ServerDailyCache(store);
    final cached = await cache.load('https://first.invalid', start, end);
    expect(cached!.statistics.dailyCounts['2026-09-02'], 3);
    expect(cached.statistics.bestDayDate, '2026-09-02');
    expect(cached.fetchedAt, fetchedAt);
    expect(await cache.load('https://second.invalid', start, end), isNull);
    expect(await cache.load('https://first.invalid', DateTime(2026, 8), end),
        isNull);
    expect(await store.getOutbox(), isEmpty);
  });

  test('repeated saves replace the same month without modifying diaries',
      () async {
    await cache.save('scope', start, end, daily);
    await cache.save('scope', start, end, daily);
    expect((await (await store.database).query('sync_state')), hasLength(1));
    expect(await store.getDiaries(), isEmpty);
    expect(await store.getOutbox(), isEmpty);
  });

  test('corrupt or mismatched cached data never become historical events',
      () async {
    expect(() => cache.save('scope', DateTime(2026, 8), end, daily),
        throwsFormatException);
    await cache.save('scope', start, end, daily);
    final database = await store.database;
    final rows = await database.query('sync_state');
    await database.update('sync_state', {'value': '{broken'},
        where: 'key = ?', whereArgs: [rows.single['key']]);
    expect(await cache.load('scope', start, end), isNull);
    await cache.save('scope', start, end, daily);
    final valid = await database.query('sync_state');
    final payload =
        jsonDecode(valid.single['value'] as String) as Map<String, dynamic>;
    (payload['statistics'] as Map<String, dynamic>)['total_events'] = 99;
    await database.update('sync_state', {'value': jsonEncode(payload)},
        where: 'key = ?', whereArgs: [valid.single['key']]);
    expect(await cache.load('scope', start, end), isNull);
    expect(await store.getOutbox(), isEmpty);
  });
}
