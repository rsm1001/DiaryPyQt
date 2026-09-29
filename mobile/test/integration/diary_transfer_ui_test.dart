import 'package:diary_mobile/models/diary.dart';
import 'package:diary_mobile/pages/diary_transfer_page.dart';
import 'package:diary_mobile/platform/diary_document_adapter.dart';
import 'package:diary_mobile/services/diary_api.dart';
import 'package:diary_mobile/services/diary_transfer.dart';
import 'package:diary_mobile/services/local_store.dart';
import 'package:diary_mobile/services/sync_manager.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

class _FakeDocuments extends DiaryDocumentAdapter {
  const _FakeDocuments();

  @override
  Future<String?> pickJson() async =>
      '[{"date":"2026-09-29","content":"imported diary","tags":["work"]}]';

  @override
  Future<bool> saveJson(String data) async => true;
}

class _MemoryStore extends LocalStore {
  @override
  Future<List<Diary>> getDiaries() async => [];
}

class _MemorySync extends SyncManager {
  _MemorySync({required super.api, required super.store});

  int created = 0;

  @override
  Future<int> importDiaries(List<DiaryImportEntry> entries) async {
    created += entries.length;
    return entries.length;
  }
}

void main() {
  testWidgets('import requires preview confirmation', (tester) async {
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
    await tester.tap(find.text('\u4ece JSON \u5bfc\u5165'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));
    expect(find.text('\u786e\u8ba4\u5bfc\u5165'), findsOneWidget);
    expect(sync.created, 0);
    await tester.tap(find.text('\u5bfc\u5165').last);
    await tester.pumpAndSettle();
    expect(notified, isTrue);
    expect(sync.created, 1);
  });
}
