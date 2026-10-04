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
  String dateLabel(String date) =>
      english ? 'Date: $date' : '\u65e5\u671f\uff1a$date';
  String localCacheCount(int count) => english
      ? 'Local cache: $count diaries'
      : '\u672c\u5730\u7f13\u5b58\uff1a$count \u7bc7';
  String serverCount(int count) => english
      ? 'Server: $count diaries'
      : '\u670d\u52a1\u5668\uff1a$count \u7bc7';
  String get localNoDateDiaries => english
      ? 'No cached diary for this date.'
      : '\u672c\u5730\u6ca1\u6709\u7f13\u5b58\u8be5\u65e5\u671f\u7684\u65e5\u8bb0\u3002';
  String get serverHistoryDetails => english
      ? 'Server history details'
      : '\u670d\u52a1\u5668\u5386\u53f2\u660e\u7ec6';
  String get serverDateUnavailable => english
      ? 'Server date details are unavailable.'
      : '\u670d\u52a1\u5668\u65e5\u671f\u660e\u7ec6\u6682\u4e0d\u53ef\u7528\u3002';
  String get serverCacheFallback => english
      ? 'Server statistics are unavailable; showing readable local cache data.'
      : '\u670d\u52a1\u5668\u7edf\u8ba1\u4e0d\u53ef\u7528\uff1b\u4ee5\u4e0b\u5c55\u793a\u672c\u8bbe\u5907\u53ef\u8bfb\u53d6\u7684\u7f13\u5b58\u6570\u636e\u3002';
  String get serverPreviousFallback => english
      ? 'Server is unavailable; the summary below is the last successful result, not real-time data.'
      : '\u670d\u52a1\u5668\u6682\u4e0d\u53ef\u7528\uff1b\u4ee5\u4e0b\u6c47\u603b\u4e3a\u4e0a\u6b21\u6210\u529f\u83b7\u53d6\u7684\u7ed3\u679c\uff0c\u5e76\u975e\u5b9e\u65f6\u6570\u636e\u3002';
  String get loadingServerSummary => english
      ? 'Loading server summary?'
      : '\u6b63\u5728\u83b7\u53d6\u670d\u52a1\u5668\u6c47\u603b\u2026\u2026';
  String get dailyUnavailable => english
      ? 'Daily server details are unavailable; device events are not used as a substitute.'
      : '\u670d\u52a1\u5668\u6bcf\u65e5\u660e\u7ec6\u6682\u4e0d\u53ef\u7528\uff1b\u4e0d\u4f7f\u7528\u672c\u8bbe\u5907\u4e8b\u4ef6\u66ff\u4ee3\u3002';
  String get loadingDaily => english
      ? 'Loading server daily details?'
      : '\u6b63\u5728\u8bfb\u53d6\u670d\u52a1\u5668\u6bcf\u65e5\u660e\u7ec6\u2026\u2026';
  String get deviceCacheNote => english
      ? 'These statistics only cover diaries cached on this device, not the entire server.'
      : '\u4ee5\u4e0b\u7edf\u8ba1\u53ea\u8986\u76d6\u5f53\u524d\u8bbe\u5907\u5df2\u7f13\u5b58\u7684\u65e5\u8bb0\uff0c\u4e0d\u4ee3\u8868\u670d\u52a1\u5668\u5168\u90e8\u65e5\u8bb0\u3002';
  String get deviceRecordsUnavailable => english
      ? 'Device daily records failed to load. Please retry.'
      : '\u672c\u8bbe\u5907\u9010\u65e5\u8bb0\u5f55\u8bfb\u53d6\u5931\u8d25\uff0c\u8bf7\u91cd\u8bd5\u3002';
  String get loadingDeviceRecords => english
      ? 'Loading device daily records?'
      : '\u6b63\u5728\u8bfb\u53d6\u672c\u8bbe\u5907\u9010\u65e5\u8bb0\u5f55\u2026\u2026';
  String get noDeviceEvents => english
      ? 'No new device view events this month.'
      : '\u672c\u6708\u6ca1\u6709\u672c\u8bbe\u5907\u65b0\u589e\u67e5\u770b\u4e8b\u4ef6\u3002';
  String deviceEventCount(int count) => english
      ? 'New device views: $count times'
      : '\u672c\u8bbe\u5907\u65b0\u589e\u67e5\u770b $count \u6b21';
  String get statisticsSourceNote => english
      ? 'Server date details come from real view events; device events and server history are shown separately.'
      : '\u670d\u52a1\u5668\u65e5\u671f\u660e\u7ec6\u6765\u81ea\u771f\u5b9e\u67e5\u770b\u4e8b\u4ef6\uff1b\u672c\u8bbe\u5907\u65b0\u589e\u4e8b\u4ef6\u4e0e\u670d\u52a1\u5668\u5386\u53f2\u5206\u5f00\u5c55\u793a\u3002';
  String monthLabel(int year, int month) =>
      english ? '$year/$month' : '$year \u5e74 $month \u6708';
  String get pendingSync =>
      english ? 'Pending sync' : '\u5176\u4e2d\u5f85\u540c\u6b65';
  String get trashTitle => english ? 'Trash' : '\u56de\u6536\u7ad9';
  String selectedTrashCount(int count) =>
      english ? '$count selected' : '\u5df2\u9009\u62e9 $count \u7bc7';
  String get selectCurrentResults => english
      ? 'Select filtered results'
      : '\u9009\u62e9\u7b5b\u9009\u7ed3\u679c';
  String get refreshTrash =>
      english ? 'Refresh trash' : '\u5237\u65b0\u56de\u6536\u7ad9';
  String get trashSearchHint => english
      ? 'Search by date or content (space separates keywords)'
      : '\u6309\u65e5\u671f\u6216\u6b63\u6587\u641c\u7d22\uff0c\u7a7a\u683c\u5206\u9694\u5173\u952e\u8bcd';
  String get retryTrash =>
      english ? 'Retry loading' : '\u91cd\u8bd5\u8bfb\u53d6';
  String batchResult(int completed, int failed, int unprocessed) => english
      ? 'Completed $completed, failed $failed, unprocessed $unprocessed. Failed and unprocessed items can be retried.'
      : '\u6210\u529f $completed \u7bc7\uff0c\u5931\u8d25 $failed \u7bc7\uff0c\u672a\u5904\u7406 $unprocessed \u7bc7\u3002\u5931\u8d25\u548c\u672a\u5904\u7406\u9879\u76ee\u4ecd\u53ef\u5355\u72ec\u91cd\u8bd5\u3002';
  String get selectResults => english
      ? 'Select filtered results'
      : '\u9009\u62e9\u7b5b\u9009\u7ed3\u679c';
  String get clearTrash =>
      english ? 'Empty trash' : '\u6e05\u7a7a\u56de\u6536\u7ad9';
  String get batchRestore =>
      english ? 'Batch restore' : '\u6279\u91cf\u6062\u590d';
  String get batchPurge => english
      ? 'Batch permanently delete'
      : '\u6279\u91cf\u6c38\u4e45\u5220\u9664';
  String get emptyTrash =>
      english ? 'Trash is empty' : '\u56de\u6536\u7ad9\u6682\u65e0\u65e5\u8bb0';
  String get restore => english ? 'Restore' : '\u6062\u590d';
  String get purge =>
      english ? 'Permanently delete' : '\u6c38\u4e45\u5220\u9664';
  String get confirmContinue => english ? 'Continue' : '\u7ee7\u7eed';
  String clearTrashConfirm(int count) => english
      ? 'Permanently delete $count diaries from the current list. This cannot be undone. Continue?'
      : '\u5c06\u6c38\u4e45\u5220\u9664\u5f53\u524d\u5217\u8868\u4e2d\u7684 $count \u7bc7\u65e5\u8bb0\u3002\u6b64\u64cd\u4f5c\u4e0d\u53ef\u6062\u590d\uff0c\u662f\u5426\u7ee7\u7eed\uff1f';
  String get clearTrashTitle => english
      ? 'Empty the entire trash?'
      : '\u6e05\u7a7a\u6574\u4e2a\u56de\u6536\u7ad9\uff1f';
  String get confirmPurgeTitle => english
      ? 'Confirm permanent deletion'
      : '\u786e\u8ba4\u6c38\u4e45\u5220\u9664\uff1f';
  String purgeConfirm(int count) => english
      ? 'Permanently delete $count diaries. They cannot be recovered. Make sure the selection is correct.'
      : '\u5c06\u6c38\u4e45\u5220\u9664 $count \u7bc7\u65e5\u8bb0\uff0c\u65e0\u6cd5\u6062\u590d\u3002\u8bf7\u786e\u8ba4\u6ca1\u6709\u9009\u9519\u3002';
  String get confirmAgain => english
      ? 'Confirm permanent deletion again'
      : '\u518d\u6b21\u786e\u8ba4\u6c38\u4e45\u5220\u9664';
  String get typeClearToConfirm => english
      ? 'Type "EMPTY" to confirm'
      : '\u8bf7\u8f93\u5165\u201c\u6e05\u7a7a\u201d\u4ee5\u786e\u8ba4';
  String get permanentlyEmpty =>
      english ? 'Empty permanently' : '\u6c38\u4e45\u6e05\u7a7a';
  String get noMatchingTrash => english
      ? 'No matching diaries'
      : '\u6ca1\u6709\u5339\u914d\u7684\u65e5\u8bb0';
  String get trashReadError => english
      ? 'Failed to load trash; the current list was kept. Check the network and retry.'
      : '\u56de\u6536\u7ad9\u8bfb\u53d6\u5931\u8d25\uff1b\u5df2\u4fdd\u7559\u5f53\u524d\u5217\u8868\uff0c\u8bf7\u68c0\u67e5\u7f51\u7edc\u540e\u91cd\u8bd5\u3002';
  String get unsupportedDelete => english
      ? 'The version-checked delete API is unavailable or the diary was removed; remaining items were not deleted.'
      : '\u7248\u672c\u6821\u9a8c\u5220\u9664\u63a5\u53e3\u4e0d\u53ef\u7528\u6216\u65e5\u8bb0\u5df2\u88ab\u79fb\u9664\uff1b\u672a\u7ee7\u7eed\u5220\u9664\u5176\u4f59\u9879\u76ee\u3002';
  String get interruptedTrash => english
      ? 'The operation was interrupted or queued offline; remaining items were not processed. Retry later.'
      : '\u64cd\u4f5c\u4e2d\u65ad\u6216\u5df2\u79bb\u7ebf\u6392\u961f\uff0c\u5176\u4f59\u9879\u76ee\u672a\u5904\u7406\uff1b\u8bf7\u7a0d\u540e\u91cd\u8bd5\u3002';
  String get restoreConflict => english
      ? 'A restore version conflict requires manual review.'
      : '\u6062\u590d\u7248\u672c\u51b2\u7a81\uff0c\u7b49\u5f85\u4eba\u5de5\u5ba1\u6838';
}
