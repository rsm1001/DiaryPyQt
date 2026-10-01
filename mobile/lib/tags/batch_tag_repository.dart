import 'dart:convert';

import '../models/diary.dart';
import '../services/local_store.dart';
import 'batch_tag_policy.dart';

extension BatchTagRepository on LocalStore {
  Future<int> batchUpdateTags(
    Set<String> diaryIds,
    List<String> tags,
    BatchTagMode mode,
  ) async {
    if (diaryIds.isEmpty) return 0;
    final db = await database;
    return db.transaction((transaction) async {
      final rows = await transaction.query('diaries');
      final current = {
        for (final row in rows)
          row['id'] as String: Diary.fromJson(Map<String, dynamic>.from(
              jsonDecode(row['json'] as String) as Map)),
      };
      if (diaryIds
          .any((id) => current[id] == null || current[id]!.deletedAt != null)) {
        throw StateError('Selected diary is missing or deleted');
      }
      var changed = 0;
      for (final id in diaryIds) {
        final diary = current[id]!;
        final nextTags = applyBatchTags(diary.tags, tags, mode);
        if (nextTags.toSet().containsAll(diary.tags) &&
            diary.tags.toSet().containsAll(nextTags)) {
          continue;
        }
        final existing = await transaction.query('outbox',
            where: 'entity_id = ? AND action != ?',
            whereArgs: [id, 'view'],
            orderBy: 'id ASC',
            limit: 1);
        if (existing.isNotEmpty &&
            existing.first['action'] != 'create' &&
            existing.first['action'] != 'update') {
          throw StateError('Selected diary has an incompatible mutation');
        }
        if (id.startsWith('local-') &&
            (existing.isEmpty || existing.first['action'] != 'create')) {
          throw StateError('Local diary has no pending create');
        }
        final updated = Diary(
          id: diary.id,
          date: diary.date,
          content: diary.content,
          contentHash: diary.contentHash,
          version: diary.version,
          tags: nextTags,
          updatedAt: DateTime.now().toUtc().toIso8601String(),
          viewCount: diary.viewCount,
          lastViewedAt: diary.lastViewedAt,
          deletedAt: diary.deletedAt,
        );
        await transaction.update(
            'diaries', {'json': jsonEncode(updated.toJson())},
            where: 'id = ?', whereArgs: [id]);
        if (existing.isEmpty) {
          await transaction.insert('outbox', {
            'entity_id': id,
            'action': 'update',
            'base_version': diary.version,
            'json': jsonEncode({'content': diary.content, 'tags': nextTags}),
          });
        } else {
          final pending = existing.first;
          final payload = Map<String, dynamic>.from(
              jsonDecode(pending['json'] as String) as Map);
          await transaction.update(
              'outbox',
              {
                'json': jsonEncode({...payload, 'tags': nextTags})
              },
              where: 'id = ?',
              whereArgs: [pending['id']]);
        }
        changed++;
      }
      return changed;
    });
  }
}
