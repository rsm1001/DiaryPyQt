import 'package:diary_mobile/conflicts/diary_conflict.dart';
import 'package:diary_mobile/models/diary.dart';
import 'package:diary_mobile/services/diary_api.dart';
import 'package:diary_mobile/services/local_store.dart';
import 'package:diary_mobile/services/sync_manager.dart';
import 'package:diary_mobile/pages/trash_page.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

Diary entry(String id, {String date = '2026-10-03', String? content}) => Diary(
    id: id,
    date: date,
    content: content ?? '正文$id',
    contentHash: 'hash:$id',
    version: 2,
    tags: const [],
    updatedAt: '',
    deletedAt: '2026-10-03T01:00:00Z');

class _FakeTrashApi extends DiaryApi {
  _FakeTrashApi() : super(baseUrl: '');
  final items = <Diary>[
    entry('a'),
    entry('b', date: '2026-09-02', content: '秋天的阅读'),
    entry('c')
  ];
  final purged = <String>[];
  final restored = <String>[];
  final failIds = <String>{};
  bool unavailable = false;
  bool unsupported = false;

  @override
  Future<List<Diary>> fetchTrash() async {
    if (unavailable) throw const DiaryApiException('离线', network: true);
    return List.of(items);
  }

  @override
  Future<Diary> restoreDiary(Diary diary) async {
    restored.add(diary.id);
    items.removeWhere((item) => item.id == diary.id);
    return diary;
  }

  @override
  Future<void> permanentlyDeleteDiary(Diary diary) async {
    purged.add(diary.id);
    if (unsupported) {
      throw const DiaryApiException('旧服务端不支持版本删除', statusCode: 404);
    }
    if (failIds.contains(diary.id)) {
      throw const DiaryApiException('版本冲突', conflict: true, statusCode: 409);
    }
    if (unavailable) throw const DiaryApiException('离线', network: true);
    items.removeWhere((item) => item.id == diary.id);
  }
}

class _FakeStore extends LocalStore {
  bool queued = false;
  @override
  Future<List<Map<String, dynamic>>> getOutbox() async => queued
      ? [
          {'entity_id': 'a', 'action': 'restore'}
        ]
      : const [];
}

class _FakeSync extends SyncManager {
  _FakeSync({required super.api, required super.store});
  bool offline = false;
  @override
  Future<List<DiaryConflict>> getConflicts() async => const [];
  @override
  Future<void> restoreDiary(Diary diary) async {
    if (offline) {
      (store as _FakeStore).queued = true;
      return;
    }
    await api.restoreDiary(diary);
  }
}

void useTallViewport(WidgetTester tester) {
  tester.view.physicalSize = const Size(1100, 2600);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
}

void main() {
  testWidgets('搜索日期正文、多选恢复、成功结果及列表刷新', (tester) async {
    useTallViewport(tester);
    final api = _FakeTrashApi();
    final store = _FakeStore();
    final sync = _FakeSync(api: api, store: store);
    var changes = 0;
    addTearDown(api.dispose);
    await tester.pumpWidget(MaterialApp(
        home:
            TrashPage(api: api, sync: sync, onChanged: () async => changes++)));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField), '2026-09 秋天');
    await tester.pumpAndSettle();
    expect(find.text('秋天的阅读'), findsOneWidget);
    expect(find.text('正文a'), findsNothing);
    await tester.longPress(find.text('秋天的阅读'));
    await tester.pumpAndSettle();
    expect(find.text('已选择 1 篇'), findsOneWidget);
    await tester.tap(find.text('批量恢复'));
    await tester.pumpAndSettle();
    expect(api.restored, ['b']);
    expect(changes, 1);
    expect(find.textContaining('成功 1 篇，失败 0 篇，未处理 0 篇'), findsOneWidget);
    expect(find.text('没有匹配的日记'), findsOneWidget);
  });

  testWidgets('单篇永久删除失败不阻断后续，保留失败项供重试', (tester) async {
    useTallViewport(tester);
    final api = _FakeTrashApi()..failIds.add('b');
    addTearDown(api.dispose);
    await tester.pumpWidget(MaterialApp(
        home: TrashPage(
            api: api, sync: _FakeSync(api: api, store: _FakeStore()))));
    await tester.pumpAndSettle();
    await tester.tap(find.text('选择筛选结果'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('批量永久删除'));
    await tester.pumpAndSettle();
    expect(api.purged, isEmpty);
    await tester.tap(find.text('继续'));
    await tester.pumpAndSettle();
    expect(api.purged, ['a', 'b', 'c']);
    expect(find.textContaining('成功 2 篇，失败 1 篇，未处理 0 篇'), findsOneWidget);
    expect(find.text('已选择 1 篇'), findsOneWidget);
    api.failIds.clear();
    await tester.tap(find.text('批量永久删除'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('继续'));
    await tester.pumpAndSettle();
    expect(api.purged.last, 'b');
    expect(find.text('回收站暂无日记'), findsOneWidget);
  });

  testWidgets('清空回收站要求二次确认，旧服务端版本入口不可用时安全停止', (tester) async {
    useTallViewport(tester);
    final api = _FakeTrashApi()..unsupported = true;
    addTearDown(api.dispose);
    await tester.pumpWidget(MaterialApp(
        home: TrashPage(
            api: api, sync: _FakeSync(api: api, store: _FakeStore()))));
    await tester.pumpAndSettle();
    await tester.tap(find.text('清空回收站'));
    await tester.pumpAndSettle();
    expect(api.purged, isEmpty);
    await tester.tap(find.text('取消'));
    await tester.pumpAndSettle();
    expect(api.purged, isEmpty);
    await tester.tap(find.text('清空回收站'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('继续'));
    await tester.pumpAndSettle();
    final clear =
        tester.widget<FilledButton>(find.widgetWithText(FilledButton, '永久清空'));
    expect(clear.onPressed, isNull);
    await tester.enterText(find.byType(TextField).last, '清空');
    await tester.pumpAndSettle();
    expect(
        tester
            .widget<FilledButton>(find.widgetWithText(FilledButton, '永久清空'))
            .onPressed,
        isNotNull);
    await tester.tap(find.text('永久清空'));
    await tester.pumpAndSettle();
    expect(api.purged, ['a']);
    expect(find.textContaining('成功 0 篇，失败 1 篇，未处理 2 篇'), findsOneWidget);
    expect(find.textContaining('版本校验删除接口不可用'), findsOneWidget);
    expect(find.text('正文b'), findsNothing);
    api.unsupported = false;
    await tester.tap(find.text('清空回收站'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('继续'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField).last, '清空');
    await tester.pumpAndSettle();
    await tester.tap(find.text('永久清空'));
    await tester.pumpAndSettle();
    expect(api.purged, ['a', 'a', 'b', 'c']);
    expect(find.text('回收站暂无日记'), findsOneWidget);
  });

  testWidgets('离线恢复排队不算成功，其余项目保留未处理', (tester) async {
    useTallViewport(tester);
    final api = _FakeTrashApi();
    final store = _FakeStore();
    final sync = _FakeSync(api: api, store: store)..offline = true;
    addTearDown(api.dispose);
    await tester.pumpWidget(MaterialApp(home: TrashPage(api: api, sync: sync)));
    await tester.pumpAndSettle();
    await tester.tap(find.text('选择筛选结果'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('批量恢复'));
    await tester.pumpAndSettle();
    expect(api.restored, isEmpty);
    expect(find.textContaining('成功 0 篇，失败 0 篇，未处理 3 篇'), findsOneWidget);
    expect(find.text('已选择 3 篇'), findsOneWidget);
  });
}
