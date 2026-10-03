import 'dart:math';

import '../models/diary.dart';

class DeletionFilters {
  const DeletionFilters({this.before, this.minViews, this.maxViews, this.tag});

  final DateTime? before;
  final int? minViews;
  final int? maxViews;
  final String? tag;

  bool get isValid =>
      (minViews == null || minViews! >= 0) &&
      (maxViews == null || maxViews! >= 0) &&
      (minViews == null || maxViews == null || minViews! <= maxViews!);
}

class RandomDeletionPolicy {
  const RandomDeletionPolicy();

  List<Diary> candidates(
    List<Diary> diaries, {
    DeletionFilters filters = const DeletionFilters(),
    Set<String> excluded = const {},
    DateTime? now,
  }) {
    if (!filters.isValid) throw const FormatException('查看次数筛选范围无效');
    final current = now ?? DateTime.now();
    final today = DateTime(current.year, current.month, current.day);
    final upper = filters.before == null
        ? today
        : DateTime(
            filters.before!.year, filters.before!.month, filters.before!.day);
    return List.unmodifiable(diaries.where((diary) {
      final parsed = DateTime.tryParse(diary.date);
      if (parsed == null ||
          diary.deletedAt != null ||
          diary.id.startsWith('local-') ||
          excluded.contains(diary.id)) {
        return false;
      }
      final day = DateTime(parsed.year, parsed.month, parsed.day);
      return !day.isAfter(today) &&
          !day.isAfter(upper) &&
          (filters.minViews == null || diary.viewCount >= filters.minViews!) &&
          (filters.maxViews == null || diary.viewCount <= filters.maxViews!) &&
          (filters.tag == null || diary.tags.contains(filters.tag));
    }));
  }

  Map<String, double> weights(List<Diary> diaries, {DateTime? now}) {
    if (diaries.isEmpty) return const {};
    final current = now ?? DateTime.now();
    final today = DateTime(current.year, current.month, current.day);
    final ages = <String, double>{};
    final views = <String, double>{};
    for (final diary in diaries) {
      final date = DateTime.tryParse(diary.date);
      if (date == null) throw const FormatException('候选日记日期无效');
      final day = DateTime(date.year, date.month, date.day);
      ages[diary.id] = log(max(0, today.difference(day).inDays) + 1);
      views[diary.id] = sqrt(max(0, diary.viewCount));
    }
    final ageRank = _ranks(ages);
    final viewRank = _ranks(views);
    // 删除权重只依赖日期和查看次数，不读取随机播放历史。
    return Map.unmodifiable({
      for (final diary in diaries)
        diary.id: 0.6 * ageRank[diary.id]! + 0.4 * viewRank[diary.id]!,
    });
  }

  Map<String, double> _ranks(Map<String, double> values) {
    final ordered = values.entries.toList()
      ..sort((a, b) => a.value.compareTo(b.value));
    if (ordered.length == 1) return {ordered.single.key: 0.5};
    final ranks = <String, double>{};
    for (var start = 0; start < ordered.length;) {
      var end = start + 1;
      while (
          end < ordered.length && ordered[end].value == ordered[start].value) {
        end++;
      }
      final rank = (start + end - 1) / (2 * (ordered.length - 1));
      for (var index = start; index < end; index++) {
        ranks[ordered[index].key] = rank;
      }
      start = end;
    }
    return ranks;
  }

  Diary? draw(List<Diary> diaries, {DateTime? now, Random? random}) {
    if (diaries.isEmpty) return null;
    final weightsById = weights(diaries, now: now);
    final total =
        weightsById.values.fold<double>(0, (sum, value) => sum + value);
    final generator = random ?? Random();
    if (total <= 0) return diaries[generator.nextInt(diaries.length)];
    var target = generator.nextDouble() * total;
    for (final diary in diaries) {
      target -= weightsById[diary.id]!;
      if (target < 0) return diary;
    }
    return diaries.last;
  }
}
