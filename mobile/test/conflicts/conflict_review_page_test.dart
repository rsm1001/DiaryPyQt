import 'package:diary_mobile/conflicts/conflict_review_page.dart';
import 'package:diary_mobile/conflicts/diary_conflict.dart';
import 'package:diary_mobile/models/diary.dart';
import 'package:diary_mobile/services/diary_api.dart';
import 'package:diary_mobile/services/local_store.dart';
import 'package:diary_mobile/services/sync_manager.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

Diary sample(String content, int version) => Diary(
      id: 'entry',
      date: '2026-09-27',
      content: content,
      contentHash: 'hash:$content',
      version: version,
      tags: [content],
      updatedAt: '2026-09-27T10:00:00Z',
    );

class _MockSync extends SyncManager {
  _MockSync() : super(api: DiaryApi(baseUrl: ''), store: LocalStore());
  final reviews = <DiaryConflict>[];
  bool? kept;
  @override
  Future<List<DiaryConflict>> getConflicts() async => List.of(reviews);
  @override
  Future<void> resolveConflict(DiaryConflict conflict,
      {required bool keepLocal}) async {
    kept = keepLocal;
    reviews.remove(conflict);
  }

  @override
  Future<void> refreshConflict(DiaryConflict conflict) async {}
}

void main() {
  testWidgets('展示本地与服务器正文标签版本，暂不处理和取消确认不修改冲突', (tester) async {
    final sync = _MockSync();
    final conflict = DiaryConflict(
        diaryId: 'entry',
        local: sample('手机内容', 1),
        remote: sample('电脑内容', 2),
        action: 'update');
    sync.reviews.add(conflict);
    var changed = 0;
    await tester.pumpWidget(MaterialApp(
        home: ConflictReviewPage(
      sync: sync,
      onResolved: () async => changed++,
    )));
    await tester.pumpAndSettle();
    expect(find.textContaining('本地版本 1'), findsOneWidget);
    expect(find.textContaining('服务器版本 2'), findsOneWidget);
    expect(find.textContaining('手机内容'), findsWidgets);
    expect(find.textContaining('电脑内容'), findsWidgets);
    await tester.tap(find.text('暂不处理'));
    await tester.pumpAndSettle();
    expect(sync.reviews, hasLength(1));
    expect(changed, 0);
    await tester.tap(find.text('采用服务器'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('取消'));
    await tester.pumpAndSettle();
    expect(sync.reviews, hasLength(1));
    expect(sync.kept, isNull);
    await tester.tap(find.text('保留本地'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('确认'));
    await tester.pumpAndSettle();
    expect(sync.kept, true);
    expect(sync.reviews, isEmpty);
    expect(changed, 1);
    sync.api.dispose();
  });

  testWidgets('服务器已删除时禁用保留本地以免自动复活', (tester) async {
    final sync = _MockSync();
    final remote = Diary(
        id: 'entry',
        date: '2026-09-27',
        content: '已删除',
        contentHash: 'hash:已删除',
        version: 3,
        tags: const [],
        updatedAt: '2026-09-28T00:00:00Z',
        deletedAt: '2026-09-29T00:00:00Z');
    sync.reviews.add(DiaryConflict(
        diaryId: 'entry',
        local: sample('本地编辑', 1),
        remote: remote,
        action: 'update'));
    await tester.pumpWidget(MaterialApp(
        home: ConflictReviewPage(sync: sync, onResolved: () async {})));
    await tester.pumpAndSettle();
    expect(find.textContaining('服务器已删除该日记'), findsOneWidget);
    expect(
        tester
            .widget<FilledButton>(find.widgetWithText(FilledButton, '保留本地'))
            .onPressed,
        isNull);
    expect(
        tester
            .widget<FilledButton>(find.widgetWithText(FilledButton, '采用服务器'))
            .onPressed,
        isNotNull);
    sync.api.dispose();
  });
  testWidgets('服务器快照缺失时禁用处理操作，只允许刷新', (tester) async {
    final sync = _MockSync();
    sync.reviews.add(DiaryConflict(
        diaryId: 'entry',
        local: sample('本地', 1),
        remote: null,
        action: 'delete'));
    await tester.pumpWidget(MaterialApp(
        home: ConflictReviewPage(
      sync: sync,
      onResolved: () async {},
    )));
    await tester.pumpAndSettle();
    expect(find.textContaining('服务器版本暂不可用'), findsOneWidget);
    expect(
        tester
            .widget<FilledButton>(find.widgetWithText(FilledButton, '采用服务器'))
            .onPressed,
        isNull);
    sync.api.dispose();
  });
}
