import 'dart:math';

import '../models/diary.dart';

class RandomUsage {
  const RandomUsage({required this.count, required this.lastSelectedAt});

  final int count;
  final DateTime? lastSelectedAt;

  factory RandomUsage.fromJson(Map<String, dynamic> json) => RandomUsage(
        count: (json['count'] as num?)?.toInt() ?? 0,
        lastSelectedAt:
            DateTime.tryParse(json['last_selected_at'] as String? ?? ''),
      );

  Map<String, dynamic> toJson() => {
        'count': count,
        'last_selected_at': lastSelectedAt?.toUtc().toIso8601String(),
      };
}

Map<String, RandomUsage> withRandomSelectionRecorded(
    Map<String, RandomUsage> usage, String diaryId, DateTime selectedAt) {
  final previous = usage[diaryId];
  return {
    ...usage,
    diaryId: RandomUsage(
      count: (previous?.count ?? 0) + 1,
      lastSelectedAt: selectedAt,
    ),
  };
}

class WeightedRandomSelector {
  const WeightedRandomSelector();

  Map<String, double> calculateWeights(
    List<Diary> diaries, {
    Map<String, RandomUsage> usage = const {},
    DateTime? now,
  }) {
    if (diaries.isEmpty) return const {};
    final current = now ?? DateTime.now();
    final details = diaries.map((diary) {
      final item =
          usage[diary.id] ?? const RandomUsage(count: 0, lastSelectedAt: null);
      final effectiveCount = max(diary.viewCount, item.count);
      final referenceText = item.lastSelectedAt?.toIso8601String() ??
          diary.lastViewedAt ??
          diary.date;
      final reference = DateTime.tryParse(referenceText) ?? current;
      final daysAgo = max(0, current.difference(reference).inDays);
      return _WeightDetail(
        diary: diary,
        count: effectiveCount,
        timeRaw: log(daysAgo + 1),
      );
    }).toList(growable: false);
    if (details.length == 1) return {details.single.diary.id: 0.5};

    final byTime = [...details]..sort((a, b) => a.timeRaw.compareTo(b.timeRaw));
    final byCount = [...details]..sort((a, b) => a.count.compareTo(b.count));
    final timeNorm = <String, double>{};
    final countNorm = <String, double>{};
    for (var index = 0; index < details.length; index++) {
      timeNorm[byTime[index].diary.id] = index / (details.length - 1);
      countNorm[byCount[index].diary.id] =
          (details.length - 1 - index) / (details.length - 1);
    }
    final maxCount = details.map((item) => item.count).reduce(max);
    return {
      for (final item in details)
        item.diary.id: 0.3 * timeNorm[item.diary.id]! +
            countNorm[item.diary.id]! +
            (item.count == 0 && maxCount > 0 ? 0.5 : 0),
    };
  }

  Diary? select(
    List<Diary> diaries, {
    Set<String> excluded = const {},
    Map<String, RandomUsage> usage = const {},
    Random? random,
    DateTime? now,
  }) {
    final candidates =
        diaries.where((diary) => !excluded.contains(diary.id)).toList();
    if (candidates.isEmpty) return null;
    final weights = calculateWeights(candidates, usage: usage, now: now);
    final total = weights.values.fold<double>(0, (sum, value) => sum + value);
    if (total <= 0) {
      return candidates[(random ?? Random()).nextInt(candidates.length)];
    }
    var target = (random ?? Random()).nextDouble() * total;
    for (final diary in candidates) {
      target -= weights[diary.id] ?? 0;
      if (target <= 0) {
        return diary;
      }
    }
    return candidates.last;
  }
}

class _WeightDetail {
  const _WeightDetail(
      {required this.diary, required this.count, required this.timeRaw});

  final Diary diary;
  final int count;
  final double timeRaw;
}
