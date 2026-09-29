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
  test('records selection on an immutable empty usage map', () {
    final firstAt = DateTime.utc(2026, 9, 27);
    final secondAt = firstAt.add(const Duration(minutes: 1));
    final first = withRandomSelectionRecorded(const {}, 'a', firstAt);
    final second = withRandomSelectionRecorded(first, 'a', secondAt);
    expect(first['a']!.count, 1);
    expect(second['a']!.count, 2);
    expect(second['a']!.lastSelectedAt, secondAt);
    expect(first['a']!.lastSelectedAt, firstAt);
  });

  test('????????????????', () {
    const selector = WeightedRandomSelector();
    final now = DateTime.utc(2026, 9, 27, 12);
    final equalA = diary('a', '2020-01-01').copyWith(viewCount: 2);
    final equalB = diary('b', '2020-01-01').copyWith(viewCount: 2);
    final recent = diary('c', '2026-09-27').copyWith(
      viewCount: 8,
      lastViewedAt: now.toIso8601String(),
    );
    final weights =
        selector.calculateWeights([equalA, recent, equalB], now: now);
    expect(weights['a'], weights['b']);
    expect(weights['a'], greaterThan(weights['c'] ?? 0));
  });

  test('?????????????????????', () {
    const selector = WeightedRandomSelector();
    final now = DateTime.utc(2026, 9, 27, 12);
    for (final count in [0, 5]) {
      final items = [
        diary('a', '2020-01-01').copyWith(viewCount: count),
        diary('b', '2020-01-01').copyWith(viewCount: count),
        diary('c', '2020-01-01').copyWith(viewCount: count),
      ];
      final weights = selector.calculateWeights(items, now: now);
      final reversed =
          selector.calculateWeights(items.reversed.toList(), now: now);
      expect(weights.values.toSet(), hasLength(1));
      expect(weights.values.first, greaterThan(0));
      expect(reversed, weights);
    }
  });

  test('?????????????????????', () {
    const selector = WeightedRandomSelector();
    final now = DateTime.utc(2026, 9, 27, 12);
    final monthAgo = now.subtract(const Duration(days: 30));
    final current = diary('recent', '2020-01-01').copyWith(
      viewCount: 3,
      lastViewedAt: now.subtract(const Duration(minutes: 1)).toIso8601String(),
    );
    final old = diary('old', '2020-01-01').copyWith(
      viewCount: 3,
      lastViewedAt: monthAgo.toIso8601String(),
    );
    final weights = selector.calculateWeights(
      [current, old],
      usage: {'recent': RandomUsage(count: 1, lastSelectedAt: monthAgo)},
      now: now,
    );
    expect(weights['old'], greaterThan(weights['recent'] ?? 0));
  });

  test('??????????????????????', () {
    const selector = WeightedRandomSelector();
    final now = DateTime.utc(2026, 9, 27, 12);
    final monthAgo = now.subtract(const Duration(days: 30));
    final current = diary('recent', '2020-01-01').copyWith(
      viewCount: 3,
      lastViewedAt: monthAgo.toIso8601String(),
    );
    final old = diary('old', '2020-01-01').copyWith(
      viewCount: 3,
      lastViewedAt: monthAgo.toIso8601String(),
    );
    final weights = selector.calculateWeights(
      [current, old],
      usage: {
        'recent': RandomUsage(
          count: 1,
          lastSelectedAt: now.subtract(const Duration(minutes: 1)),
        ),
      },
      now: now,
    );
    expect(weights['old'], greaterThan(weights['recent'] ?? 0));
  });
}
