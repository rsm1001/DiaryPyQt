import 'dart:convert';
import 'dart:io';

import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:diary_mobile/models/diary.dart';
import 'package:diary_mobile/models/diary_view_result.dart';
import 'package:diary_mobile/services/diary_api.dart';
import 'package:diary_mobile/services/local_store.dart';
import 'package:diary_mobile/services/sync_manager.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:path/path.dart' as path;
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

Diary sample(String id, {int version = 1, String content = '原文'}) => Diary(
      id: id,
      date: '2026-09-27',
      content: content,
      contentHash: 'sha256:sample',
      version: version,
      tags: const [],
      updatedAt: '2026-09-27T00:00:00Z',
    );

class MutationApi extends DiaryApi {
  MutationApi() : super(baseUrl: '');

  final remote = <String, Diary>{};
  final calls = <String>[];
  final seenViews = <String>{};
  bool offline = true;
  bool unreachable = false;
  int nextId = 0;
  int fetches = 0;

  void checkNetwork() {
    if (offline || unreachable) {
      throw const DiaryApiException('网络不可用', network: true);
    }
  }

  @override
  Future<Diary> createDiary({
    required String date,
    required String content,
    required List<String> tags,
  }) async {
    checkNetwork();
    final created = Diary(
      id: 'server-${++nextId}',
      date: date,
      content: content,
      contentHash: 'sha256:sample',
      version: 1,
      tags: tags,
      updatedAt: '2026-09-27T00:00:00Z',
    );
    remote[created.id] = created;
    return created;
  }

  @override
  Future<Diary> updateDiary(
    Diary diary, {
    required String content,
    required List<String> tags,
  }) async {
    checkNetwork();
    final current = remote[diary.id];
    if (current == null || current.version != diary.version) {
      throw const DiaryApiException('版本冲突', conflict: true);
    }
    final updated = Diary(
      id: diary.id,
      date: current.date,
      content: content,
      contentHash: 'sha256:sample',
      version: current.version + 1,
      tags: tags,
      updatedAt: '2026-09-27T00:00:00Z',
      viewCount: current.viewCount,
      lastViewedAt: current.lastViewedAt,
    );
    remote[diary.id] = updated;
    return updated;
  }

  @override
  Future<DiaryViewResult> recordView(
    Diary diary, {
    required String eventId,
    required String viewedAt,
  }) async {
    checkNetwork();
    calls.add('view');
    final current = remote[diary.id];
    if (current == null) {
      throw const DiaryApiException('日记不存在', conflict: true);
    }
    if (seenViews.add(eventId)) {
      remote[diary.id] = current.copyWith(
        viewCount: current.viewCount + 1,
        lastViewedAt: viewedAt,
      );
    }
    return DiaryViewResult(
      viewCount: remote[diary.id]!.viewCount,
      viewedAt: remote[diary.id]!.lastViewedAt!,
    );
  }

  @override
  Future<void> deleteDiary(Diary diary) async {
    checkNetwork();
    calls.add('delete');
    if (remote[diary.id]?.version != diary.version) {
      throw const DiaryApiException('版本冲突', conflict: true);
    }
    remote.remove(diary.id);
  }

  @override
  Future<List<Diary>> fetchDiaries() async {
    checkNetwork();
    fetches++;
    return remote.values.toList();
  }

  @override
  Future<Map<String, dynamic>> pull(int cursor) async {
    checkNetwork();
    return {'items': <dynamic>[], 'next_cursor': cursor + 1};
  }
}

