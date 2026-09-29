import 'dart:io';

import 'package:diary_mobile/services/diary_api.dart';
import 'package:diary_mobile/services/diary_transfer.dart';
import 'package:diary_mobile/services/local_store.dart';
import 'package:diary_mobile/services/sync_manager.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:path/path.dart' as path;
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

void main() {
  sqfliteFfiInit();
  late Directory directory;
  late Database database;
  late LocalStore store;
  late DiaryApi api;

  setUp(() async {
    directory = await Directory.systemTemp.createTemp('diary-import-test-');
    database = await databaseFactoryFfi
        .openDatabase(path.join(directory.path, 'diary.db'));
    await LocalStore.createSchema(database, 1);
    store = LocalStore.withDatabase(database);
    api = DiaryApi(baseUrl: '');
  });

  tearDown(() async {
    await store.close();
    api.dispose();
    await directory.delete(recursive: true);
  });

  const first =
      DiaryImportEntry(date: '2026-09-29', content: 'first', tags: ['one']);
  const second =
      DiaryImportEntry(date: '2026-09-29', content: 'second', tags: []);

  test('import is atomic, offline, deduplicated and preserves outbox',
      () async {
    final sync = SyncManager(api: api, store: store);
    expect(await sync.importDiaries([first, second, first]), 2);
    expect((await store.getDiaries()).length, 2);
    final outbox = await store.getOutbox();
    expect(outbox, hasLength(2));
    expect(outbox.map((row) => row['action']), everyElement('create'));
    expect(await sync.importDiaries([first]), 0);
    expect(await store.getOutbox(), hasLength(2));
    expect((await store.getDiaries()).first.viewCount, 0);
  });

  test('outbox failure rolls back all imported diaries', () async {
    await database.execute('''
      CREATE TRIGGER reject_import BEFORE INSERT ON outbox
      WHEN NEW.json LIKE '%second%'
      BEGIN SELECT RAISE(ABORT, 'import rejected'); END
    ''');
    final sync = SyncManager(api: api, store: store);
    await expectLater(
        sync.importDiaries([first, second]), throwsA(isA<DatabaseException>()));
    expect(await store.getDiaries(), isEmpty);
    expect(await store.getOutbox(), isEmpty);
  });
}
