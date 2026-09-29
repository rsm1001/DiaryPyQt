import 'dart:io';

import 'package:diary_mobile/models/diary.dart';
import 'package:diary_mobile/models/diary_view_result.dart';
import 'package:diary_mobile/services/diary_api.dart';
import 'package:diary_mobile/services/local_store.dart';
import 'package:diary_mobile/services/sync_manager.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:path/path.dart' as path;
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

Diary sample(String id) => Diary(
      id: id,
      date: '2026-09-27',
      content: '示例正文',
      contentHash: 'sha256:sample',
      version: 1,
      tags: const [],
      updatedAt: '2026-09-27T00:00:00Z',
    );

class FakeViewApi extends DiaryApi {
  FakeViewApi() : super(baseUrl: '');

  @override
  Future<Diary> updateDiary(
    Diary diary, {
    required String content,
    required List<String> tags,
  }) async {
    if (!onlineUpdates) {
      throw const DiaryApiException('\u7f51\u7edc\u4e2d\u65ad', network: true);
    }
    return Diary(
      id: diary.id,
      date: diary.date,
      content: content,
      contentHash: 'sha256:changed',
      version: diary.version + 1,
      tags: tags,
      updatedAt: diary.updatedAt,
    );
  }

  @override
  Future<void> deleteDiary(Diary diary) async =>
      throw const DiaryApiException('\u7f51\u7edc\u4e2d\u65ad', network: true);

  bool onlineUpdates = false;
  final seen = <String>{};
  final requestedIds = <String>[];
  int remoteCount = 0;
  String? lastViewedAt;
  bool offline = false;
  bool loseReply = false;
  bool reject = false;

  @override
  Future<DiaryViewResult> recordView(
    Diary diary, {
    required String eventId,
    required String viewedAt,
  }) async {
    requestedIds.add(diary.id);
    if (reject) throw const DiaryApiException('服务器拒绝事件');
    if (offline) throw const DiaryApiException('网络中断', network: true);
    if (seen.add(eventId)) {
      remoteCount++;
      lastViewedAt = viewedAt;
    }
    if (loseReply) {
      loseReply = false;
      throw const DiaryApiException('响应丢失', network: true);
    }
    return DiaryViewResult(
      viewCount: remoteCount,
      viewedAt: lastViewedAt!,
    );
  }

  @override
  Future<Diary> createDiary({
    required String date,
    required String content,
    required List<String> tags,
  }) async =>
      sample('server-id');
}

