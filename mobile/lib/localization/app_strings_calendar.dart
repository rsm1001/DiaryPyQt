import 'app_strings.dart';

extension AppStringsCalendar on AppStrings {
  String heatmapLegend({required bool hasServerHistory}) => hasServerHistory
      ? (english
          ? 'Color shows server history; bold dates show new device views; dots show locally cached diaries.'
          : '\u989c\u8272\u8868\u793a\u670d\u52a1\u5668\u5386\u53f2\u67e5\u770b\uff0c\u7c97\u4f53\u6570\u5b57\u8868\u793a\u672c\u8bbe\u5907\u65b0\u589e\u67e5\u770b\uff0c\u5706\u70b9\u8868\u793a\u672c\u5730\u7f13\u5b58\u65e5\u8bb0\u3002')
      : (english
          ? 'Color shows new device views; dots show the dates of locally cached diaries.'
          : '\u989c\u8272\u8868\u793a\u672c\u8bbe\u5907\u65b0\u589e\u67e5\u770b\uff0c\u5706\u70b9\u8868\u793a\u672c\u5730\u7f13\u5b58\u65e5\u8bb0\u7684\u521b\u5efa\u65e5\u671f\u3002');

  List<String> get weekdays => english
      ? const ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
      : const [
          '\u4e00',
          '\u4e8c',
          '\u4e09',
          '\u56db',
          '\u4e94',
          '\u516d',
          '\u65e5'
        ];

  String heatmapDescription(
    String date,
    int serverCount,
    int deviceCount,
    int cachedCount,
  ) =>
      english
          ? '$date: $serverCount server views, $deviceCount new device views, $cachedCount cached diaries'
          : '$date\uff1a\u670d\u52a1\u5668\u67e5\u770b $serverCount \u6b21\uff0c\u672c\u8bbe\u5907\u65b0\u589e\u67e5\u770b $deviceCount \u6b21\uff0c\u7f13\u5b58\u65e5\u8bb0 $cachedCount \u7bc7';
}
