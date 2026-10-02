import 'dart:convert';

import 'package:diary_mobile/models/diary.dart';
import 'package:diary_mobile/pages/diary_statistics_page.dart';
import 'package:diary_mobile/services/diary_api.dart';
import 'package:diary_mobile/services/diary_statistics.dart';
import 'package:diary_mobile/services/local_store.dart';
import 'package:diary_mobile/statistics/device_view_repository.dart';
import 'package:flutter/material.dart';
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
    final key = '${month.year.toString().padLeft(4, '0')}-'
        '${month.month.toString().padLeft(2, '0')}-01';
    return DeviceViewHistory(
      totalEvents: 2,
      pendingEvents: 1,
      dailyCounts:
          month.year == selectedMonth.year && month.month == selectedMonth.month
              ? {key: 2}
              : const {},
    );
  }
}

void useTallViewport(WidgetTester tester) {
  tester.view.physicalSize = const Size(1100, 3000);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
}

void main() {
  const cached = [
    Diary(
        id: 'one',
        date: '2026-09-27',
        content: '离线日记',
        contentHash: '',
        version: 1,
        tags: ['生活'],
        updatedAt: '',
        viewCount: 19),
  ];

  test('缓存日期分布不伪造查看历史', () {
    final distribution = cachedDiaryDays(cached, DateTime(2026, 9));
    expect(distribution['2026-09-27'], 1);
    expect(cachedDiaryDays(cached, DateTime(2026, 10)), isEmpty);
    expect(cached.single.viewCount, 19);
  });

  testWidgets('服务器与缓存口径分开；刷新和换月仅发送统计 GET', (tester) async {
    useTallViewport(tester);
    final now = DateTime.now();
    final local = _MemoryHistory()..selectedMonth = now;
    var offline = false;
    final requests = <http.Request>[];
    final api = DiaryApi(
      baseUrl: 'https://example.invalid',
      client: MockClient((request) async {
        requests.add(request);
        if (offline) throw const DiaryApiException('模拟离线', network: true);
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
        home: DiaryStatisticsPage(
      diaries: cached,
      api: api,
      store: local,
    )));
    await tester.pumpAndSettle();
    expect(find.text('325 次'), findsOneWidget);
    expect(find.text('19 次'), findsOneWidget);
    expect(find.text('本设备新增查看 2 次', skipOffstage: false), findsOneWidget);
    expect(find.text('其中待同步'), findsOneWidget);
    expect(find.textContaining('服务器历史逐日明细不可用', skipOffstage: false),
        findsOneWidget);
    await tester.tap(find.byTooltip('上个月'));
    await tester.pumpAndSettle();
    expect(local.requested.last.month, DateTime(now.year, now.month - 1).month);
    expect(find.text('本月没有本设备新增查看事件。', skipOffstage: false), findsOneWidget);
    offline = true;
    await tester.tap(find.byTooltip('刷新统计'));
    await tester.pumpAndSettle();
    expect(find.textContaining('上次成功获取', skipOffstage: false), findsOneWidget);
    expect(find.text('325 次', skipOffstage: false), findsOneWidget);
    expect(requests, hasLength(2));
    expect(
        requests.every((request) =>
            request.method == 'GET' &&
            request.url.path.endsWith('/statistics')),
        isTrue);
    expect(cached.single.viewCount, 19);
  });

  testWidgets('断网与本地读取失败明确标示来源且不显示虚构总数', (tester) async {
    useTallViewport(tester);
    final local = _MemoryHistory()..selectedMonth = DateTime.now();
    final api = DiaryApi(
        baseUrl: 'https://example.invalid',
        client: MockClient((request) async =>
            throw const DiaryApiException('模拟断网', network: true)));
    addTearDown(api.dispose);
    await tester.pumpWidget(MaterialApp(
        home: DiaryStatisticsPage(
      diaries: cached,
      api: api,
      store: local,
    )));
    await tester.pumpAndSettle();
    expect(
        find.textContaining('服务器统计不可用', skipOffstage: false), findsOneWidget);
    expect(find.text('19 次', skipOffstage: false), findsOneWidget);
    expect(find.text('本设备新增查看 2 次', skipOffstage: false), findsOneWidget);
    local.fail = true;
    await tester.tap(find.byTooltip('下个月'));
    await tester.pumpAndSettle();
    expect(find.text('本设备逐日记录读取失败，请重试。', skipOffstage: false), findsOneWidget);
    expect(find.textContaining('服务器历史逐日明细不可用', skipOffstage: false),
        findsOneWidget);
  });

  testWidgets('空缓存与空查看事件有明确状态', (tester) async {
    useTallViewport(tester);
    final local = _MemoryHistory()..selectedMonth = DateTime(1900, 1);
    final api = DiaryApi(
        baseUrl: 'https://example.invalid',
        client: MockClient((request) async => http.Response(
            jsonEncode({
              'total_diaries': 0,
              'total_views': 0,
              'average_views': 0,
            }),
            200)));
    addTearDown(api.dispose);
    await tester.pumpWidget(MaterialApp(
        home: DiaryStatisticsPage(
      diaries: const [],
      api: api,
      store: local,
    )));
    await tester.pumpAndSettle();
    expect(find.text('缓存日记'), findsOneWidget);
    expect(find.text('暂无标签', skipOffstage: false), findsOneWidget);
    expect(find.text('本月没有本设备新增查看事件。', skipOffstage: false), findsOneWidget);
  });
}
