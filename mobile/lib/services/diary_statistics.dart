import '../models/diary.dart';

class DiaryStatistics {
  const DiaryStatistics({
    required this.total,
    required this.totalCharacters,
    required this.totalViews,
    required this.activeDays,
    required this.tagCounts,
    required this.latestDate,
    required this.longestContent,
  });

  final int total;
  final int totalCharacters;
  final int totalViews;
  final int activeDays;
  final Map<String, int> tagCounts;
  final String? latestDate;
  final Diary? longestContent;
}

DiaryStatistics calculateDiaryStatistics(List<Diary> diaries) {
  final tagCounts = <String, int>{};
  final days = <String>{};
  Diary? longest;
  String? latestDate;
  var totalCharacters = 0;
  var totalViews = 0;
  for (final diary in diaries) {
    totalCharacters += diary.content.runes.length;
    totalViews += diary.viewCount;
    days.add(diary.date
        .substring(0, diary.date.length >= 10 ? 10 : diary.date.length));
    final currentLatest = latestDate;
    latestDate =
        currentLatest == null || diary.date.compareTo(currentLatest) > 0
            ? diary.date
            : currentLatest;
    final currentLongest = longest;
    if (currentLongest == null ||
        diary.content.runes.length > currentLongest.content.runes.length) {
      longest = diary;
    }
    for (final tag in diary.tags) {
      tagCounts[tag] = (tagCounts[tag] ?? 0) + 1;
    }
  }
  return DiaryStatistics(
    total: diaries.length,
    totalCharacters: totalCharacters,
    totalViews: totalViews,
    activeDays: days.length,
    tagCounts: Map.unmodifiable(tagCounts),
    latestDate: latestDate,
    longestContent: longest,
  );
}
