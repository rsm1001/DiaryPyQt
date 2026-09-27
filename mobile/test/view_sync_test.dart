import 'dart:convert';

import 'package:diary_mobile/models/diary.dart';
import 'package:diary_mobile/models/diary_view_result.dart';
import 'package:diary_mobile/services/diary_api.dart';
import 'package:diary_mobile/services/local_store.dart';
import 'package:diary_mobile/services/sync_manager.dart';
import 'package:flutter_test/flutter_test.dart';

Diary sample(String id) => Diary(
      id: id,
      date: '2026-09-27',
      content: 'sample',
      contentHash: 'sha256:sample',
      version: 1,
      tags: const [],
      updatedAt: '2026-09-27T00:00:00Z',
    );

class MemoryStore extends LocalStore {
  MemoryStore(this.diary);
  Diary diary;
  final pending = <Map<String, dynamic>>[];

  @override
  Future<int> recordViewLocally(String diaryId, String eventId, String viewedAt) async {
    final id = pending.length + 1;
    pending.add({
      'id': id,
      'entity_id': diaryId,
      'action': 'view',
      'json': jsonEncode({'event_id': eventId, 'viewed_at': viewedAt}),
    });
    diary = diary.copyWith(viewCount: diary.viewCount + 1, lastViewedAt: viewedAt);
    return id;
  }

  @override
  Future<List<Map<String, dynamic>>> getOutbox() async => List.of(pending);

  @override
  Future<Diary?> getDiary(String id) async => diary.id == id ? diary : null;

  @override
  Future<void> confirmView(int id, String diaryId, DiaryViewResult result) async {
    diary = diary.copyWith(viewCount: result.viewCount, lastViewedAt: result.viewedAt);
    pending.removeWhere((item) => item['id'] == id);
  }

  @override
  Future<void> replaceLocalId(String temporaryId, Diary created, int outboxId) async {
    diary = created.copyWith(viewCount: diary.viewCount, lastViewedAt: diary.lastViewedAt);
    for (final item in pending) {
      if (item['entity_id'] == temporaryId) item['entity_id'] = created.id;
    }
    pending.removeWhere((item) => item['id'] == outboxId);
  }
}

class MemoryApi extends DiaryApi {
  MemoryApi() : super(baseUrl: 'https://example.invalid');
  final seen = <String>{};
  final requestedIds = <String>[];
  bool loseFirstResponse = false;

  @override
  Future<DiaryViewResult> recordView(Diary diary,
      {required String eventId, required String viewedAt}) async {
    requestedIds.add(diary.id);
    seen.add(eventId);
    if (loseFirstResponse) {
      loseFirstResponse = false;
      throw const DiaryApiException('Offline after commit', network: true);
    }
    return DiaryViewResult(viewCount: seen.length, viewedAt: viewedAt);
  }

  @override
  Future<Diary> createDiary({required String date, required String content,
      required List<String> tags}) async => sample('server-id');
}

void main() {
  test('lost acknowledgement retries the same view event', () async {
    final store = MemoryStore(sample('server-id'));
    final api = MemoryApi()..loseFirstResponse = true;
    final sync = SyncManager(api: api, store: store);
    await sync.recordView(store.diary);
    expect(store.diary.viewCount, 1);
    expect(store.pending, hasLength(1));
    final eventId = jsonDecode(store.pending.first['json'] as String)['event_id'];
    await sync.flushPending();
    expect(api.seen, {eventId});
    expect(store.pending, isEmpty);
    expect(store.diary.viewCount, 1);
    api.dispose();
  });

  test('view of temporary diary waits for server ID', () async {
    final store = MemoryStore(sample('local-1'));
    store.pending.add({
      'id': 1,
      'entity_id': 'local-1',
      'action': 'create',
      'json': jsonEncode({'date': '2026-09-27', 'content': 'sample', 'tags': []}),
    });
    final api = MemoryApi();
    final sync = SyncManager(api: api, store: store);
    await sync.recordView(store.diary);
    expect(api.seen, isEmpty);
    await sync.flushPending();
    expect(api.requestedIds, ['server-id']);
    expect(store.diary.viewCount, 1);
    expect(store.pending, isEmpty);
    api.dispose();
  });
}