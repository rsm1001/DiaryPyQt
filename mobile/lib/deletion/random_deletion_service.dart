import 'dart:math';

import '../models/diary.dart';
import '../services/local_store.dart';
import '../services/sync_manager.dart';
import 'random_deletion_policy.dart';

enum RandomDeletionResult { confirmed, queued, conflict }

class RandomDeletionService {
  const RandomDeletionService(
      {required this.store,
      required this.sync,
      this.policy = const RandomDeletionPolicy()});

  final LocalStore store;
  final SyncManager sync;
  final RandomDeletionPolicy policy;

  Future<List<Diary>> candidates({
    DeletionFilters filters = const DeletionFilters(),
    Set<String> excluded = const {},
    DateTime? now,
  }) async {
    final diaries = await store.getDiaries();
    final pending = await store.getOutbox();
    final lockedIds = pending
        .where((item) => item['action'] != 'view')
        .map((item) => item['entity_id'] as String)
        .toSet();
    lockedIds.addAll((await store.getConflicts()).map((item) => item.diaryId));
    return policy.candidates(diaries,
        filters: filters, excluded: {...excluded, ...lockedIds}, now: now);
  }

  Future<Diary?> draw({
    DeletionFilters filters = const DeletionFilters(),
    Set<String> excluded = const {},
    DateTime? now,
    Random? random,
  }) async =>
      policy.draw(
          await candidates(filters: filters, excluded: excluded, now: now),
          now: now,
          random: random);

  Future<RandomDeletionResult> moveToTrash(Diary preview) async {
    final current = await store.getDiary(preview.id);
    if (current == null ||
        current.deletedAt != null ||
        current.version != preview.version ||
        current.date != preview.date ||
        current.contentHash != preview.contentHash ||
        current.content != preview.content ||
        current.updatedAt != preview.updatedAt ||
        current.viewCount != preview.viewCount ||
        current.lastViewedAt != preview.lastViewedAt ||
        !_sameTags(current.tags, preview.tags)) {
      throw StateError('候选日记已变化，请重新抽取并确认');
    }
    final pending = await store.getOutbox();
    if (pending.any((item) =>
            item['entity_id'] == preview.id && item['action'] != 'view') ||
        await store.hasConflict(preview.id)) {
      throw StateError('日记存在其他待同步修改，需先处理');
    }
    await sync.deleteDiary(current);
    if (await store.hasConflict(preview.id)) {
      return RandomDeletionResult.conflict;
    }
    final after = await store.getOutbox();
    if (after.any((item) =>
        item['entity_id'] == preview.id && item['action'] == 'delete')) {
      return RandomDeletionResult.queued;
    }
    if (await store.getDiary(preview.id) != null) {
      throw StateError('删除状态不确定，已停止操作');
    }
    return RandomDeletionResult.confirmed;
  }

  bool _sameTags(List<String> left, List<String> right) =>
      left.length == right.length && left.toSet().containsAll(right);
}
