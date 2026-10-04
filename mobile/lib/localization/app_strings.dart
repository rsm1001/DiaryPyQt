export 'app_strings_extra.dart';
export 'app_strings_playback.dart';
export 'app_strings_transfer.dart';
export 'app_strings_calendar.dart';

import 'package:flutter/widgets.dart';

class AppStrings {
  const AppStrings._(this.english);

  final bool english;

  static AppStrings of(BuildContext context) =>
      AppStrings._(Localizations.localeOf(context).languageCode == 'en');

  String get appTitle => 'DiaryPyQt';
  String get diary => english ? 'Diary' : '\u65e5\u8bb0';
  String get newDiary => english ? 'New diary' : '\u65b0\u5efa\u65e5\u8bb0';
  String get refresh => english ? 'Refresh' : '\u5237\u65b0';
  String get retry => english ? 'Retry' : '\u91cd\u8bd5';
  String get serverSettings =>
      english ? 'Server settings' : '\u670d\u52a1\u5668\u8bbe\u7f6e';
  String get moreTools => english ? 'More tools' : '\u66f4\u591a\u5de5\u5177';
  String get cancel => english ? 'Cancel' : '\u53d6\u6d88';
  String get save => english ? 'Save' : '\u4fdd\u5b58';
  String get close => english ? 'Close' : '\u5173\u95ed';
  String get search => english ? 'Advanced search' : '\u9ad8\u7ea7\u641c\u7d22';
  String get transfer =>
      english ? 'Import / Export' : '\u5bfc\u5165 / \u5bfc\u51fa';
  String get tags => english ? 'Tag management' : '\u6807\u7b7e\u7ba1\u7406';
  String get trash => english ? 'Trash' : '\u56de\u6536\u7ad9';
  String get voices =>
      english ? 'Voice packages' : '\u8bed\u97f3\u5305\u9009\u62e9';
  String get conflicts =>
      english ? 'Sync conflicts' : '\u540c\u6b65\u51b2\u7a81\u5ba1\u6838';
  String get randomDelete =>
      english ? 'Random deletion' : '\u968f\u673a\u5220\u9664';
  String get statistics => english ? 'Statistics' : '\u7edf\u8ba1';
  String get preferences => english
      ? 'Theme, language and list'
      : '\u4e3b\u9898\u3001\u8bed\u8a00\u4e0e\u5217\u8868\u663e\u793a';
  String get batchTag => english ? 'Batch tag' : '\u6279\u91cf\u6807\u7b7e';
  String get batchDelete =>
      english ? 'Batch delete' : '\u6279\u91cf\u5220\u9664';
  String get playRandom => english
      ? 'Play random continuously'
      : '\u968f\u673a\u8fde\u7eed\u64ad\u653e';
  String get pausePlayback =>
      english ? 'Pause playback' : '\u6682\u505c\u6717\u8bfb';
  String get playPlayback =>
      english ? 'Play playback' : '\u64ad\u653e\u6717\u8bfb';
  String get searchHint => english
      ? 'Search date, content or tags (space separates keywords)'
      : '\u641c\u7d22\u65e5\u671f\u3001\u6b63\u6587\u6216\u6807\u7b7e\uff08\u7a7a\u683c\u5206\u9694\u591a\u4e2a\u5173\u952e\u8bcd\uff09';
  String get allTags => english ? 'All tags' : '\u5168\u90e8\u6807\u7b7e';
  String get clearFilters =>
      english ? 'Clear all filters' : '\u6e05\u9664\u5168\u90e8\u7b5b\u9009';
  String get noCachedDiaries => english
      ? 'No cached diaries'
      : '\u6682\u65e0\u5df2\u7f13\u5b58\u7684\u65e5\u8bb0';
  String get noMatchingDiaries => english
      ? 'No matching diaries'
      : '\u6ca1\u6709\u5339\u914d\u7684\u65e5\u8bb0';
  String get hiddenFields => english
      ? 'List fields are hidden'
      : '\u5217\u8868\u5b57\u6bb5\u5df2\u9690\u85cf';
  String viewed(int count) =>
      english ? 'Viewed $count times' : '\u67e5\u770b $count \u6b21';
  String selectedCount(int count) =>
      english ? '$count selected' : '\u5df2\u9009\u62e9 $count \u7bc7';
  String version(int value) => 'v$value';
  String get playingFirst => english ? 'Playing 1/2' : '\u64ad\u653e 1/2';
  String get playingSecond => english ? 'Playing 2/2' : '\u64ad\u653e 2/2';
  String get buffering => english ? 'Buffering' : '\u7f13\u51b2\u4e2d';
  String waiting(int seconds) =>
      english ? 'Waiting $seconds s' : '\u7b49\u5f85 $seconds \u79d2';
  String get paused => english ? 'Paused' : '\u5df2\u6682\u505c';
  String get completed => english ? 'Completed' : '\u5df2\u5b8c\u6210';
  String get ready => english ? 'Ready' : '\u5c31\u7eea';
  String get settingsTitle => english
      ? 'Theme, language and list display'
      : '\u4e3b\u9898\u3001\u8bed\u8a00\u4e0e\u5217\u8868\u663e\u793a';
  String get theme => english ? 'Theme' : '\u4e3b\u9898';
  String get themeMode => english ? 'Theme mode' : '\u4e3b\u9898\u6a21\u5f0f';
  String get systemTheme =>
      english ? 'Follow system' : '\u8ddf\u968f\u7cfb\u7edf';
  String get lightTheme => english ? 'Light' : '\u6d45\u8272';
  String get darkTheme => english ? 'Dark' : '\u6df1\u8272';
  String get language => english ? 'Language' : '\u8bed\u8a00';
  String get interfaceLanguage =>
      english ? 'Interface language' : '\u754c\u9762\u8bed\u8a00';
  String get chinese => '\u7b80\u4f53\u4e2d\u6587';
  String get listFields => english ? 'List fields' : '\u5217\u8868\u5b57\u6bb5';
  String get showDate => english ? 'Show date' : '\u663e\u793a\u65e5\u671f';
  String get showViews =>
      english ? 'Show view count' : '\u663e\u793a\u67e5\u770b\u6b21\u6570';
  String get showTags => english ? 'Show tags' : '\u663e\u793a\u6807\u7b7e';
  String get showPreview =>
      english ? 'Show content preview' : '\u663e\u793a\u6b63\u6587\u6458\u8981';
  String get sortField => english ? 'Sort field' : '\u6392\u5e8f\u5b57\u6bb5';
  String get diaryDate => english ? 'Diary date' : '\u65e5\u8bb0\u65e5\u671f';
  String get viewCount => english ? 'View count' : '\u67e5\u770b\u6b21\u6570';
  String get descending => english ? 'Descending' : '\u964d\u5e8f\u6392\u5217';
  String get preferencesNote => english
      ? 'These settings only affect this device and do not modify diary content, statistics or sync tasks.'
      : '\u8fd9\u4e9b\u8bbe\u7f6e\u53ea\u5f71\u54cd\u672c\u673a\u754c\u9762\uff0c\u4e0d\u4f1a\u4fee\u6539\u65e5\u8bb0\u5185\u5bb9\u3001\u67e5\u770b\u7edf\u8ba1\u6216\u540c\u6b65\u4efb\u52a1\u3002';
  String get statsTitle => english
      ? 'Statistics and dates'
      : '\u7edf\u8ba1\u4e0e\u65e5\u671f\u5206\u5e03';
  String get serverSummary =>
      english ? 'Server summary' : '\u670d\u52a1\u5668\u6c47\u603b';
  String get serverDailyDetails => english
      ? 'Server daily history'
      : '\u670d\u52a1\u5668\u5386\u53f2\u65e5\u671f\u660e\u7ec6';
  String get deviceCache =>
      english ? 'Current device cache' : '\u5f53\u524d\u8bbe\u5907\u7f13\u5b58';
  String get heatmap =>
      english ? 'Date heatmap' : '\u65e5\u671f\u70ed\u529b\u56fe';
  String get previousMonth => english ? 'Previous month' : '\u4e0a\u4e2a\u6708';
  String get nextMonth => english ? 'Next month' : '\u4e0b\u4e2a\u6708';
  String get serverDiaries =>
      english ? 'Server diaries' : '\u670d\u52a1\u5668\u65e5\u8bb0';
  String get serverViews =>
      english ? 'Server views' : '\u670d\u52a1\u5668\u67e5\u770b\u6b21\u6570';
  String get serverAverageViews => english
      ? 'Server average views'
      : '\u670d\u52a1\u5668\u5e73\u5747\u67e5\u770b';
  String get mostViewed => english ? 'Most viewed' : '\u6700\u591a\u67e5\u770b';
  String get leastViewed =>
      english ? 'Least viewed' : '\u6700\u5c11\u67e5\u770b';
  String get serverDailyEvents => english
      ? 'Server events this month'
      : '\u672c\u6708\u670d\u52a1\u5668\u67e5\u770b\u4e8b\u4ef6';
  String get activeDays => english ? 'Active days' : '\u6d3b\u8dc3\u65e5\u671f';
  String get cachedDiaries =>
      english ? 'Cached diaries' : '\u7f13\u5b58\u65e5\u8bb0';
  String get contentCharacters =>
      english ? 'Content characters' : '\u6b63\u6587\u5b57\u7b26';
  String get cachedViews =>
      english ? 'Cached views' : '\u7f13\u5b58\u67e5\u770b\u603b\u6570';
  String get latestDate => english ? 'Latest date' : '\u6700\u8fd1\u65e5\u671f';
  String get tagUsage =>
      english ? 'Tag usage' : '\u6807\u7b7e\u4f7f\u7528\u6b21\u6570';
  String get longestDiary =>
      english ? 'Longest diary' : '\u6700\u957f\u65e5\u8bb0';
  String get noData => english ? 'None' : '\u65e0';
  String get noTags => english ? 'No tags' : '\u6682\u65e0\u6807\u7b7e';
  String get noCachedDiary =>
      english ? 'No cached diary' : '\u6682\u65e0\u7f13\u5b58\u65e5\u8bb0';
  String count(int value, String unit) => '$value $unit';
  String get diaryUnit => english ? 'diaries' : '\u7bc7';
  String get timesUnit => english ? 'times' : '\u6b21';
  String get dayUnit => english ? 'days' : '\u5929';
  String get characterUnit => english ? 'characters' : '\u4e2a';
}
