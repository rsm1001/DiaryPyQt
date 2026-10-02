import '../models/diary.dart';
import '../services/diary_filter.dart';

class DiarySearchIndex {
  DiarySearchIndex(List<Diary> diaries)
      : _diaries = List.unmodifiable(diaries) {
    for (var i = 0; i < _diaries.length; i++) {
      final diary = _diaries[i];
      final text =
          '${diary.date}\u0000${diary.content}\u0000${diary.tags.join('\u0000')}'
              .toLowerCase();
      for (final gram in _grams(text)) {
        _terms.putIfAbsent(gram, () => <int>{}).add(i);
      }
      for (final tag in diary.tags) {
        _tags.putIfAbsent(tag, () => <int>{}).add(i);
      }
      final date = DateTime.tryParse(diary.date);
      if (date != null) {
        _dates.add((
          DateTime(date.year, date.month, date.day).millisecondsSinceEpoch,
          i
        ));
      }
      _views.add((diary.viewCount, i));
    }
    _dates.sort((a, b) => a.$1.compareTo(b.$1));
    _views.sort((a, b) => a.$1.compareTo(b.$1));
  }

  final List<Diary> _diaries;
  final Map<String, Set<int>> _terms = {};
  final Map<String, Set<int>> _tags = {};
  final List<(int, int)> _dates = [];
  final List<(int, int)> _views = [];

  static Set<String> _grams(String text) {
    final found = <String>{};
    for (var length = 1; length <= 3; length++) {
      for (var i = 0; i <= text.length - length; i++) {
        found.add(text.substring(i, i + length));
      }
    }
    return found;
  }

  static int _lowerBound(List<(int, int)> sorted, int value) {
    var low = 0;
    var high = sorted.length;
    while (low < high) {
      final middle = (low + high) ~/ 2;
      if (sorted[middle].$1 < value) {
        low = middle + 1;
      } else {
        high = middle;
      }
    }
    return low;
  }

  Set<int> _range(List<(int, int)> sorted, int? minimum, int? maximum) {
    final start = minimum == null ? 0 : _lowerBound(sorted, minimum);
    final end =
        maximum == null ? sorted.length : _lowerBound(sorted, maximum + 1);
    if (end <= start) return {};
    return {for (var i = start; i < end; i++) sorted[i].$2};
  }

  List<Diary> search(
    String query,
    String? selectedTag, {
    DiarySearchOptions options = const DiarySearchOptions(),
  }) {
    final terms = diarySearchTerms(query);
    Set<int>? candidates;
    void intersect(Set<int> ids) {
      if (candidates == null) {
        candidates = Set.of(ids);
      } else {
        candidates!.retainAll(ids);
      }
    }

    for (final term in terms) {
      final length = term.length < 3 ? term.length : 3;
      for (var i = 0; i <= term.length - length; i++) {
        intersect(_terms[term.substring(i, i + length)] ?? const {});
        if (candidates!.isEmpty) return const [];
      }
    }
    for (final tag in <String>{
      ...options.tags,
      if (selectedTag != null) selectedTag
    }) {
      intersect(_tags[tag] ?? const {});
      if (candidates!.isEmpty) return const [];
    }
    if (options.from != null || options.to != null) {
      final start = options.from == null
          ? null
          : DateTime(options.from!.year, options.from!.month, options.from!.day)
              .millisecondsSinceEpoch;
      final end = options.to == null
          ? null
          : DateTime(options.to!.year, options.to!.month, options.to!.day)
              .millisecondsSinceEpoch;
      intersect(_range(_dates, start, end));
      if (candidates!.isEmpty) return const [];
    }
    if (options.minViews != null || options.maxViews != null) {
      intersect(_range(_views, options.minViews, options.maxViews));
      if (candidates!.isEmpty) return const [];
    }
    if (candidates == null) return _diaries;
    final indices = candidates!.toList()..sort();
    return indices
        .map((index) => _diaries[index])
        .where(
            (diary) => diaryMatchesSearch(diary, terms, selectedTag, options))
        .toList(growable: false);
  }
}
