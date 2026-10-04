import 'app_strings.dart';

extension AppStringsStatistics on AppStrings {
  String dailyLiveAt(DateTime fetchedAt) => english
      ? 'Live server history (UTC fetched ${fetchedAt.toIso8601String()})'
      : '\u670d\u52a1\u5668\u5b9e\u65f6\u5386\u53f2\u660e\u7ec6\uff08\u83b7\u53d6\u4e8e UTC ${fetchedAt.toIso8601String()}\uff09';

  String dailyCacheAt(DateTime fetchedAt) => english
      ? 'Offline server history cache (UTC fetched ${fetchedAt.toIso8601String()}); not real-time.'
      : '\u79bb\u7ebf\u670d\u52a1\u5668\u5386\u53f2\u7f13\u5b58\uff08\u83b7\u53d6\u4e8e UTC ${fetchedAt.toIso8601String()}\uff09\uff0c\u975e\u5b9e\u65f6\u6570\u636e\u3002';

  String get dailyCacheHint => english
      ? 'Server daily details could not refresh; showing only the previously cached server events.'
      : '\u670d\u52a1\u5668\u6bcf\u65e5\u660e\u7ec6\u5237\u65b0\u5931\u8d25\uff1b\u4ec5\u663e\u793a\u4e4b\u524d\u7f13\u5b58\u7684\u670d\u52a1\u5668\u4e8b\u4ef6\u3002';

  String get loadingCalendarDate => english
      ? 'Loading server diaries for this date...'
      : '\u6b63\u5728\u8bfb\u53d6\u8be5\u65e5\u671f\u7684\u670d\u52a1\u5668\u65e5\u8bb0\u2026\u2026';
  String get yesterdayServerViews => english
      ? 'Yesterday server views (UTC)'
      : '\u6628\u65e5\u670d\u52a1\u5668\u67e5\u770b\uff08UTC\uff09';

  String get bestServerDay => english
      ? 'All-time best day (server UTC)'
      : '\u670d\u52a1\u5668\u5386\u53f2\u6700\u4f73\u5355\u65e5\uff08UTC\uff09';

  String bestServerDayValue(String? date, int views) => date == null
      ? (english
          ? 'No recorded events'
          : '\u6682\u65e0\u8bb0\u5f55\u4e8b\u4ef6')
      : '$date · ${count(views, timesUnit)}';

  String get dailyHistoryUnavailable => english
      ? 'Server history summary is unavailable.'
      : '\u670d\u52a1\u5668\u5386\u53f2\u6c47\u603b\u660e\u7ec6\u6682\u4e0d\u53ef\u7528\u3002';
}
