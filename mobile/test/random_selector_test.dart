import 'package:diary_mobile/models/diary.dart';
import 'package:diary_mobile/services/random_selector.dart';
import 'package:flutter_test/flutter_test.dart';

Diary diary(String id, String date) => Diary(
      id: id,
      date: date,
      content: id,
      contentHash: 'sha256:$id',
      version: 1,
      tags: const [],
      updatedAt: date,
    );

void main() {
  test('随机权重优先冷却时间长且使用次数少的日记', () {
    const selector = WeightedRandomSelector();
    final diaries = [
      diary('old-unused', '2020-01-01'),
      diary('recent-used', '2026-09-26'),
    ];
    final weights = selector.calculateWeights(
      diaries,
      usage: {
        'old-unused': const RandomUsage(count: 0, lastSelectedAt: null),
        'recent-used':
            RandomUsage(count: 4, lastSelectedAt: DateTime(2026, 9, 25)),
      },
      now: DateTime(2026, 9, 26),
    );
    expect(weights['old-unused'], greaterThan(weights['recent-used'] ?? 0));
  });

  test('排除集合用于构建不重复的播放队列', () {
    const selector = WeightedRandomSelector();
    final diaries = [diary('a', '2026-09-20'), diary('b', '2026-09-21')];
    expect(selector.select(diaries, excluded: {'a'})?.id, 'b');
    expect(selector.select(diaries, excluded: {'a', 'b'}), isNull);
  });
  test('??????????????????', () {
    const selector = WeightedRandomSelector();
    final old = diary('old', '2020-01-01');
    final recent = Diary(
      id: 'recent',
      date: '2020-01-01',
      content: 'recent',
      contentHash: 'sha256:recent',
      version: 1,
      tags: const [],
      updatedAt: '2026-09-26T00:00:00Z',
      viewCount: 5,
      lastViewedAt: '2026-09-26T00:00:00Z',
    );
    final weights = selector.calculateWeights(
      [old, recent],
      now: DateTime(2026, 9, 27),
    );
    expect(weights['old'], greaterThan(weights['recent'] ?? 0));
  });
}
