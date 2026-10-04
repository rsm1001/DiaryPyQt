import 'app_strings.dart';

extension AppStringsTransfer on AppStrings {
  String integrityPassed(int pending, int conflicts) => english
      ? 'Local database integrity verified; $pending pending sync tasks, $conflicts conflicts for review.'
      : '\u672c\u5730\u6570\u636e\u5e93\u5b8c\u6574\u6027\u68c0\u67e5\u901a\u8fc7\uff1b\u5f85\u540c\u6b65 $pending \u6761\uff0c\u5f85\u5ba1\u6838\u51b2\u7a81 $conflicts \u6761\u3002';
  String get integrityUnhealthy => english
      ? 'Local database integrity check failed. Export a backup and stop writing data.'
      : '\u672c\u5730\u6570\u636e\u5e93\u5b8c\u6574\u6027\u68c0\u67e5\u672a\u901a\u8fc7\uff0c\u8bf7\u5148\u5bfc\u51fa\u5907\u4efd\u5e76\u505c\u6b62\u5199\u5165\u3002';
  String get integrityCheckFailed => english
      ? 'Failed to check local database integrity.'
      : '\u672c\u5730\u6570\u636e\u5e93\u5b8c\u6574\u6027\u68c0\u67e5\u5931\u8d25\u3002';
  String backupExported(int count) => english
      ? 'Local backup exported: $count diaries'
      : '\u5df2\u5bfc\u51fa\u672c\u5730\u5907\u4efd\uff1a$count \u7bc7\u65e5\u8bb0';
  String get backupExportFailed => english
      ? 'Local backup export failed. Check file permissions.'
      : '\u672c\u5730\u5907\u4efd\u5bfc\u51fa\u5931\u8d25\uff0c\u8bf7\u68c0\u67e5\u6587\u4ef6\u6743\u9650\u3002';
  String get confirmRestore =>
      english ? 'Confirm restore' : '\u786e\u8ba4\u6062\u590d';
  String restorePreview(int diaries, int pending, int conflicts, int playback,
          bool hasLocalPending) =>
      english
          ? 'Backup preview: $diaries diaries, $pending pending sync tasks, '
              '$conflicts conflicts, $playback playback records. '
              '${hasLocalPending ? 'This device has pending sync tasks or conflicts! ' : ''}'
              'Restoring replaces local data and requires the same server. '
              'The backup contains plaintext diary content; store it safely. Continue?'
          : '\u5907\u4efd\u9884\u89c8\uff1a$diaries \u7bc7\u65e5\u8bb0\uff0c'
              '$pending \u6761\u5f85\u540c\u6b65\u4efb\u52a1\uff0c$conflicts \u6761\u51b2\u7a81\uff0c'
              '$playback \u6761\u64ad\u653e\u8bb0\u5f55\u3002'
              '${hasLocalPending ? '\u5f53\u524d\u8bbe\u5907\u6709\u672a\u540c\u6b65\u4efb\u52a1\u6216\u5f85\u5ba1\u6838\u51b2\u7a81\uff01' : ''}'
              '\u6062\u590d\u4f1a\u66ff\u6362\u672c\u5730\u6570\u636e\uff0c\u53ea\u80fd\u7528\u4e8e\u539f\u670d\u52a1\u5668\uff1b'
              '\u5907\u4efd\u6587\u4ef6\u5305\u542b\u660e\u6587\u65e5\u8bb0\uff0c\u8bf7\u59a5\u5584\u4fdd\u7ba1\u3002\u662f\u5426\u7ee7\u7eed\uff1f';
  String restoreCompleted(int diaries, int pending, int conflicts) => english
      ? 'Restore complete: $diaries diaries, $pending pending sync tasks, $conflicts conflicts.'
      : '\u6062\u590d\u5b8c\u6210\uff1a$diaries \u7bc7\u65e5\u8bb0\uff0c$pending \u6761\u5f85\u540c\u6b65\u4efb\u52a1\uff0c$conflicts \u6761\u51b2\u7a81\u3002';
  String get restoreRefreshFailed => english
      ? 'Local data restored, but the list failed to refresh. Refresh manually.'
      : '\u672c\u5730\u6570\u636e\u5df2\u6062\u590d\uff0c\u4f46\u5217\u8868\u5237\u65b0\u5931\u8d25\uff0c\u8bf7\u624b\u52a8\u5237\u65b0\u3002';
  String get restoreFailed => english
      ? 'Local backup restore failed. Existing local data was kept.'
      : '\u672c\u5730\u5907\u4efd\u6062\u590d\u5931\u8d25\uff0c\u539f\u6709\u672c\u5730\u6570\u636e\u5df2\u4fdd\u7559\u3002';
  String diariesExported(int count) => english
      ? 'Exported $count diaries'
      : '\u5df2\u5bfc\u51fa $count \u7bc7\u65e5\u8bb0';
  String get exportFailed => english
      ? 'Export failed. Check file permissions.'
      : '\u5bfc\u51fa\u5931\u8d25\uff0c\u8bf7\u68c0\u67e5\u6587\u4ef6\u6743\u9650';
  String importPreview(int ready, int skipped, int errors) => english
      ? 'Can create $ready diaries; skipped $skipped duplicates; $errors errors.\n'
          'Only date, content and tags are imported; old view counts are not re-imported.'
          '${errors > 0 ? '\nFix invalid rows before retrying; no data has been written.' : ''}'
      : '\u53ef\u65b0\u5efa $ready \u7bc7\uff0c\u8df3\u8fc7 $skipped \u7bc7\u91cd\u590d\uff0c\u9519\u8bef $errors \u7bc7\u3002\n'
          '\u4ec5\u5bfc\u5165\u65e5\u671f\u3001\u6b63\u6587\u548c\u6807\u7b7e\uff1b\u5386\u53f2\u67e5\u770b\u6b21\u6570\u4e0d\u4f1a\u88ab\u91cd\u590d\u5bfc\u5165\u3002'
          '${errors > 0 ? '\n\u8bf7\u4fee\u590d\u9519\u8bef\u884c\u540e\u91cd\u65b0\u5bfc\u5165\uff0c\u6574\u6279\u6570\u636e\u5c1a\u672a\u5199\u5165\u3002' : ''}';
  String diariesImported(int count) => english
      ? 'Imported $count diaries; the rest were skipped'
      : '\u5df2\u5bfc\u5165 $count \u7bc7\uff0c\u5176\u4f59\u5df2\u8df3\u8fc7';
  String get importFailed => english
      ? 'Import failed. Check the file format and size.'
      : '\u5bfc\u5165\u5931\u8d25\uff1a\u8bf7\u68c0\u67e5\u6587\u4ef6\u683c\u5f0f\u548c\u5927\u5c0f';
}
