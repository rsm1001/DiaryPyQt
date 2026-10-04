import 'app_strings.dart';

extension AppStringsExtra on AppStrings {
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
  String get connectServer => english
      ? 'Connect diary server'
      : '\u8fde\u63a5\u65e5\u8bb0\u670d\u52a1\u5668';
  String get serverAddress =>
      english ? 'Server address' : '\u670d\u52a1\u5668\u5730\u5740';
  String get connectionPassword =>
      english ? 'Connection password' : '\u8fde\u63a5\u5bc6\u7801';
  String get savedPasswordHint => english
      ? 'Use the password from the desktop connection file'
      : '\u4f7f\u7528\u7535\u8111\u8fde\u63a5\u6587\u4ef6\u4e2d\u7684\u5bc6\u7801';
  String get httpsNote => english
      ? 'Use HTTPS for public connections; leaving the password empty keeps the saved password for the same server.'
      : '\u516c\u7f51\u8fde\u63a5\u8bf7\u4f7f\u7528 HTTPS\uff1b\u7559\u7a7a\u5bc6\u7801\u53ef\u4fdd\u7559\u540c\u4e00\u670d\u52a1\u5668\u7684\u5df2\u5b58\u5bc6\u7801\u3002';
  String get testAndSave =>
      english ? 'Test and save' : '\u6d4b\u8bd5\u5e76\u4fdd\u5b58';
  String get invalidServerUrl => english
      ? 'Enter an HTTPS URL without a path; HTTP is only allowed for trusted private-network endpoints.'
      : '\u8bf7\u8f93\u5165\u4e0d\u542b\u8def\u5f84\u7684 HTTPS \u5730\u5740\uff1bHTTP \u4ec5\u5141\u8bb8\u4fe1\u4efb\u7684\u79c1\u7f51\u5165\u53e3';
  String get tagManagement =>
      english ? 'Tag management' : '\u6807\u7b7e\u7ba1\u7406';
  String get createTag => english ? 'New tag' : '\u65b0\u5efa\u6807\u7b7e';
  String get renameTag =>
      english ? 'Rename tag' : '\u91cd\u547d\u540d\u6807\u7b7e';
  String get name => english ? 'Name' : '\u540d\u79f0';
  String get createTagFailed =>
      english ? 'Failed to create tag' : '\u521b\u5efa\u6807\u7b7e\u5931\u8d25';
  String get renameTagFailed => english
      ? 'Rename failed; the tag may be duplicated or the network is unavailable.'
      : '\u91cd\u547d\u540d\u5931\u8d25\uff1b\u6807\u7b7e\u91cd\u590d\u6216\u4ecd\u6709\u7f51\u7edc\u95ee\u9898';
  String get deleteTagTitle =>
      english ? 'Delete tag?' : '\u5220\u9664\u6807\u7b7e\uff1f';
  String deleteTagMessage(String tag) => english
      ? 'Delete ?$tag?? Tags in use cannot be deleted.'
      : '\u786e\u5b9a\u5220\u9664\u201c$tag\u201d\uff1f\u6b63\u5728\u4f7f\u7528\u7684\u6807\u7b7e\u4e0d\u80fd\u5220\u9664\u3002';
  String get deleteTagFailed => english
      ? 'Delete failed; tags in use cannot be deleted.'
      : '\u5220\u9664\u5931\u8d25\uff1b\u6b63\u5728\u4f7f\u7528\u7684\u6807\u7b7e\u4e0d\u80fd\u5220\u9664';
  String get noTagsAvailable =>
      english ? 'No tags' : '\u6682\u65e0\u6807\u7b7e';
  String get rename => english ? 'Rename' : '\u91cd\u547d\u540d';
  String get create => english ? 'Create' : '\u521b\u5efa';
  String get conflictReview =>
      english ? 'Sync conflict review' : '\u540c\u6b65\u51b2\u7a81\u5ba1\u6838';
  String get refreshConflicts =>
      english ? 'Refresh conflicts' : '\u5237\u65b0\u51b2\u7a81\u5217\u8868';
  String get conflictLoadFailed => english
      ? 'Failed to load conflicts. Please retry.'
      : '\u8bfb\u53d6\u51b2\u7a81\u5217\u8868\u5931\u8d25\uff0c\u8bf7\u91cd\u8bd5\u3002';
  String get noConflicts => english
      ? 'No pending sync conflicts.'
      : '\u6682\u65e0\u5f85\u5ba1\u6838\u7684\u540c\u6b65\u51b2\u7a81\u3002';
  String get serverVersionUpdated => english
      ? 'Server version updated. Please review again.'
      : '\u670d\u52a1\u5668\u7248\u672c\u5df2\u66f4\u65b0\uff0c\u8bf7\u91cd\u65b0\u6838\u5bf9\u3002';
  String get serverVersionUnavailable => english
      ? 'Unable to get the server version; local content was kept.'
      : '\u6682\u65f6\u65e0\u6cd5\u83b7\u53d6\u670d\u52a1\u5668\u7248\u672c\uff0c\u5df2\u4fdd\u7559\u672c\u5730\u5185\u5bb9\u3002';
  String get keepLocalTitle => english
      ? 'Keep local version?'
      : '\u786e\u8ba4\u4fdd\u7559\u672c\u5730\u7248\u672c\uff1f';
  String get useServerTitle => english
      ? 'Use server version?'
      : '\u786e\u8ba4\u91c7\u7528\u670d\u52a1\u5668\u7248\u672c\uff1f';
  String get keepLocalMessage => english
      ? 'Resubmit local content and tags based on the current server version. Review both sides first.'
      : '\u5c06\u57fa\u4e8e\u5f53\u524d\u670d\u52a1\u5668\u7248\u672c\u91cd\u65b0\u63d0\u4ea4\u672c\u5730\u6b63\u6587\u4e0e\u6807\u7b7e\uff1b\u8bf7\u5148\u786e\u8ba4\u4e24\u7aef\u5dee\u5f02\u3002';
  String get useServerMessage => english
      ? 'Discard the pending local edit or restore operation. Device view events and statistics remain independent.'
      : '\u5c06\u4e22\u5f03\u5f53\u524d\u5f85\u540c\u6b65\u7684\u6b63\u6587\u6216\u6062\u590d\u64cd\u4f5c\uff1b\u672c\u8bbe\u5907\u67e5\u770b\u4e8b\u4ef6\u548c\u7edf\u8ba1\u4fdd\u6301\u72ec\u7acb\u3002';
  String get confirm => english ? 'Confirm' : '\u786e\u8ba4';
  String get conflictHandled => english
      ? 'Conflict handled. Check sync status.'
      : '\u5df2\u5904\u7406\u51b2\u7a81\uff0c\u8bf7\u67e5\u770b\u540c\u6b65\u72b6\u6001\u3002';
  String get conflictRefreshFailed => english
      ? 'Conflict handled, but list refresh failed. Please refresh manually.'
      : '\u51b2\u7a81\u5df2\u5904\u7406\uff0c\u5217\u8868\u5237\u65b0\u5931\u8d25\uff0c\u8bf7\u624b\u52a8\u5237\u65b0\u3002';
  String get conflictHandleFailed => english
      ? 'Handling failed or the version changed. Review and retry.'
      : '\u5904\u7406\u5931\u8d25\u6216\u7248\u672c\u5df2\u53d8\u5316\uff0c\u8bf7\u91cd\u65b0\u6838\u5bf9\u540e\u91cd\u8bd5\u3002';
  String get conflictDeferred => english
      ? 'Deferred; local content and pending tasks were unchanged.'
      : '\u5df2\u6682\u4e0d\u5904\u7406\uff0c\u672c\u5730\u5185\u5bb9\u4e0e\u5f85\u540c\u6b65\u4efb\u52a1\u4fdd\u6301\u4e0d\u53d8\u3002';
  String versionLabel(String side, int version) =>
      english ? '$side version $version' : '$side\u7248\u672c $version';
  String updatedLabel(String value) =>
      english ? 'Updated: $value' : '\u66f4\u65b0\uff1a$value';
  String tagsLabel(String value) =>
      english ? 'Tags: $value' : '\u6807\u7b7e\uff1a$value';
  String summaryLabel(String value) => english
      ? 'Content preview: $value'
      : '\u6b63\u6587\u6458\u8981\uff1a$value';
  String get unknown => english ? 'Unknown' : '\u672a\u77e5';
  String get none => english ? 'None' : '\u65e0';
  String get deletedOrRestoring => english
      ? 'Deleted or waiting for restore'
      : '\u5df2\u5220\u9664\u6216\u7b49\u5f85\u6062\u590d';
  String get serverUnavailableBeforeReview => english
      ? 'Server version unavailable; refresh it before handling this conflict.'
      : '\u670d\u52a1\u5668\u7248\u672c\u6682\u4e0d\u53ef\u7528\uff1b\u91cd\u65b0\u83b7\u53d6\u524d\u4e0d\u80fd\u5904\u7406\u51b2\u7a81\u3002';
  String conflictTitle(String date, String action) => '$date ? $action';
  String get restoreAction => english ? 'Restore' : '\u6062\u590d';
  String get editAction => english ? 'Edit' : '\u7f16\u8f91';
  String get deleteAction => english ? 'Delete' : '\u5220\u9664';
  String get serverDeletedWarning => english
      ? 'The server deleted this diary; only the server state can be used, local edits cannot be restored automatically.'
      : '\u670d\u52a1\u5668\u5df2\u5220\u9664\u8be5\u65e5\u8bb0\uff1b\u53ea\u80fd\u91c7\u7528\u670d\u52a1\u5668\u72b6\u6001\uff0c\u4e0d\u80fd\u81ea\u52a8\u6062\u590d\u672c\u5730\u7f16\u8f91\u3002';
  String get serverRestoredWarning => english
      ? 'The server restored this diary; no duplicate restore submission is needed.'
      : '\u670d\u52a1\u5668\u5df2\u6062\u590d\u8be5\u65e5\u8bb0\uff1b\u65e0\u9700\u91cd\u590d\u63d0\u4ea4\u6062\u590d\u64cd\u4f5c\u3002';
  String get refreshServerVersion => english
      ? 'Refresh server version'
      : '\u5237\u65b0\u670d\u52a1\u5668\u7248\u672c';
  String get deferConflict => english ? 'Defer' : '\u6682\u4e0d\u5904\u7406';
  String get keepLocal => english ? 'Keep local' : '\u4fdd\u7559\u672c\u5730';
  String get useServer =>
      english ? 'Use server' : '\u91c7\u7528\u670d\u52a1\u5668';
  String get voiceSelection =>
      english ? 'Select voice package' : '\u9009\u62e9\u8bed\u97f3\u5305';
  String get refreshVoices =>
      english ? 'Refresh voice packages' : '\u5237\u65b0\u8bed\u97f3\u5305';
  String get noVoices => english
      ? 'No voice packages on the server; current setting kept.'
      : '\u670d\u52a1\u5668\u6682\u65e0\u53ef\u9009\u8bed\u97f3\u5305\uff0c\u4fdd\u7559\u5f53\u524d\u8bbe\u7f6e\u3002';
  String get voicesUnavailable => english
      ? 'Voice packages unavailable; current setting kept.'
      : '\u8bed\u97f3\u5305\u5217\u8868\u4e0d\u53ef\u7528\uff0c\u4fdd\u7559\u5f53\u524d\u8bbe\u7f6e\u3002';
  String get saveVoiceFailed => english
      ? 'Failed to save voice package. Please retry.'
      : '\u4fdd\u5b58\u8bed\u97f3\u5305\u5931\u8d25\uff0c\u8bf7\u91cd\u8bd5\u3002';
  String get currentSetting =>
      english ? 'Current setting' : '\u5f53\u524d\u8bbe\u7f6e';
  String get defaultVoice => english
      ? 'Server default voice'
      : '\u670d\u52a1\u5668\u9ed8\u8ba4\u8bed\u97f3\u5305';
  String voiceId(String id) => english
      ? 'Voice package ID: $id'
      : '\u8bed\u97f3\u5305\u7f16\u53f7\uff1a$id';
  String get useDefaultVoice => english
      ? 'Use server default voice'
      : '\u4f7f\u7528\u670d\u52a1\u5668\u9ed8\u8ba4\u8bed\u97f3\u5305';
  String voiceOffline(bool supported) => supported
      ? (english
          ? 'Offline supported; uncached generation still needs network'
          : '\u8bed\u97f3\u5305\u652f\u6301\u79bb\u7ebf\uff0c\u672a\u7f13\u5b58\u4ecd\u9700\u8054\u7f51\u751f\u6210')
      : (english
          ? 'Network required when uncached'
          : '\u672a\u7f13\u5b58\u9700\u8054\u7f51\u751f\u6210');
  String get voiceNote => english
      ? 'Switching voice packages does not delete cached audio or create view events.'
      : '\u5207\u6362\u8bed\u97f3\u5305\u4e0d\u5220\u9664\u5df2\u7f13\u5b58\u97f3\u9891\uff0c\u4e5f\u4e0d\u4f1a\u4ea7\u751f\u67e5\u770b\u6b21\u6570\u3002';
  String get newDiaryTitle =>
      english ? 'New diary' : '\u65b0\u5efa\u65e5\u8bb0';
  String get editDiaryTitle =>
      english ? 'Edit diary' : '\u7f16\u8f91\u65e5\u8bb0';
  String dateText(String date) =>
      english ? 'Date: $date' : '\u65e5\u671f\uff1a$date';
  String get newDiaryDateHint => english
      ? 'Choose a date for a new diary'
      : '\u65b0\u65e5\u8bb0\u53ef\u9009\u62e9\u65e5\u671f';
  String get existingDiaryDateHint => english
      ? 'The creation date of an existing diary cannot be changed'
      : '\u5df2\u6709\u65e5\u8bb0\u7684\u521b\u5efa\u65e5\u671f\u4e0d\u4fee\u6539';
  String get content => english ? 'Content' : '\u6b63\u6587';
  String get tagsField => english ? 'Tags' : '\u6807\u7b7e';
  String get tagsHint => english
      ? 'Separate multiple tags with commas'
      : '\u7528\u9017\u53f7\u5206\u9694\u591a\u4e2a\u6807\u7b7e';
  String get saveDiary => english ? 'Save' : '\u4fdd\u5b58';
  String get deleteDiary =>
      english ? 'Delete diary' : '\u5220\u9664\u65e5\u8bb0';
  String get contentRequired => english
      ? 'Content cannot be empty'
      : '\u6b63\u6587\u4e0d\u80fd\u4e3a\u7a7a';
  String get diarySaveFailed => english
      ? 'Save failed. Check the network; for a version conflict, refresh before editing.'
      : '\u4fdd\u5b58\u5931\u8d25\uff0c\u8bf7\u68c0\u67e5\u7f51\u7edc\uff1b\u7248\u672c\u51b2\u7a81\u65f6\u5148\u5237\u65b0\u518d\u7f16\u8f91';
  String get deleteDiaryTitle =>
      english ? 'Delete diary?' : '\u5220\u9664\u65e5\u8bb0\uff1f';
  String get deleteDiaryMessage => english
      ? 'This diary will be moved to the server trash. Make sure there are no unsaved changes.'
      : '\u8fd9\u7bc7\u65e5\u8bb0\u4f1a\u88ab\u79fb\u5230\u670d\u52a1\u5668\u56de\u6536\u72b6\u6001\uff1b\u8bf7\u786e\u8ba4\u6ca1\u6709\u672a\u4fdd\u5b58\u7684\u66f4\u6539\u3002';
  String get diaryDeleteFailed => english
      ? 'Delete failed. Check the network; for a version conflict, refresh first.'
      : '\u5220\u9664\u5931\u8d25\uff0c\u8bf7\u68c0\u67e5\u7f51\u7edc\uff1b\u7248\u672c\u51b2\u7a81\u65f6\u5148\u5237\u65b0';
  String get advancedSearch =>
      english ? 'Advanced search' : '\u9ad8\u7ea7\u641c\u7d22';
  String get minimumViews =>
      english ? 'Minimum views' : '\u6700\u5c11\u67e5\u770b\u6b21\u6570';
  String get maximumViews =>
      english ? 'Maximum views' : '\u6700\u591a\u67e5\u770b\u6b21\u6570';
  String get clearAdvancedConditions => english
      ? 'Clear advanced conditions'
      : '\u6e05\u9664\u9ad8\u7ea7\u6761\u4ef6';
  String get apply => english ? 'Apply' : '\u5e94\u7528';
  String get filterTags => english ? 'Filter tags' : '\u6807\u7b7e\u7b5b\u9009';
  String batchTags(int count) => english
      ? 'Batch tags ($count)'
      : '\u6279\u91cf\u6807\u7b7e\uff08$count \u7bc7\uff09';
  String get addTags => english ? 'Add' : '\u6dfb\u52a0';
  String get removeTags => english ? 'Remove' : '\u79fb\u9664';
  String get replaceTags => english ? 'Replace' : '\u66ff\u6362';
  String get tagsCommaHint => english
      ? 'Tags (comma separated)'
      : '\u6807\u7b7e\uff08\u9017\u53f7\u5206\u9694\uff09';
  String get tagsRequired => english
      ? 'Select or enter tags'
      : '\u8bf7\u9009\u62e9\u6216\u8f93\u5165\u6807\u7b7e';
  String get replaceTagsNote => english
      ? 'Replace removes old tags not selected; leave empty to clear all.'
      : '\u66ff\u6362\u4f1a\u79fb\u9664\u672a\u9009\u4e2d\u7684\u65e7\u6807\u7b7e\uff1b\u7559\u7a7a\u8868\u793a\u6e05\u7a7a\u3002';
  String get dateRangeInvalid => english
      ? 'Check the date and view-count ranges.'
      : '\u8bf7\u68c0\u67e5\u65e5\u671f\u4e0e\u6b21\u6570\u8303\u56f4';
  String get startDateUnlimited =>
      english ? 'No start date limit' : '\u5f00\u59cb\u65e5\u671f\u4e0d\u9650';
  String get endDateUnlimited =>
      english ? 'No end date limit' : '\u7ed3\u675f\u65e5\u671f\u4e0d\u9650';
  String startDate(String date) =>
      english ? 'Start: $date' : '\u5f00\u59cb\uff1a$date';
  String endDate(String date) =>
      english ? 'End: $date' : '\u7ed3\u675f\uff1a$date';
  String get tagsAllRequired => english
      ? 'Tag combination (all selected tags required)'
      : '\u6807\u7b7e\u7ec4\u5408\uff08\u987b\u5305\u542b\u6240\u6709\u9009\u4e2d\u6807\u7b7e\uff09';
  String get transferTitle => english
      ? 'Diary import and export'
      : '\u65e5\u8bb0\u5bfc\u5165\u5bfc\u51fa';
  String get checkIntegrity => english
      ? 'Check local database integrity'
      : '\u68c0\u67e5\u672c\u5730\u6570\u636e\u5e93\u5b8c\u6574\u6027';
  String get integrityNote => english
      ? 'A failed check does not modify local data'
      : '\u68c0\u67e5\u5931\u8d25\u4e0d\u4f1a\u4fee\u6539\u672c\u5730\u6570\u636e';
  String get exportBackup => english
      ? 'Export full local backup'
      : '\u5bfc\u51fa\u672c\u5730\u5b8c\u6574\u5907\u4efd';
  String get exportBackupNote => english
      ? 'Includes diaries, sync queue and playback records; excludes audio, address and password'
      : '\u4fdd\u5b58\u65e5\u8bb0\u3001\u540c\u6b65\u961f\u5217\u548c\u64ad\u653e\u8bb0\u5f55\uff1b\u4e0d\u542b\u97f3\u9891\u3001\u5730\u5740\u53ca\u5bc6\u7801';
  String get restoreBackup => english
      ? 'Restore full local backup'
      : '\u6062\u590d\u672c\u5730\u5b8c\u6574\u5907\u4efd';
  String get restoreBackupNote => english
      ? 'Validate the file before restore; failures roll back automatically'
      : '\u6062\u590d\u524d\u6821\u9a8c\u6587\u4ef6\uff1b\u5931\u8d25\u65f6\u81ea\u52a8\u56de\u6eda';
  String get exportJson =>
      english ? 'Export JSON diaries' : '\u5bfc\u51fa JSON \u65e5\u8bb0';
  String get exportJsonNote => english
      ? 'Export cached diaries, including view counts'
      : '\u5bfc\u51fa\u5f53\u524d\u7f13\u5b58\u7684\u65e5\u8bb0\uff0c\u5305\u542b\u67e5\u770b\u6b21\u6570';
  String get importJson =>
      english ? 'Import from JSON' : '\u4ece JSON \u5bfc\u5165';
  String get importJsonNote => english
      ? 'Create non-duplicate diaries; offline sync is supported'
      : '\u65b0\u5efa\u4e0d\u91cd\u590d\u7684\u65e5\u8bb0\uff0c\u652f\u6301\u65ad\u7f51\u5f85\u540c\u6b65';
  String get exportCsv => english ? 'Export CSV' : '\u5bfc\u51fa CSV';
  String get exportCsvNote => english
      ? 'Export local diaries with desktop-compatible CSV fields'
      : '\u5bfc\u51fa\u672c\u5730\u65e5\u8bb0\uff0c\u4e0e\u7535\u8111\u7aef CSV \u5b57\u6bb5\u517c\u5bb9';
  String get importCsv =>
      english ? 'Import from CSV' : '\u4ece CSV \u5bfc\u5165';
  String get importCsvNote => english
      ? 'Preview before import; reject the whole batch if any row is invalid'
      : '\u5148\u9884\u89c8\u518d\u5bfc\u5165\uff1b\u6709\u9519\u8bef\u884c\u65f6\u6574\u6279\u62d2\u7edd';
  String get transferNote => english
      ? 'Imports do not overwrite existing diaries or old IDs/view history. CSV is not a database backup.'
      : '\u5bfc\u5165\u4e0d\u8986\u76d6\u5df2\u6709\u65e5\u8bb0\uff0c\u4e0d\u5bfc\u5165\u65e7 ID \u6216\u5386\u53f2\u67e5\u770b\u7edf\u8ba1\u3002CSV \u4e0d\u662f\u6570\u636e\u5e93\u5907\u4efd\u3002';
  String get confirmRestoreBackup => english
      ? 'Restore local backup?'
      : '\u6062\u590d\u672c\u5730\u5907\u4efd\uff1f';
  String get confirmImport =>
      english ? 'Confirm import' : '\u786e\u8ba4\u5bfc\u5165';
  String get import => english ? 'Import' : '\u5bfc\u5165';
  String get moveToTrash =>
      english ? 'Move to trash' : '\u79fb\u5165\u56de\u6536\u7ad9';
  String get randomDeleteTitle => english
      ? 'Random deletion candidates'
      : '\u968f\u673a\u5220\u9664\u5019\u9009';
  String get randomDeleteNote => english
      ? 'Candidates come from this device cache and do not represent all server diaries. Only submit to trash; never permanently delete.'
      : '\u5019\u9009\u6765\u81ea\u672c\u8bbe\u5907\u7f13\u5b58\uff0c\u4e0d\u4ee3\u8868\u670d\u52a1\u5668\u5168\u90e8\u65e5\u8bb0\u3002\u4ec5\u63d0\u4ea4\u79fb\u5165\u56de\u6536\u7ad9\uff0c\u4e0d\u4f1a\u6c38\u4e45\u5220\u9664\u3002';
  String get noDateLimit => english
      ? 'No creation-date limit'
      : '\u521b\u5efa\u65e5\u671f\u4e0d\u9650';
  String dateBefore(String date) => english
      ? 'Created no later than $date'
      : '\u521b\u5efa\u65e5\u671f\u4e0d\u665a\u4e8e $date';
  String get clearDateFilter =>
      english ? 'Clear date filter' : '\u6e05\u9664\u65e5\u671f\u6761\u4ef6';
  String get invalidViewRange => english
      ? 'View counts must be non-negative integers, with minimum no greater than maximum.'
      : '\u67e5\u770b\u6b21\u6570\u8bf7\u8f93\u5165\u975e\u8d1f\u6574\u6570\uff0c\u4e14\u6700\u5c11\u4e0d\u5927\u4e8e\u6700\u591a\u3002';
  String get noDeletionCandidates => english
      ? 'No deletable diary matches the filters.'
      : '\u6ca1\u6709\u7b26\u5408\u7b5b\u9009\u6761\u4ef6\u7684\u53ef\u5220\u9664\u65e5\u8bb0\u3002';
  String get candidatesExhausted => english
      ? 'Candidates for this filter are exhausted. Reset the draw record.'
      : '\u5f53\u524d\u7b5b\u9009\u7684\u5019\u9009\u5df2\u770b\u5b8c\uff0c\u53ef\u91cd\u7f6e\u62bd\u53d6\u8bb0\u5f55\u3002';
  String get deletionDrawFailed => english
      ? 'Failed to draw locally. Check the cache and retry.'
      : '\u672c\u5730\u62bd\u53d6\u5931\u8d25\uff0c\u8bf7\u68c0\u67e5\u7f13\u5b58\u540e\u91cd\u8bd5\u3002';
  String get localCandidateFailed => english
      ? 'Failed to read local candidates. Please retry later.'
      : '\u672c\u5730\u5019\u9009\u8bfb\u53d6\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5\u3002';
  String get allTagsOption => english ? 'All tags' : '\u5168\u90e8\u6807\u7b7e';
  String get applyAndDraw => english
      ? 'Apply filters and draw'
      : '\u5e94\u7528\u7b5b\u9009\u5e76\u62bd\u53d6';
  String get redraw => english ? 'Draw again' : '\u91cd\u65b0\u62bd\u53d6';
  String get resetDraw =>
      english ? 'Reset draw record' : '\u91cd\u7f6e\u62bd\u53d6\u8bb0\u5f55';
  String get pendingCandidate => english
      ? 'Candidate pending confirmation'
      : '\u5f85\u786e\u8ba4\u5019\u9009';
  String get confirmMoveTrash => english
      ? 'Move to trash?'
      : '\u786e\u8ba4\u79fb\u5165\u56de\u6536\u7ad9\uff1f';
  String deletionPreview(String date, int views, String tags, String content) => english
      ? 'Date: $date\nViews: $views\nTags: $tags\n\n$content\n\nThis does not permanently delete; it remains pending until the server confirms.'
      : '\u65e5\u671f\uff1a$date\n\u67e5\u770b\u6b21\u6570\uff1a$views\n\u6807\u7b7e\uff1a$tags\n\n$content\n\n\u6b64\u64cd\u4f5c\u4e0d\u4f1a\u6c38\u4e45\u5220\u9664\uff0c\u670d\u52a1\u5668\u672a\u786e\u8ba4\u65f6\u53ea\u4fdd\u5b58\u5f85\u540c\u6b65\u4efb\u52a1\u3002';
  String get confirmedTrash => english
      ? 'Server confirmed the diary was moved to trash.'
      : '\u670d\u52a1\u5668\u5df2\u786e\u8ba4\u79fb\u5165\u56de\u6536\u7ad9\u3002';
  String get queuedTrash => english
      ? 'The deletion task was queued; the server has not confirmed it.'
      : '\u5220\u9664\u4efb\u52a1\u5df2\u4fdd\u5b58\u5f85\u540c\u6b65\uff0c\u670d\u52a1\u5668\u5c1a\u672a\u786e\u8ba4\u3002';
  String get conflictTrash => english
      ? 'Version conflict: deletion intent kept. Review the sync conflict; the server did not delete it.'
      : '\u7248\u672c\u51b2\u7a81\uff1a\u5df2\u4fdd\u7559\u5220\u9664\u610f\u56fe\uff0c\u8bf7\u5230\u540c\u6b65\u51b2\u7a81\u5ba1\u6838\u5904\u7406\uff1b\u670d\u52a1\u5668\u672a\u5220\u9664\u3002';
  String get deletionRefreshFailed => english
      ? 'Deletion state was saved, but list refresh failed. Refresh manually.'
      : '\u5220\u9664\u72b6\u6001\u5df2\u4fdd\u5b58\uff0c\u4f46\u5217\u8868\u5237\u65b0\u5931\u8d25\uff0c\u8bf7\u624b\u52a8\u5237\u65b0\u3002';
  String get deletionUnconfirmed => english
      ? 'Deletion was not confirmed. Check the diary and sync status before retrying.'
      : '\u5220\u9664\u672a\u786e\u8ba4\u6210\u529f\uff0c\u8bf7\u6838\u5bf9\u65e5\u8bb0\u548c\u540c\u6b65\u72b6\u6001\u540e\u91cd\u8bd5\u3002';
  String dateLabelShort(String date) =>
      english ? 'Date: $date' : '\u65e5\u671f\uff1a$date';
  String viewsLabel(int views) =>
      english ? 'Views: $views' : '\u67e5\u770b\u6b21\u6570\uff1a$views';
  String tagsValue(String value) =>
      english ? 'Tags: $value' : '\u6807\u7b7e\uff1a$value';
  String summaryValue(String value) => english
      ? 'Content preview: $value'
      : '\u6b63\u6587\u6458\u8981\uff1a$value';
}
