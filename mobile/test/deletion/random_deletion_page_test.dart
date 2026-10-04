import 'dart:math';

import 'package:diary_mobile/deletion/random_deletion_page.dart';
import 'package:diary_mobile/deletion/random_deletion_policy.dart';
import 'package:diary_mobile/deletion/random_deletion_service.dart';
import 'package:diary_mobile/models/diary.dart';
import 'package:diary_mobile/services/diary_api.dart';
import 'package:diary_mobile/services/local_store.dart';
import 'package:diary_mobile/services/sync_manager.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';

Diary entry(String id, {int views = 4, List<String> tags = const ['生活']}) =>
    Diary(
        id: id,
        date: '2026-09-15',
        content: '示例日记$id',
        contentHash: 'hash:$id',
        version: 1,
        tags: tags,
        updatedAt: '2026-09-15T10:00:00Z',
        viewCount: views);

class _MemoryService extends RandomDeletionService {
  _MemoryService()
      : super(
            store: LocalStore(),
            sync: SyncManager(api: DiaryApi(baseUrl: ''), store: LocalStore()));

  final entries = <Diary>[
    entry('a', views: 8, tags: ['工作']),
    entry('b', views: 2)
  ];
  final movedIds = <String>[];
  Object? error;
  RandomDeletionResult outcome = RandomDeletionResult.confirmed;

  @override
  Future<List<Diary>> candidates(
          {DeletionFilters filters = const DeletionFilters(),
          Set<String> excluded = const {},
          DateTime? now}) async =>
      const RandomDeletionPolicy().candidates(entries,
          filters: filters, excluded: excluded, now: DateTime(2026, 10, 3));

  @override
  Future<Diary?> draw(
      {DeletionFilters filters = const DeletionFilters(),
      Set<String> excluded = const {},
      DateTime? now,
      Random? random}) async {
    final available = await candidates(filters: filters, excluded: excluded);
    return available.isEmpty ? null : available.first;
  }

  @override
  Future<RandomDeletionResult> moveToTrash(Diary preview) async {
    movedIds.add(preview.id);
    if (error != null) throw error!;
    entries.removeWhere((diary) => diary.id == preview.id);
    return outcome;
  }

  void dispose() => sync.api.dispose();
}

void useTallViewport(WidgetTester tester) {
  tester.view.physicalSize = const Size(1100, 3000);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
}

void main() {
  testWidgets('候选筛选、摘要预览、重新抽取与取消不触发删除', (tester) async {
    useTallViewport(tester);
    final service = _MemoryService();
    addTearDown(service.dispose);
    var changed = 0;
    await tester.pumpWidget(MaterialApp(
        locale: const Locale('zh', 'CN'),
        supportedLocales: const [Locale('zh', 'CN'), Locale('en', 'US')],
        localizationsDelegates: GlobalMaterialLocalizations.delegates,
        home: RandomDeletionPage(
          service: service,
          onChanged: () async => changed++,
        )));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField).first, '5');
    await tester.tap(find.text('应用筛选并抽取'));
    await tester.pumpAndSettle();
    expect(find.textContaining('正文摘要：示例日记a'), findsOneWidget);
    expect(find.text('查看次数：8'), findsWidgets);
    expect(find.textContaining('标签：工作'), findsWidgets);
    await tester.tap(find.text('取消').first);
    await tester.pumpAndSettle();
    expect(service.movedIds, isEmpty);
    expect(changed, 0);
    await tester.tap(find.text('重置抽取记录'));
    await tester.pumpAndSettle();
    expect(find.textContaining('正文摘要：示例日记a'), findsOneWidget);
    await tester.tap(find.text('重新抽取'));
    await tester.pumpAndSettle();
    expect(find.textContaining('候选已看完'), findsOneWidget);
    await tester.enterText(find.byType(TextField).first, '-1');
    await tester.tap(find.text('应用筛选并抽取'));
    await tester.pumpAndSettle();
    expect(find.textContaining('查看次数请输入非负整数'), findsOneWidget);
    expect(service.movedIds, isEmpty);
  });

  testWidgets('取消确认不删除，断网排队时不误报服务器删除', (tester) async {
    useTallViewport(tester);
    final service = _MemoryService()..outcome = RandomDeletionResult.queued;
    addTearDown(service.dispose);
    var changed = 0;
    await tester.pumpWidget(MaterialApp(
        locale: const Locale('zh', 'CN'),
        supportedLocales: const [Locale('zh', 'CN'), Locale('en', 'US')],
        localizationsDelegates: GlobalMaterialLocalizations.delegates,
        home: RandomDeletionPage(
          service: service,
          onChanged: () async => changed++,
        )));
    await tester.pumpAndSettle();
    await tester.tap(find.text('应用筛选并抽取'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('移入回收站').first);
    await tester.pumpAndSettle();
    expect(find.text('确认移入回收站？'), findsOneWidget);
    await tester.tap(find.text('取消').last);
    await tester.pumpAndSettle();
    expect(service.movedIds, isEmpty);
    await tester.tap(find.text('移入回收站').first);
    await tester.pumpAndSettle();
    await tester.tap(find.text('移入回收站').last);
    await tester.pumpAndSettle();
    expect(service.movedIds, ['a']);
    expect(changed, 1);
    expect(find.text('删除任务已保存待同步，服务器尚未确认。'), findsOneWidget);
  });

  testWidgets('失败提示保持候选供重试；确认后才显示服务器成功', (tester) async {
    useTallViewport(tester);
    final service = _MemoryService()..error = StateError('模拟服务器失败');
    addTearDown(service.dispose);
    var changed = 0;
    await tester.pumpWidget(MaterialApp(
        locale: const Locale('zh', 'CN'),
        supportedLocales: const [Locale('zh', 'CN'), Locale('en', 'US')],
        localizationsDelegates: GlobalMaterialLocalizations.delegates,
        home: RandomDeletionPage(
          service: service,
          onChanged: () async => changed++,
        )));
    await tester.pumpAndSettle();
    await tester.tap(find.text('应用筛选并抽取'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('移入回收站').first);
    await tester.pumpAndSettle();
    await tester.tap(find.text('移入回收站').last);
    await tester.pumpAndSettle();
    expect(find.textContaining('删除未确认成功'), findsOneWidget);
    expect(find.textContaining('正文摘要：示例日记a'), findsOneWidget);
    expect(changed, 0);
    service.error = null;
    await tester.tap(find.text('移入回收站').first);
    await tester.pumpAndSettle();
    await tester.tap(find.text('移入回收站').last);
    await tester.pumpAndSettle();
    expect(find.text('服务器已确认移入回收站。'), findsOneWidget);
    expect(changed, 1);
  });
  testWidgets(
      'English locale labels random deletion without altering candidates',
      (tester) async {
    useTallViewport(tester);
    final service = _MemoryService();
    addTearDown(service.dispose);
    await tester.pumpWidget(MaterialApp(
      locale: const Locale('en', 'US'),
      supportedLocales: const [Locale('zh', 'CN'), Locale('en', 'US')],
      localizationsDelegates: GlobalMaterialLocalizations.delegates,
      home: RandomDeletionPage(service: service, onChanged: () async {}),
    ));
    await tester.pumpAndSettle();
    expect(find.text('Random deletion candidates'), findsOneWidget);
    expect(find.text('Apply filters and draw'), findsOneWidget);
    await tester.tap(find.text('Apply filters and draw'));
    await tester.pumpAndSettle();
    expect(find.text('Move to trash'), findsOneWidget);
    expect(service.movedIds, isEmpty);
  });
}
