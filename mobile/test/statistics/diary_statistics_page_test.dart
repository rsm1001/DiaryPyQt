import 'dart:async';
import 'dart:convert';

import 'package:diary_mobile/models/diary.dart';
import 'package:diary_mobile/pages/diary_statistics_page.dart';
import 'package:diary_mobile/services/diary_api.dart';
import 'package:diary_mobile/services/diary_statistics.dart';
import 'package:diary_mobile/services/local_store.dart';
import 'package:diary_mobile/statistics/device_view_repository.dart';
import 'package:diary_mobile/statistics/server_daily_cache.dart';
import 'package:diary_mobile/models/server_daily_statistics.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

class _MemoryHistory extends LocalStore {
  bool fail = false;
  final requested = <DateTime>[];
  late DateTime selectedMonth;

  @override
  Future<DeviceViewHistory> getDeviceViewHistory(DateTime month) async {
    requested.add(month);
    if (fail) throw StateError('模拟本地读取失败');
    return DeviceViewHistory(
      totalEvents: 2,
      pendingEvents: 1,
      dailyCounts:
          month.year == selectedMonth.year && month.month == selectedMonth.month
              ? {
                  '${month.year.toString().padLeft(4, '0')}-'
                      '${month.month.toString().padLeft(2, '0')}-01': 2
                }
              : const {},
    );
  }
}

class _MemoryDailyCache extends ServerDailyCache {
  _MemoryDailyCache() : super(LocalStore());

  final entries = <String, CachedServerDailyStatistics>{};

  String key(String scope, DateTime start, DateTime end) =>
      '$scope:${start.year}-${start.month}:${end.day}';

  @override
  Future<CachedServerDailyStatistics?> load(
          String scope, DateTime start, DateTime end) async =>
      entries[key(scope, start, end)];

  @override
  Future<CachedServerDailyStatistics> save(
    String scope,
    DateTime start,
    DateTime end,
    ServerDailyStatistics statistics, {
    DateTime? fetchedAt,
  }) async {
    final entry = CachedServerDailyStatistics(
      statistics: statistics,
      fetchedAt: fetchedAt ?? DateTime.utc(2026, 10, 4),
    );
    entries[key(scope, start, end)] = entry;
    return entry;
  }
}

void useTallViewport(WidgetTester tester) {
  tester.view.physicalSize = const Size(1100, 3000);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
}

const cached = [
  Diary(
    id: 'one',
    date: '2026-09-27',
    content: '离线日记',
    contentHash: '',
    version: 1,
    tags: ['生活'],
    updatedAt: '',
    viewCount: 19,
  ),
];

