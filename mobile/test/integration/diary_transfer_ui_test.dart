import 'package:diary_mobile/models/diary.dart';
import 'package:diary_mobile/pages/diary_transfer_page.dart';
import 'package:diary_mobile/platform/diary_document_adapter.dart';
import 'package:diary_mobile/services/diary_api.dart';
import 'package:diary_mobile/transfer/diary_transfer.dart';
import 'package:diary_mobile/services/local_store.dart';
import 'package:diary_mobile/services/sync_manager.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

class _FakeDocuments extends DiaryDocumentAdapter {
  const _FakeDocuments(
      {this.csv = 'date,content,tags,view_count\n'
          '2026-09-29,imported diary,"[""work""]",22\n'});

  final String csv;

  @override
  Future<String?> pickJson() async =>
      '[{"date":"2026-09-29","content":"imported diary","tags":["work"]}]';

  @override
  Future<String?> pickCsv() async => csv;

  @override
  Future<bool> saveJson(String data) async => true;

  @override
  Future<bool> saveCsv(String data) async => true;
}

class _MemoryStore extends LocalStore {
  @override
  Future<List<Diary>> getDiaries() async => [];
}

class _MemorySync extends SyncManager {
  _MemorySync({required super.api, required super.store});

  int created = 0;
  List<DiaryImportEntry> entries = [];

  @override
  Future<int> importDiaries(List<DiaryImportEntry> entries) async {
    this.entries = entries;
    created += entries.length;
    return entries.length;
  }
}

void main() {
  for (final csv in [false, true]) {
    testWidgets('${csv ? 'CSV' : 'JSON'} 导入前需要预览确认', (tester) async {
      final store = _MemoryStore();
      final api = DiaryApi(baseUrl: '');
      final sync = _MemorySync(api: api, store: store);
      var notified = false;
      addTearDown(api.dispose);
      await tester.pumpWidget(MaterialApp(
        home: DiaryTransferPage(
          store: store,
          sync: sync,
          documents: const _FakeDocuments(),
          onImported: () async => notified = true,
        ),
      ));
      await tester.tap(find.text(csv ? '从 CSV 导入' : '从 JSON 导入'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));
      expect(find.text('确认导入'), findsOneWidget);
      expect(sync.created, 0);
      await tester.tap(find.text('导入').last);
      await tester.pumpAndSettle();
      expect(notified, isTrue);
      expect(sync.created, 1);
      expect(sync.entries.single.tags, ['work']);
    });
  }

  testWidgets('有非法日期时整批 CSV 不导入', (tester) async {
    final store = _MemoryStore();
    final api = DiaryApi(baseUrl: '');
    final sync = _MemorySync(api: api, store: store);
    addTearDown(api.dispose);
    await tester.pumpWidget(MaterialApp(
      home: DiaryTransferPage(
        store: store,
        sync: sync,
        documents: const _FakeDocuments(
            csv: 'date,content\n'
                '2026-09-29,valid\n2026-02-29,invalid\n'),
        onImported: () async {},
      ),
    ));
    await tester.tap(find.text('从 CSV 导入'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));
    expect(find.textContaining('错误 1 篇'), findsOneWidget);
    expect(
        tester
            .widget<FilledButton>(find.widgetWithText(FilledButton, '导入'))
            .onPressed,
        isNull);
    expect(sync.created, 0);
  });
}
