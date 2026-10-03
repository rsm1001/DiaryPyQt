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

Diary entry(
        {int version = 1,
        String content = '原始内容',
        List<String> tags = const ['原标签'],
        int views = 3,
        String? deletedAt}) =>
    Diary(
      id: 'entry',
      date: '2026-09-27',
      content: content,
      contentHash: 'hash:$content',
      version: version,
      tags: tags,
      updatedAt: '2026-09-27T12:00:00Z',
      viewCount: views,
      lastViewedAt: '2026-09-27T10:00:00Z',
      deletedAt: deletedAt,
    );

class _ConflictApi extends DiaryApi {
  _ConflictApi() : super(baseUrl: '');
  Diary remote = entry();
  bool offline = false;
  int updateCalls = 0;

  void checkOnline() {
    if (offline) throw const DiaryApiException('网络不可用', network: true);
  }

  @override
  Future<Diary> fetchDiary(String id) async {
    checkOnline();
    if (remote.deletedAt != null) {
      throw const DiaryApiException('日记已删除', statusCode: 404);
    }
    return remote;
  }

  @override
  Future<List<Diary>> fetchTrash() async {
    checkOnline();
    return remote.deletedAt != null ? [remote] : const [];
  }

  @override
  Future<Diary> updateDiary(
    Diary diary, {
    required String content,
    required List<String> tags,
  }) async {
    checkOnline();
    updateCalls++;
    if (diary.version != remote.version || remote.deletedAt != null) {
      throw const DiaryApiException('版本冲突', conflict: true, statusCode: 409);
    }
    remote = entry(
        version: remote.version + 1,
        content: content,
        tags: tags,
        views: remote.viewCount);
    return remote;
  }

  @override
  Future<void> deleteDiary(Diary diary) async {
    checkOnline();
    if (diary.version != remote.version || remote.deletedAt != null) {
      throw const DiaryApiException('删除冲突', conflict: true, statusCode: 409);
    }
    remote = entry(
        version: remote.version + 1,
        content: remote.content,
        tags: remote.tags,
        views: remote.viewCount,
        deletedAt: '2026-09-29T00:00:00Z');
  }

  @override
  Future<Diary> restoreDiary(Diary diary) async {
    checkOnline();
    if (diary.version != remote.version || remote.deletedAt == null) {
      throw const DiaryApiException('恢复冲突', conflict: true, statusCode: 409);
    }
    remote = entry(
        version: remote.version + 1,
        content: remote.content,
        tags: remote.tags,
        views: remote.viewCount);
    return remote;
  }

  @override
  Future<DiaryViewResult> recordView(
    Diary diary, {
    required String eventId,
    required String viewedAt,
  }) async {
    checkOnline();
    remote = remote.copyWith(
        viewCount: remote.viewCount + 1, lastViewedAt: viewedAt);
    return DiaryViewResult(viewCount: remote.viewCount, viewedAt: viewedAt);
  }
}