void main() {
  sqfliteFfiInit();
  late Directory directory;
  late Database database;
  late LocalStore store;
  late MutationApi api;
  late SyncManager sync;
  var online = false;

  setUp(() async {
    directory = await Directory.systemTemp.createTemp('diary-mutation-sqlite-');
    database = await databaseFactoryFfi
        .openDatabase(path.join(directory.path, 'diary.db'));
    await LocalStore.createSchema(database, 1);
    store = LocalStore.withDatabase(database);
    api = MutationApi();
    online = false;
    sync = SyncManager(
      api: api,
      store: store,
      checkConnectivity: () async => [
        online ? ConnectivityResult.wifi : ConnectivityResult.none,
      ],
    );
  });

  tearDown(() async {
    await store.close();
    api.dispose();
    await directory.delete(recursive: true);
  });

  test('断网新建后多次编辑合并为一次上传，恢复后换成服务器 ID', () async {
    final created = await sync.createDiary(
      date: '2026-09-27',
      content: '草稿',
      tags: [],
    );
    expect(created.id, startsWith('local-'));
    final first = await sync.updateDiary(created, content: '修改', tags: []);
    await sync.updateDiary(first, content: '最终正文', tags: ['工作']);
    final pending = await store.getOutbox();
    expect(pending, hasLength(1));
    expect(pending.single['action'], 'create');
    expect(jsonDecode(pending.single['json'] as String)['content'], '最终正文');
    expect(await sync.refresh(), hasLength(1));
    expect(api.fetches, 0);

    api.offline = false;
    online = true;
    final refreshed = await sync.refresh();
    expect(refreshed.single.id, 'server-1');
    expect(refreshed.single.content, '最终正文');
    expect(refreshed.single.tags, ['工作']);
    expect(await store.getDiary(created.id), isNull);
    expect(await store.getOutbox(), isEmpty);
    expect(await store.getCursor(), 1);
  });

  test('离线新建查看后删除会连同未上传查看事件一起清除', () async {
    final created = await sync.createDiary(
      date: '2026-09-27',
      content: '撤销',
      tags: [],
    );
    await sync.recordView(created);
    expect(await store.getOutbox(), hasLength(2));
    await sync.deleteDiary(created);
    expect(await store.getDiary(created.id), isNull);
    expect(await store.getOutbox(), isEmpty);
    api.offline = false;
    online = true;
    expect(await sync.refresh(), isEmpty);
    expect(api.remote, isEmpty);
  });

  test('两端版本冲突保留离线编辑与基线版本，不覆写服务器', () async {
    final diary = sample('entry-id');
    await store.saveDiary(diary);
    api.remote[diary.id] = sample(diary.id, version: 2, content: '远端修改');
    await sync.updateDiary(diary, content: '本地修改', tags: []);
    api.offline = false;
    online = true;
    await expectLater(
      sync.refresh(),
      throwsA(isA<DiaryApiException>().having(
        (error) => error.conflict,
        '版本冲突',
        isTrue,
      )),
    );
    expect((await store.getDiary(diary.id))!.content, '本地修改');
    expect(api.remote[diary.id]!.content, '远端修改');
    expect((await store.getOutbox()).single['base_version'], 1);
    expect(await store.getCursor(), 0);
  });

  test('删除冲突时保留软删除和待同步事件', () async {
    final diary = sample('entry-id');
    await store.saveDiary(diary);
    api.remote[diary.id] = sample(diary.id, version: 2);
    await sync.deleteDiary(diary);
    expect(await store.getDiaries(), isEmpty);
    api.offline = false;
    online = true;
    await expectLater(sync.refresh(), throwsA(isA<DiaryApiException>()));
    expect((await store.getOutbox()).single['action'], 'delete');
    expect((await store.getDiary(diary.id))!.deletedAt, isNotNull);
    expect(api.remote[diary.id]!.version, 2);
  });

  test('系统显示已联网但 API 不可达时保留队列直到恢复', () async {
    final created = await sync.createDiary(
      date: '2026-09-27',
      content: '待重试',
      tags: [],
    );
    online = true;
    api.offline = false;
    api.unreachable = true;
    await expectLater(sync.refresh(), throwsA(isA<DiaryApiException>()));
    expect(await store.getOutbox(), hasLength(1));
    expect(await store.getDiary(created.id), isNotNull);
    api.unreachable = false;
    final refreshed = await sync.refresh();
    expect(refreshed.single.id, 'server-1');
    expect(await store.getOutbox(), isEmpty);
  });

  test('联网后仍可直接撤销未上传的新建日记', () async {
    final created = await sync.createDiary(
      date: '2026-09-27',
      content: '撤销新建',
      tags: [],
    );
    api.offline = false;
    online = true;
    await sync.deleteDiary(created);
    expect(await store.getDiary(created.id), isNull);
    expect(await store.getOutbox(), isEmpty);
    expect(api.remote, isEmpty);
    expect(api.calls, isEmpty);
  });

  test('联网删除前先提交本地尚未同步的查看事件', () async {
    final diary = sample('entry-id');
    api.remote[diary.id] = diary;
    await store.saveDiary(diary);
    await sync.recordView(diary);
    expect(await store.getOutbox(), hasLength(1));
    api.offline = false;
    online = true;
    await sync.deleteDiary(diary);
    expect(api.calls, ['view', 'delete']);
    expect(await store.getOutbox(), isEmpty);
    expect(await store.getDiary(diary.id), isNull);
    expect(api.remote, isEmpty);
  });

  test('查看未同步且服务器暂不可用时删除先入队，恢复后按序提交', () async {
    final diary = sample('entry-id');
    api.remote[diary.id] = diary;
    await store.saveDiary(diary);
    await sync.recordView(diary);
    online = true;
    await sync.deleteDiary(diary);
    final pending = await store.getOutbox();
    expect(pending.map((item) => item['action']), ['view', 'delete']);
    expect((await store.getDiary(diary.id))!.viewCount, 1);
    expect((await store.getDiary(diary.id))!.deletedAt, isNotNull);
    expect(api.remote.containsKey(diary.id), isTrue);

    api.offline = false;
    await sync.refresh();
    expect(api.calls, ['view', 'delete']);
    expect(await store.getOutbox(), isEmpty);
    expect(await store.getDiary(diary.id), isNull);
    expect(api.remote, isEmpty);
  });
}