void main() {
  test('缓存日期分布不伪造查看历史', () {
    expect(cachedDiaryDays(cached, DateTime(2026, 9))['2026-09-27'], 1);
    expect(cachedDiaryDays(cached, DateTime(2026, 10)), isEmpty);
    expect(cached.single.viewCount, 19);
  });

  testWidgets('服务器历史与本设备事件分开展示，换月读取每日接口', (tester) async {
    useTallViewport(tester);
    final now = DateTime.now();
    final local = _MemoryHistory()..selectedMonth = now;
    final requests = <http.Request>[];
    final api = DiaryApi(
      baseUrl: 'https://example.invalid',
      client: MockClient((request) async {
        requests.add(request);
        if (request.url.path.endsWith('/statistics/daily')) {
          final start = request.url.queryParameters['start_date']!;
          return http.Response(
              jsonEncode({
                'start_date': start,
                'end_date': request.url.queryParameters['end_date'],
                'total_events': 3,
                'active_days': 1,
                'daily_counts': {start: 3},
                'yesterday_date': '2026-10-03',
                'yesterday_total_views': 0,
                'best_day_date': '2026-01-01',
                'best_day_views': 9,
              }),
              200);
        }
        return http.Response(
            jsonEncode({
              'total_diaries': 80,
              'total_views': 325,
              'average_views': 4.0625,
              'most_viewed_count': 21,
              'least_viewed_count': 0,
            }),
            200);
      }),
    );
    addTearDown(api.dispose);
    await tester.pumpWidget(MaterialApp(
        locale: const Locale('zh', 'CN'),
        supportedLocales: const [Locale('zh', 'CN'), Locale('en', 'US')],
        localizationsDelegates: GlobalMaterialLocalizations.delegates,
        home: DiaryStatisticsPage(
          diaries: cached,
          api: api,
          store: local,
          dailyCache: _MemoryDailyCache(),
        )));
    await tester.pumpAndSettle();
    expect(find.text('325 次'), findsOneWidget);
    expect(find.text('本月服务器查看事件'), findsOneWidget);
    expect(find.textContaining('昨日服务器查看（UTC）', skipOffstage: false),
        findsOneWidget);
    expect(find.text('2026-01-01 · 9 次', skipOffstage: false), findsOneWidget);
    expect(
        find.textContaining('服务器实时历史明细', skipOffstage: false), findsOneWidget);
    expect(find.text('3 次'), findsOneWidget);
    expect(find.text('本设备新增查看 2 次', skipOffstage: false), findsOneWidget);
    await tester.tap(find.byTooltip('上个月'));
    await tester.pumpAndSettle();
    expect(local.requested.last.month, DateTime(now.year, now.month - 1).month);
    expect(
        requests.where((request) => request.url.path.contains('/statistics')),
        hasLength(3));
    expect(cached.single.viewCount, 19);
  });

  testWidgets('离线只显示同一服务器缓存的真实历史并标注获取时间', (tester) async {
    useTallViewport(tester);
    final now = DateTime.now();
    final month = DateTime(now.year, now.month);
    final start = DateTime(month.year, month.month);
    final end = DateTime(month.year, month.month + 1, 0);
    String date(DateTime value) => '${value.year.toString().padLeft(4, '0')}-'
        '${value.month.toString().padLeft(2, '0')}-'
        '${value.day.toString().padLeft(2, '0')}';
    final fetchTime = DateTime.utc(2026, 10, 4, 8);
    final cache = _MemoryDailyCache();
    await cache.save(
      'https://example.invalid',
      start,
      end,
      ServerDailyStatistics(
        startDate: date(start),
        endDate: date(end),
        totalEvents: 7,
        activeDays: 1,
        dailyCounts: {date(start): 7},
        yesterdayDate: date(now.subtract(const Duration(days: 1))),
        yesterdayTotalViews: 3,
        bestDayDate: date(start),
        bestDayViews: 7,
      ),
      fetchedAt: fetchTime,
    );
    final local = _MemoryHistory()..selectedMonth = now;
    final api = DiaryApi(
      baseUrl: 'https://example.invalid',
      client: MockClient((request) async =>
          throw const DiaryApiException('offline', network: true)),
    );
    addTearDown(api.dispose);
    await tester.pumpWidget(MaterialApp(
      locale: const Locale('zh', 'CN'),
      supportedLocales: const [Locale('zh', 'CN'), Locale('en', 'US')],
      localizationsDelegates: GlobalMaterialLocalizations.delegates,
      home: DiaryStatisticsPage(
        diaries: cached,
        api: api,
        store: local,
        dailyCache: cache,
      ),
    ));
    await tester.pumpAndSettle();
    expect(
        find.textContaining('离线服务器历史缓存', skipOffstage: false), findsOneWidget);
    expect(
        find.textContaining(fetchTime.toIso8601String(), skipOffstage: false),
        findsOneWidget);
    expect(find.text('7 次', skipOffstage: false), findsWidgets);
    expect(find.text('3 次', skipOffstage: false), findsOneWidget);
    expect(find.textContaining('本设备新增查看 2 次', skipOffstage: false),
        findsOneWidget);
    expect(find.textContaining('服务器统计不可用'), findsOneWidget);
    expect(cache.entries, hasLength(1));
    await tester.tap(find.byTooltip('上个月'));
    await tester.pumpAndSettle();
    expect(find.textContaining('服务器每日明细暂不可用', skipOffstage: false),
        findsOneWidget);
    expect(find.textContaining('离线服务器历史缓存', skipOffstage: false), findsNothing);
    await tester.tap(find.byTooltip('下个月'));
    await tester.pumpAndSettle();
    expect(
        find.textContaining('离线服务器历史缓存', skipOffstage: false), findsOneWidget);
  });
  testWidgets('日期点击立即显示本地结果，服务器失败时不伪造日记', (tester) async {
    useTallViewport(tester);
    final now = DateTime.now();
    final local = _MemoryHistory()..selectedMonth = now;
    final calendar = Completer<http.Response>();
    final api = DiaryApi(
      baseUrl: 'https://example.invalid',
      client: MockClient((request) async {
        if (request.url.path.endsWith('/calendar/diaries')) {
          return calendar.future;
        }
        if (request.url.path.endsWith('/statistics/daily')) {
          return http.Response(
              jsonEncode({
                'start_date': request.url.queryParameters['start_date'],
                'end_date': request.url.queryParameters['end_date'],
                'total_events': 0,
                'active_days': 0,
                'daily_counts': <String, int>{},
              }),
              200);
        }
        return http.Response(
            jsonEncode({
              'total_diaries': 0,
              'total_views': 0,
              'average_views': 0,
            }),
            200);
      }),
    );
    addTearDown(api.dispose);
    await tester.pumpWidget(MaterialApp(
      locale: const Locale('zh', 'CN'),
      supportedLocales: const [Locale('zh', 'CN'), Locale('en', 'US')],
      localizationsDelegates: GlobalMaterialLocalizations.delegates,
      home: DiaryStatisticsPage(
        diaries: const [],
        api: api,
        store: local,
        dailyCache: _MemoryDailyCache(),
      ),
    ));
    await tester.pumpAndSettle();
    await tester.tap(find.text('1').first);
    await tester.pump();
    expect(find.text('本地没有缓存该日期的日记。'), findsOneWidget);
    expect(find.text('正在读取该日期的服务器日记……'), findsOneWidget);
    calendar.completeError(const DiaryApiException('offline', network: true));
    await tester.pumpAndSettle();
    expect(find.text('服务器日期明细暂不可用。'), findsOneWidget);
    expect(find.text('本地没有缓存该日期的日记。'), findsOneWidget);
  });
  testWidgets('断网、每日明细失败和空数据都有明确提示', (tester) async {
    useTallViewport(tester);
    final local = _MemoryHistory()..selectedMonth = DateTime.now();
    local.fail = true;
    final api = DiaryApi(
      baseUrl: 'https://example.invalid',
      client: MockClient((request) async =>
          throw const DiaryApiException('模拟断网', network: true)),
    );
    addTearDown(api.dispose);
    await tester.pumpWidget(MaterialApp(
        locale: const Locale('zh', 'CN'),
        supportedLocales: const [Locale('zh', 'CN'), Locale('en', 'US')],
        localizationsDelegates: GlobalMaterialLocalizations.delegates,
        home: DiaryStatisticsPage(
          diaries: const [],
          api: api,
          store: local,
          dailyCache: _MemoryDailyCache(),
        )));
    await tester.pumpAndSettle();
    expect(find.textContaining('服务器统计不可用'), findsOneWidget);
    expect(find.text('暂无标签', skipOffstage: false), findsOneWidget);
    expect(find.text('本设备逐日记录读取失败，请重试。', skipOffstage: false), findsOneWidget);
    expect(find.textContaining('服务器历史逐日明细不可用'), findsNothing);
  });
}
