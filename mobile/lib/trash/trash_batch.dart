import '../models/diary.dart';

List<Diary> filterTrash(List<Diary> diaries, String query) {
  final terms = query
      .trim()
      .toLowerCase()
      .split(RegExp(r'\s+'))
      .where((term) => term.isNotEmpty)
      .toList();
  if (terms.isEmpty) return List.unmodifiable(diaries);
  return List.unmodifiable(diaries.where((diary) {
    final date = diary.date.toLowerCase();
    final content = diary.content.toLowerCase();
    return terms.every((term) => date.contains(term) || content.contains(term));
  }));
}

enum TrashOutcome { completed, deferred }

class TrashBatchResult {
  const TrashBatchResult({
    required this.completedIds,
    required this.failedIds,
    required this.unprocessedIds,
    required this.unsupportedVersionedDelete,
  });

  final Set<String> completedIds;
  final Set<String> failedIds;
  final Set<String> unprocessedIds;
  final bool unsupportedVersionedDelete;

  int get completed => completedIds.length;
  int get failed => failedIds.length;
  int get unprocessed => unprocessedIds.length;
}

class TrashBatchService {
  const TrashBatchService();

  Future<TrashBatchResult> run(
    List<Diary> diaries,
    Future<TrashOutcome> Function(Diary) action, {
    required bool Function(Object) isInterrupted,
    bool Function(Object)? isUnsupported,
    void Function(Diary, Object)? onFailure,
  }) async {
    final completed = <String>{};
    final failed = <String>{};
    final unprocessed = <String>{};
    var unsupported = false;
    for (var index = 0; index < diaries.length; index++) {
      final diary = diaries[index];
      try {
        final outcome = await action(diary);
        if (outcome == TrashOutcome.deferred) {
          unprocessed.add(diary.id);
          unprocessed.addAll(diaries.skip(index + 1).map((item) => item.id));
          break;
        }
        completed.add(diary.id);
      } catch (error) {
        onFailure?.call(diary, error);
        failed.add(diary.id);
        if (isInterrupted(error) || (isUnsupported?.call(error) ?? false)) {
          unsupported = isUnsupported?.call(error) ?? false;
          unprocessed.addAll(diaries.skip(index + 1).map((item) => item.id));
          break;
        }
      }
    }
    return TrashBatchResult(
      completedIds: Set.unmodifiable(completed),
      failedIds: Set.unmodifiable(failed),
      unprocessedIds: Set.unmodifiable(unprocessed),
      unsupportedVersionedDelete: unsupported,
    );
  }
}
