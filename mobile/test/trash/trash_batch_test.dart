import 'package:diary_mobile/models/diary.dart';
import 'package:diary_mobile/trash/trash_batch.dart';
import 'package:flutter_test/flutter_test.dart';

Diary item(String id, {String date = '2026-10-03', String content = '正文'}) =>
    Diary(
        id: id,
        date: date,
        content: content,
        contentHash: '',
        version: 3,
        tags: const [],
        updatedAt: '',
        deletedAt: '2026-10-03T01:00:00Z');

void main() {
  final items = [
    item('a'),
    item('b', content: '关于天气'),
    item('c', date: '2026-09-02', content: '阅读')
  ];
  test('回收站按日期和正文关键词本地搜索，不修改原数据', () {
    expect(filterTrash(items, '2026-10 天气').map((row) => row.id), ['b']);
    expect(filterTrash(items, '阅读').map((row) => row.id), ['c']);
    expect(filterTrash(items, '').length, 3);
    expect(items.length, 3);
  });

  test('单篇失败不影响其余日记，失败可单独重试', () async {
    final calls = <String>[];
    final result = await const TrashBatchService().run(items, (diary) async {
      calls.add(diary.id);
      if (diary.id == 'b') throw StateError('单篇失败');
      return TrashOutcome.completed;
    }, isInterrupted: (_) => false);
    expect(calls, ['a', 'b', 'c']);
    expect(result.completedIds, {'a', 'c'});
    expect(result.failedIds, {'b'});
    expect(result.unprocessed, 0);
    final retry = await const TrashBatchService().run(
        items.where((diary) => result.failedIds.contains(diary.id)).toList(),
        (_) async => TrashOutcome.completed,
        isInterrupted: (_) => false);
    expect(retry.completedIds, {'b'});
  });

  test('断网停止后保留当前失败和剩余未处理项目', () async {
    final calls = <String>[];
    final result = await const TrashBatchService().run(items, (diary) async {
      calls.add(diary.id);
      if (diary.id == 'b') throw const _Interrupted();
      return TrashOutcome.completed;
    }, isInterrupted: (error) => error is _Interrupted);
    expect(calls, ['a', 'b']);
    expect(result.completed, 1);
    expect(result.failedIds, {'b'});
    expect(result.unprocessedIds, {'c'});
  });

  test('离线恢复已排队不得误报成功，剩余项目不执行', () async {
    final calls = <String>[];
    final result = await const TrashBatchService().run(items, (diary) async {
      calls.add(diary.id);
      return TrashOutcome.deferred;
    }, isInterrupted: (_) => false);
    expect(calls, ['a']);
    expect(result.completed, 0);
    expect(result.failed, 0);
    expect(result.unprocessedIds, {'a', 'b', 'c'});
  });

  test('服务端不支持版本保护时安全停止，不调用后续永久删除', () async {
    final calls = <String>[];
    final result = await const TrashBatchService().run(items, (diary) async {
      calls.add(diary.id);
      throw const _Unsupported();
    },
        isInterrupted: (_) => false,
        isUnsupported: (error) => error is _Unsupported);
    expect(calls, ['a']);
    expect(result.unsupportedVersionedDelete, isTrue);
    expect(result.failedIds, {'a'});
    expect(result.unprocessedIds, {'b', 'c'});
  });
}

class _Interrupted implements Exception {
  const _Interrupted();
}

class _Unsupported implements Exception {
  const _Unsupported();
}
