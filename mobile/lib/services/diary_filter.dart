import '../models/diary.dart';

class DiarySearchOptions {
  const DiarySearchOptions({
    this.from,
    this.to,
    this.minViews,
    this.maxViews,
    this.tags = const [],
  });

  final DateTime? from;
  final DateTime? to;
  final int? minViews;
  final int? maxViews;
  final List<String> tags;

  bool get isActive =>
      from != null ||
      to != null ||
      minViews != null ||
      maxViews != null ||
      tags.isNotEmpty;
}

List<String> diarySearchTerms(String query) => query
    .trim()
    .toLowerCase()
    .split(RegExp(r'\s+'))
    .where((term) => term.isNotEmpty)
    .toSet()
    .toList(growable: false);

bool diaryMatchesSearch(
  Diary diary,
  List<String> terms,
  String? tagName,
  DiarySearchOptions options,
) {
  if (tagName != null && !diary.tags.contains(tagName)) return false;
  if (options.tags.any((tag) => !diary.tags.contains(tag))) return false;
  if (options.minViews != null && diary.viewCount < options.minViews!) {
    return false;
  }
  if (options.maxViews != null && diary.viewCount > options.maxViews!) {
    return false;
  }
  if (options.from != null || options.to != null) {
    final date = DateTime.tryParse(diary.date);
    if (date == null) return false;
    final day = DateTime(date.year, date.month, date.day);
    if (options.from != null && day.isBefore(options.from!)) return false;
    if (options.to != null && day.isAfter(options.to!)) return false;
  }
  final date = diary.date.toLowerCase();
  final content = diary.content.toLowerCase();
  final tags = diary.tags.map((tag) => tag.toLowerCase()).toList();
  return terms.every((term) =>
      date.contains(term) ||
      content.contains(term) ||
      tags.any((tag) => tag.contains(term)));
}

List<Diary> filterDiaries(
  List<Diary> diaries,
  String query,
  String? tagName, {
  DiarySearchOptions options = const DiarySearchOptions(),
}) {
  final terms = diarySearchTerms(query);
  return diaries
      .where((diary) => diaryMatchesSearch(diary, terms, tagName, options))
      .toList(growable: false);
}
