import 'dart:io';

import 'package:diary_mobile/deletion/random_deletion_service.dart';
import 'package:diary_mobile/models/diary.dart';
import 'package:diary_mobile/services/diary_api.dart';
import 'package:diary_mobile/services/local_store.dart';
import 'package:diary_mobile/services/sync_manager.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:path/path.dart' as path;
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

Diary entry(String id,
        {int version = 2, String content = '原文', int views = 8}) =>
    Diary(
        id: id,
        date: '2026-09-20',
        content: content,
        contentHash: 'hash:$content',
        version: version,
        tags: const ['生活'],
        updatedAt: '2026-09-20T10:00:00Z',
        viewCount: views,
        lastViewedAt: '2026-09-21T10:00:00Z');

class _DeleteApi extends DiaryApi {
  _DeleteApi() : super(baseUrl: '');
  final remote = <String, Diary>{};
  int deletes = 0;
  bool offline = false;
  bool reject = false;

  @override
  Future<void> deleteDiary(Diary diary) async {
    deletes++;
    if (offline) throw const DiaryApiException('网络中断', network: true);
    if (reject) throw const DiaryApiException('操作失败', statusCode: 500);
    if (remote[diary.id]?.version != diary.version) {
      throw const DiaryApiException('版本冲突', conflict: true, statusCode: 409);
    }
    remote.remove(diary.id);
  }

  @override
  Future<Diary> fetchDiary(String diaryId) async => remote[diaryId]!;
}

void main() {
  sqfliteFfiInit();
  late Directory temp;
  late LocalStore store;
  late _DeleteApi api;
  late RandomDeletionService service;

  setUp(() async {
    temp = await Directory.systemTemp.createTemp('deletion-test-');
    final db =
        await databaseFactoryFfi.openDatabase(path.join(temp.path, 'diary.db'));
    await LocalStore.createSchema(db, 4);
    store = LocalStore.withDatabase(db);
    api = _DeleteApi();
    service = RandomDeletionService(
        store: store, sync: SyncManager(api: api, store: store));
  });
  tearDown(() async {
    await store.close();
    api.dispose();
    await temp.delete(recursive: true);
  });

  test('断网仅抽本地候选，候选排除待编辑和本地草稿，播放权重不变', () async {
    final diary = entry('candidate');
    await store.saveDiary(diary);
    await store.saveDiary(entry('local-draft'));
    await store.saveDiary(entry('editing'));
    await store.enqueueMutation(
        entityId: 'editing',
        action: 'update',
        baseVersion: 2,
        payload: {'content': '草稿', 'tags': <String>[]});
    await store.recordRandomSelection('candidate');
    final before = await store.getRandomUsage();
    api.offline = true;
    final chosen = await service.draw(now: DateTime(2026, 10, 3));
    expect(chosen!.id, 'candidate');
    expect(api.deletes, 0);
    expect((await store.getRandomUsage())['candidate']!.count,
        before['candidate']!.count);
    expect((await store.getDiary('candidate'))!.viewCount, 8);
  });

  test('确认后联网按版本移入回收站，绝不调用永久删除', () async {
    final diary = entry('online');
    await store.saveDiary(diary);
    api.remote[diary.id] = diary;
    final result = await service.moveToTrash(diary);
    expect(result, RandomDeletionResult.confirmed);
    expect(api.deletes, 1);
    expect(api.remote, isEmpty);
    expect(await store.getDiary(diary.id), isNull);
    expect(await store.getOutbox(), isEmpty);
  });

  test('断网只保留待同步删除，不能宣称服务器已移入回收站', () async {
    final diary = entry('offline');
    await store.saveDiary(diary);
    api.remote[diary.id] = diary;
    api.offline = true;
    final result = await service.moveToTrash(diary);
    expect(result, RandomDeletionResult.queued);
    expect(api.remote.containsKey(diary.id), isTrue);
    expect((await store.getDiary(diary.id))!.deletedAt, isNotNull);
    expect((await store.getDiary(diary.id))!.viewCount, diary.viewCount);
    expect((await store.getOutbox()).single['action'], 'delete');
    expect(await store.getRandomUsage(), isEmpty);
  });

  test('远端版本冲突保留人工审核意图，不误称服务器已删除', () async {
    final diary = entry('conflict');
    await store.saveDiary(diary);
    api.remote[diary.id] = entry(diary.id, version: 3, content: '电脑改动');
    expect(await service.moveToTrash(diary), RandomDeletionResult.conflict);
    expect(api.remote.containsKey(diary.id), isTrue);
    expect((await store.getDiary(diary.id))!.deletedAt, isNotNull);
    expect((await store.getOutbox()).single['base_version'], 2);
    expect((await store.getConflicts()).single.action, 'delete');
  });

  test('请求失败及候选变更时不修改本地原文和查看统计', () async {
    final diary = entry('failed');
    await store.saveDiary(diary);
    api.remote[diary.id] = diary;
    api.reject = true;
    await expectLater(
        service.moveToTrash(diary), throwsA(isA<DiaryApiException>()));
    expect((await store.getDiary(diary.id))!.deletedAt, isNull);
    expect((await store.getDiary(diary.id))!.viewCount, 8);
    expect(await store.getOutbox(), isEmpty);
    api.reject = false;
    await store.saveDiary(entry(diary.id, content: '手机新编辑'));
    await expectLater(service.moveToTrash(diary), throwsA(isA<StateError>()));
    expect(api.deletes, 1);
    expect((await store.getDiary(diary.id))!.content, '手机新编辑');
  });
}