void main() {
  sqfliteFfiInit();
  late Directory directory;
  late Database database;
  late LocalStore store;
  late _ConflictApi api;
  late SyncManager sync;
  setUp(() async {
    directory = await Directory.systemTemp.createTemp('diary-conflict-test-');
    database = await databaseFactoryFfi
        .openDatabase(path.join(directory.path, 'db.sqlite'));
    await LocalStore.createSchema(database, 4);
    store = LocalStore.withDatabase(database);
    api = _ConflictApi();
    sync = SyncManager(
        api: api,
        store: store,
        checkConnectivity: () async => [ConnectivityResult.wifi]);
  });
  tearDown(() async {
    await store.close();
    api.dispose();
    await directory.delete(recursive: true);
  });

  Future<void> stageEdit() async {
    await store.saveDiary(entry());
    api.offline = true;
    await sync.updateDiary(entry(), content: '手机正文', tags: ['手机标签']);
    api.offline = false;
    api.remote = entry(version: 2, content: '电脑正文', tags: ['电脑标签']);
    await expectLater(
        sync.flushPending(),
        throwsA(isA<DiaryApiException>()
            .having((error) => error.conflict, '冲突', true)));
  }

  test('旧版数据库升级保留日记和待同步操作并建立审核表', () async {
    final legacyPath = path.join(directory.path, 'legacy.db');
    final legacy = await databaseFactoryFfi.openDatabase(legacyPath,
        options: OpenDatabaseOptions(
            version: 3,
            onCreate: (db, version) async {
              await db.execute(
                  'CREATE TABLE diaries (id TEXT PRIMARY KEY, json TEXT NOT NULL, version INTEGER NOT NULL, content_hash TEXT NOT NULL)');
              await db.execute(
                  'CREATE TABLE outbox (id INTEGER PRIMARY KEY AUTOINCREMENT, entity_id TEXT NOT NULL, action TEXT NOT NULL, base_version INTEGER, json TEXT NOT NULL)');
            }));
    final oldStore = LocalStore.withDatabase(legacy);
    await oldStore.saveDiary(entry());
    await oldStore.enqueueMutation(
        entityId: 'entry',
        action: 'update',
        baseVersion: 1,
        payload: {'content': '本地修改', 'tags': <String>[]});
    await oldStore.close();
    final upgraded = await databaseFactoryFfi.openDatabase(legacyPath,
        options: OpenDatabaseOptions(
            version: 4, onUpgrade: LocalStore.upgradeSchema));
    final reopened = LocalStore.withDatabase(upgraded);
    expect((await reopened.getDiary('entry'))!.content, '原始内容');
    expect((await reopened.getOutbox()).single['action'], 'update');
    expect(await reopened.getConflicts(), isEmpty);
    await reopened.close();
  });
  test('离线编辑与电脑端冲突可反复打开，暂不处理不变更内容和队列', () async {
    await stageEdit();
    expect((await sync.getConflicts()).single.remote!.content, '电脑正文');
    final local = (await sync.getConflicts()).single.local;
    expect(local.content, '手机正文');
    expect(local.tags, ['手机标签']);
    expect(local.version, 1);
    expect((await store.getOutbox()).single['base_version'], 1);
    await expectLater(sync.flushPending(), throwsA(isA<DiaryApiException>()));
    expect(api.updateCalls, 1);
    await store.close();
    database = await databaseFactoryFfi
        .openDatabase(path.join(directory.path, 'db.sqlite'));
    store = LocalStore.withDatabase(database);
    sync = SyncManager(api: api, store: store);
    expect((await sync.getConflicts()).single.local.content, '手机正文');
    expect((await store.getOutbox()).single['base_version'], 1);
  });

  test('采用服务器版本仅移除正文任务，保留待同步查看与最新查看统计', () async {
    await stageEdit();
    await store.recordViewLocally('entry', 'event-1', '2026-09-28T01:00:00Z');
    final conflict = (await sync.getConflicts()).single;
    await sync.resolveConflict(conflict, keepLocal: false);
    final local = (await store.getDiary('entry'))!;
    expect(local.content, '电脑正文');
    expect(local.tags, ['电脑标签']);
    expect(local.viewCount, 4);
    expect(local.lastViewedAt, '2026-09-28T01:00:00Z');
    expect((await store.getOutbox()).single['action'], 'view');
    expect(await sync.getConflicts(), isEmpty);
  });

  test('待审核正文冲突不会阻塞后续独立的幂等查看事件', () async {
    await stageEdit();
    await store.recordViewLocally(
        'entry', 'view-behind-conflict', '2026-09-28T01:00:00Z');
    await expectLater(
        sync.flushPending(),
        throwsA(isA<DiaryApiException>()
            .having((error) => error.conflict, '冲突待审核', true)));
    expect(api.remote.viewCount, 4);
    expect((await store.getDiary('entry'))!.viewCount, 4);
    expect((await store.getOutbox()).single['action'], 'update');
    expect((await sync.getConflicts()).single.local.content, '手机正文');
  });
  test('保留本地需先人工确认并更新基线，随后可重试提交', () async {
    await stageEdit();
    final conflict = (await sync.getConflicts()).single;
    await sync.resolveConflict(conflict, keepLocal: true);
    expect((await store.getDiary('entry'))!.content, '手机正文');
    expect((await store.getDiary('entry'))!.version, 2);
    expect((await store.getOutbox()).single['base_version'], 2);
    expect(api.remote.content, '电脑正文');
    await sync.flushPending();
    expect(api.remote.content, '手机正文');
    expect(api.remote.tags, ['手机标签']);
    expect(await store.getOutbox(), isEmpty);
  });

  test('用户确认前服务器再次变更则拒绝应用并更新快照', () async {
    await stageEdit();
    final conflict = (await sync.getConflicts()).single;
    api.remote = entry(version: 3, content: '电脑再次修改');
    await expectLater(sync.resolveConflict(conflict, keepLocal: false),
        throwsA(isA<StateError>()));
    expect((await store.getDiary('entry'))!.content, '手机正文');
    expect((await store.getOutbox()).single['base_version'], 1);
    expect((await sync.getConflicts()).single.remote!.version, 3);
  });

  test('远端日记已删除时只可采用删除状态，不自动复活本地编辑', () async {
    await stageEdit();
    final stale = (await sync.getConflicts()).single;
    api.remote =
        entry(version: 3, content: '电脑已删除', deletedAt: '2026-09-28T12:00:00Z');
    await expectLater(sync.resolveConflict(stale, keepLocal: false),
        throwsA(isA<StateError>()));
    final latest = (await sync.getConflicts()).single;
    expect(latest.remote!.deletedAt, isNotNull);
    await expectLater(sync.resolveConflict(latest, keepLocal: true),
        throwsA(isA<StateError>()));
    expect((await store.getDiary('entry'))!.content, '手机正文');
    await sync.resolveConflict(latest, keepLocal: false);
    expect((await store.getDiary('entry'))!.deletedAt, isNotNull);
    expect(await store.getOutbox(), isEmpty);
  });
  test('数据库出错时冲突处理全部回滚，可重新处理', () async {
    await stageEdit();
    final conflict = (await sync.getConflicts()).single;
    await database.execute(
        "CREATE TRIGGER refuse_conflict BEFORE DELETE ON diary_conflicts "
        "BEGIN SELECT RAISE(ABORT, '拒绝处理'); END");
    await expectLater(sync.resolveConflict(conflict, keepLocal: false),
        throwsA(isA<DatabaseException>()));
    expect((await store.getDiary('entry'))!.content, '手机正文');
    expect((await store.getOutbox()).single['action'], 'update');
    await database.execute('DROP TRIGGER refuse_conflict');
    await sync.resolveConflict(conflict, keepLocal: false);
    expect((await store.getDiary('entry'))!.content, '电脑正文');
  });

  test('线上编辑冲突直接保存本地编辑并等待审核', () async {
    await store.saveDiary(entry());
    api.remote = entry(version: 2, content: '电脑改动');
    final local =
        await sync.updateDiary(entry(), content: '新编辑', tags: ['新标签']);
    expect(local.content, '新编辑');
    expect((await sync.getConflicts()).single.remote!.version, 2);
    expect((await store.getOutbox()).single['action'], 'update');
  });

  test('删除冲突也保留本地意图，确认服务器后可重试', () async {
    await store.saveDiary(entry());
    api.remote = entry(version: 2, content: '电脑改动');
    await sync.deleteDiary(entry());
    expect((await sync.getConflicts()).single.action, 'delete');
    await sync.resolveConflict((await sync.getConflicts()).single,
        keepLocal: true);
    expect((await store.getOutbox()).single['base_version'], 2);
    await sync.flushPending();
    expect(await store.getDiary('entry'), isNull);
    expect(api.remote.deletedAt, isNotNull);
  });

  test('离线恢复可排队，联网后重复点击不会留下多余恢复任务', () async {
    final deleted = entry(deletedAt: '2026-09-27T20:00:00Z');
    api.remote = deleted;
    api.offline = true;
    await sync.restoreDiary(deleted);
    expect((await store.getOutbox()).single['action'], 'restore');
    expect((await store.getDiary('entry'))!.deletedAt, isNotNull);
    api.offline = false;
    await sync.restoreDiary(deleted);
    expect(await store.getOutbox(), isEmpty);
    expect((await store.getDiary('entry'))!.deletedAt, isNull);
  });

  test('远端已恢复时不再重复恢复，可确认采用服务器版本', () async {
    final deleted = entry(deletedAt: '2026-09-27T20:00:00Z');
    api.remote =
        entry(version: 2, content: '电脑墓碑', deletedAt: '2026-09-28T00:00:00Z');
    await sync.restoreDiary(deleted);
    final stale = (await sync.getConflicts()).single;
    api.remote = entry(version: 3, content: '电脑已恢复');
    await expectLater(sync.resolveConflict(stale, keepLocal: false),
        throwsA(isA<StateError>()));
    final latest = (await sync.getConflicts()).single;
    await expectLater(sync.resolveConflict(latest, keepLocal: true),
        throwsA(isA<StateError>()));
    await sync.resolveConflict(latest, keepLocal: false);
    expect(await store.getOutbox(), isEmpty);
    expect((await store.getDiary('entry'))!.content, '电脑已恢复');
  });
  test('恢复冲突保留待同步恢复与查看统计，不用查看总数推算逐日记录', () async {
    final deleted = entry(deletedAt: '2026-09-27T20:00:00Z');
    api.remote =
        entry(version: 2, content: '电脑墓碑', deletedAt: '2026-09-28T00:00:00Z');
    await sync.restoreDiary(deleted);
    expect((await sync.getConflicts()).single.action, 'restore');
    expect((await sync.getConflicts()).single.remote!.version, 2);
    expect((await store.getOutbox()).single['base_version'], 1);
    await sync.resolveConflict((await sync.getConflicts()).single,
        keepLocal: true);
    expect((await store.getOutbox()).single['base_version'], 2);
    await sync.flushPending();
    expect((await store.getDiary('entry'))!.deletedAt, isNull);
    expect(api.remote.version, 3);
  });
}