void main() {
  sqfliteFfiInit();
  late Directory directory;
  late String dbPath;
  late Database database;
  late LocalStore store;
  late FakeViewApi api;

  setUp(() async {
    directory = await Directory.systemTemp.createTemp('diary-view-sqlite-');
    dbPath = path.join(directory.path, 'diary.db');
    database = await databaseFactoryFfi.openDatabase(dbPath);
    await LocalStore.createSchema(database, 1);
    store = LocalStore.withDatabase(database);
    api = FakeViewApi();
  });

  tearDown(() async {
    await store.close();
    api.dispose();
    await directory.delete(recursive: true);
  });

  test('断网查看写入 SQLite 后重启仍用同一事件重试', () async {
    final diary = sample('entry-id');
    await store.saveDiary(diary);
    final sync = SyncManager(api: api, store: store);
    api.loseReply = true;
    await sync.recordView(diary);
    final pending = await store.getOutbox();
    expect(pending, hasLength(1));
    expect((await store.getDiary(diary.id))!.viewCount, 1);
    expect(api.remoteCount, 1);

    await store.close();
    database = await databaseFactoryFfi.openDatabase(dbPath);
    store = LocalStore.withDatabase(database);
    expect(await store.getOutbox(), pending);
    await SyncManager(api: api, store: store).flushPending();
    expect(api.remoteCount, 1);
    expect(api.seen, hasLength(1));
    expect(await store.getOutbox(), isEmpty);
    expect((await store.getDiary(diary.id))!.viewCount, 1);
  });

  test('离线多次查看联网后逐条同步', () async {
    final diary = sample('entry-id');
    await store.saveDiary(diary);
    final sync = SyncManager(api: api, store: store);
    api.offline = true;
    await sync.recordView(diary);
    await sync.recordView(diary);
    final pending = await store.getOutbox();
    expect(pending, hasLength(2));
    expect(pending[0]['json'], isNot(pending[1]['json']));
    expect((await store.getDiary(diary.id))!.viewCount, 2);

    api.offline = false;
    await sync.flushPending();
    expect(api.remoteCount, 2);
    expect(api.seen, hasLength(2));
    expect((await store.getDiary(diary.id))!.viewCount, 2);
    expect(await store.getOutbox(), isEmpty);
  });

  test('服务端拒绝时保留本地查看和队列', () async {
    final diary = sample('entry-id');
    await store.saveDiary(diary);
    await store.recordViewLocally(diary.id, 'event-1', '2026-09-27T01:00:00Z');
    api.reject = true;
    await expectLater(
      SyncManager(api: api, store: store).flushPending(),
      throwsA(isA<DiaryApiException>()),
    );
    expect((await store.getDiary(diary.id))!.viewCount, 1);
    expect(await store.getOutbox(), hasLength(1));
    expect(api.remoteCount, 0);
  });

  test('SQLite 入队失败不增加本地次数', () async {
    final diary = sample('entry-id');
    await store.saveDiary(diary);
    await database.execute(
      "CREATE TRIGGER refuse_view BEFORE INSERT ON outbox "
      "BEGIN SELECT RAISE(ABORT, '模拟失败'); END",
    );
    await expectLater(
      store.recordViewLocally(diary.id, 'event-1', '2026-09-27T01:00:00Z'),
      throwsA(isA<DatabaseException>()),
    );
    expect((await store.getDiary(diary.id))!.viewCount, 0);
    expect(await store.getOutbox(), isEmpty);
  });

  test('服务器确认后 SQLite 出队失败整体回滚', () async {
    final diary = sample('entry-id');
    await store.saveDiary(diary);
    final id = await store.recordViewLocally(
      diary.id,
      'event-1',
      '2026-09-27T01:00:00Z',
    );
    await database.execute(
      "CREATE TRIGGER refuse_ack BEFORE DELETE ON outbox "
      "BEGIN SELECT RAISE(ABORT, '模拟失败'); END",
    );
    await expectLater(
      store.confirmView(
        id,
        diary.id,
        const DiaryViewResult(viewCount: 10, viewedAt: '2026-09-27T02:00:00Z'),
      ),
      throwsA(isA<DatabaseException>()),
    );
    expect((await store.getDiary(diary.id))!.viewCount, 1);
    expect(await store.getOutbox(), hasLength(1));
    await database.execute('DROP TRIGGER refuse_ack');
    await store.confirmView(
      id,
      diary.id,
      const DiaryViewResult(viewCount: 10, viewedAt: '2026-09-27T02:00:00Z'),
    );
    expect((await store.getDiary(diary.id))!.viewCount, 10);
    expect(await store.getOutbox(), isEmpty);
  });

  test('临时日记先获得服务端 ID 再同步查看', () async {
    final diary = sample('local-1');
    await store.saveDiary(diary);
    await store.enqueueMutation(
      entityId: diary.id,
      action: 'create',
      baseVersion: null,
      payload: {'date': diary.date, 'content': diary.content, 'tags': []},
    );
    await SyncManager(api: api, store: store).recordView(diary);
    expect(api.seen, isEmpty);
    await SyncManager(api: api, store: store).flushPending();
    expect(api.requestedIds, ['server-id']);
    expect(api.remoteCount, 1);
    expect(await store.getDiary(diary.id), isNull);
    expect((await store.getDiary('server-id'))!.viewCount, 1);
    expect(await store.getOutbox(), isEmpty);
  });

  test('使用旧日记快照离线编辑不回退查看次数', () async {
    final diary = sample('entry-id');
    await store.saveDiary(diary);
    await store.recordViewLocally(diary.id, 'event-1', '2026-09-27T01:00:00Z');
    final sync = SyncManager(api: api, store: store);
    await sync.updateDiary(diary, content: '更新正文', tags: []);
    final updated = (await store.getDiary(diary.id))!;
    expect(updated.viewCount, 1);
    expect(updated.lastViewedAt, '2026-09-27T01:00:00Z');
    expect(await store.getOutbox(), hasLength(2));
  });

  test('使用旧日记快照离线删除不丢查看事件', () async {
    final diary = sample('entry-id');
    await store.saveDiary(diary);
    await store.recordViewLocally(diary.id, 'event-1', '2026-09-27T01:00:00Z');
    final sync = SyncManager(api: api, store: store);
    api.offline = true;
    await sync.deleteDiary(diary);
    final deleted = (await store.getDiary(diary.id))!;
    expect(deleted.viewCount, 1);
    expect(deleted.lastViewedAt, '2026-09-27T01:00:00Z');
    expect(await store.getOutbox(), hasLength(2));
  });

  test('在线编辑保留待上报查看次数', () async {
    final diary = sample('entry-id');
    await store.saveDiary(diary);
    await store.recordViewLocally(diary.id, 'event-1', '2026-09-27T01:00:00Z');
    api.onlineUpdates = true;
    await SyncManager(api: api, store: store)
        .updateDiary(diary, content: '更新正文', tags: []);
    final cached = (await store.getDiary(diary.id))!;
    expect(cached.content, '更新正文');
    expect(cached.viewCount, 1);
    expect(cached.lastViewedAt, '2026-09-27T01:00:00Z');
    expect(await store.getOutbox(), hasLength(1));
  });
}
