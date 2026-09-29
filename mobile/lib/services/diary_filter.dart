import '../models/diary.dart';

class DiarySearchOptions {
  const DiarySearchOptions({
    this.from,
    this.to,
    this.minViews,
    this.maxViews,
  });

  final DateTime? from;
  final DateTime? to;
  final int? minViews;
  final int? maxViews;

  bool get isActive =>
      from != null || to != null || minViews != null || maxViews != null;
}

List<Diary> filterDiaries(
  List<Diary> diaries,
  String query,
  String? tagName, {
  DiarySearchOptions options = const DiarySearchOptions(),
}) {
  final needle = query.trim().toLowerCase();
  return diaries.where((diary) {
    if (tagName != null && !diary.tags.contains(tagName)) return false;
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
    if (needle.isEmpty) return true;
    return diary.date.toLowerCase().contains(needle) ||
        diary.content.toLowerCase().contains(needle) ||
        diary.tags.any((tag) => tag.toLowerCase().contains(needle));
  }).toList(growable: false);
}
