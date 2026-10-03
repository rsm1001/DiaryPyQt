import 'dart:convert';
import 'dart:io';

import 'package:diary_mobile/models/diary.dart';
import 'package:diary_mobile/services/diary_api.dart';
import 'package:diary_mobile/transfer/diary_transfer.dart';
import 'package:diary_mobile/services/local_store.dart';
import 'package:diary_mobile/services/sync_manager.dart';
import 'package:diary_mobile/tags/batch_tag_policy.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:path/path.dart' as path;
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

Diary diary(String id, {List<String> tags = const ['old']}) => Diary(
      id: id,
      date: '2026-09-29',
      content: 'content-$id',
      contentHash: 'sha256:$id',
      version: 4,
      tags: tags,
      updatedAt: '2026-09-29T00:00:00Z',
      viewCount: 7,
      lastViewedAt: '2026-09-29T01:00:00Z',
    );

class _TagApi extends DiaryApi {
  _TagApi() : super(baseUrl: '');

  bool conflict = true;
  @override
  Future<Diary> fetchDiary(String id) async => diary(id);

  @override
  Future<Diary> updateDiary(
    Diary diary, {
    required String content,
    required List<String> tags,
  }) async {
    if (conflict) {
      throw const DiaryApiException('Version conflict', conflict: true);
    }
    return Diary(
      id: diary.id,
      date: diary.date,
      content: content,
      contentHash: diary.contentHash,
      version: diary.version + 1,
      tags: tags,
      updatedAt: '2026-09-29T03:00:00Z',
      viewCount: diary.viewCount,
      lastViewedAt: diary.lastViewedAt,
    );
  }
}

void main() {
  sqfliteFfiInit();
  late Directory directory;
  late LocalStore store;
  late DiaryApi api;
  late SyncManager sync;

  setUp(() async {
    directory = await Directory.systemTemp.createTemp('diary-batch-tag-');
    final db = await databaseFactoryFfi
        .openDatabase(path.join(directory.path, 'diary.db'));
    await LocalStore.createSchema(db, 1);
    store = LocalStore.withDatabase(db);
    api = DiaryApi(baseUrl: '');
    sync = SyncManager(api: api, store: store);
  });

  tearDown(() async {
    await store.close();
    api.dispose();
    await directory.delete(recursive: true);
  });

  test('add/remove/replace modes preserve original tags as intended', () {
    expect(applyBatchTags(['a'], ['b', 'a'], BatchTagMode.add), ['a', 'b']);
    expect(applyBatchTags(['a', 'b'], ['a'], BatchTagMode.remove), ['b']);
    expect(applyBatchTags(['a'], ['b'], BatchTagMode.replace), ['b']);
    expect(applyBatchTags(['a'], [], BatchTagMode.replace), isEmpty);
  });

  test('batch edit queues versioned updates and retains pending views',
      () async {
    await store.saveDiary(diary('a'));
    await store.saveDiary(diary('b'));
    await store.recordViewLocally('a', 'event-1', '2026-09-29T02:00:00Z');
    expect(
        await sync.batchTagDiaries({'a', 'b'}, ['new'], BatchTagMode.add), 2);
    final result = await store.getDiary('a');
    expect(result!.tags, ['old', 'new']);
    expect(result.viewCount, 8);
    expect(result.lastViewedAt, '2026-09-29T02:00:00Z');
    expect(result.version, 4);
    expect(result.content, 'content-a');
    final outbox = await store.getOutbox();
    expect(outbox.map((row) => row['action']), ['view', 'update', 'update']);
    expect(outbox[1]['base_version'], 4);
    expect(jsonDecode(outbox[1]['json'] as String), {
      'content': 'content-a',
      'tags': ['old', 'new'],
    });
    expect(await sync.batchTagDiaries({'a'}, ['old'], BatchTagMode.remove), 1);
    expect((await store.getOutbox()), hasLength(3));
    expect((await store.getDiary('a'))!.tags, ['new']);
  });

  test('pending local create remains one create with merged tags', () async {
    await sync.importDiaries(const [
      DiaryImportEntry(date: '2026-09-29', content: 'draft', tags: ['one']),
    ]);
    final item = (await store.getDiaries()).single;
    expect(await sync.batchTagDiaries({item.id}, ['two'], BatchTagMode.add), 1);
    final pending = (await store.getOutbox()).single;
    expect(pending['action'], 'create');
    final payload =
        jsonDecode(pending['json'] as String) as Map<String, dynamic>;
    expect(payload['tags'], ['one', 'two']);
    expect(payload['content'], 'draft');
  });

  test('invalid or deleted selection rolls back all changes', () async {
    await store.saveDiary(diary('a'));
    await store.saveDiary(diary('b'));
    await store.enqueueMutation(
        entityId: 'b', action: 'delete', baseVersion: 4, payload: const {});
    await expectLater(
      sync.batchTagDiaries({'a', 'b'}, ['new'], BatchTagMode.add),
      throwsA(isA<StateError>()),
    );
    expect((await store.getDiary('a'))!.tags, ['old']);
    expect((await store.getOutbox()).single['action'], 'delete');
  });
  test('server conflict preserves tags and pending version for retry',
      () async {
    await store.saveDiary(diary('server-a'));
    await sync.batchTagDiaries({'server-a'}, ['new'], BatchTagMode.add);
    final remote = _TagApi();
    addTearDown(remote.dispose);
    final uploader = SyncManager(api: remote, store: store);
    await expectLater(
        uploader.flushPending(), throwsA(isA<DiaryApiException>()));
    expect((await store.getDiary('server-a'))!.tags, ['old', 'new']);
    expect((await store.getOutbox()).single['base_version'], 4);
    remote.conflict = false;
    final review = (await uploader.getConflicts()).single;
    expect(review.remote!.version, 4);
    await uploader.resolveConflict(review, keepLocal: true);
    await uploader.flushPending();
    expect(await store.getOutbox(), isEmpty);
    expect((await store.getDiary('server-a'))!.version, 5);
  });
}
