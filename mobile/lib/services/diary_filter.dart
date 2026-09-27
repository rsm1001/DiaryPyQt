import '../models/diary.dart';

List<Diary> filterDiaries(List<Diary> diaries, String query, String? tagName) {
  final needle = query.trim().toLowerCase();
  return diaries.where((diary) {
    if (tagName != null && !diary.tags.contains(tagName)) return false;
    if (needle.isEmpty) return true;
    return diary.date.toLowerCase().contains(needle) ||
        diary.content.toLowerCase().contains(needle) ||
        diary.tags.any((tag) => tag.toLowerCase().contains(needle));
  }).toList(growable: false);
}
