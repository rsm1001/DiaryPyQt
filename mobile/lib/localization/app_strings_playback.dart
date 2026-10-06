import '../models/audio_preparation_stage.dart';
import 'app_strings.dart';

extension AppStringsPlayback on AppStrings {
  String syncBanner(bool offline, bool syncing, int pending) => offline
      ? (english
          ? 'Offline, $pending records pending sync'
          : '\u5df2\u79bb\u7ebf\uff0c$pending \u6761\u8bb0\u5f55\u5f85\u540c\u6b65')
      : syncing
          ? (english
              ? 'Syncing, $pending records pending'
              : '\u6b63\u5728\u540c\u6b65\uff0c$pending \u6761\u8bb0\u5f55\u5f85\u5904\u7406')
          : (english
              ? '$pending records pending sync'
              : '$pending \u6761\u8bb0\u5f55\u5f85\u540c\u6b65');
  String syncFailure({
    required bool conflict,
    required int pending,
    int? statusCode,
  }) {
    if (statusCode == 401 || statusCode == 403) {
      return english
          ? 'Server authentication failed (HTTP $statusCode). Open More > Server settings to re-enter the password; $pending pending tasks remain.'
          : '\u670d\u52a1\u5668\u8eab\u4efd\u9a8c\u8bc1\u5931\u8d25\uff08HTTP $statusCode\uff09\u3002\u8bf7\u5230\u53f3\u4e0a\u89d2\u201c\u66f4\u591a\u2192\u670d\u52a1\u5668\u8bbe\u7f6e\u201d\u91cd\u65b0\u8f93\u5165\u8fde\u63a5\u5bc6\u7801\uff1b$pending \u6761\u5f85\u540c\u6b65\u4efb\u52a1\u4ecd\u4fdd\u7559\u3002';
    }
    if (conflict) {
      return english
          ? 'Version conflict: $pending pending tasks were kept. Review before retrying.'
          : '\u5b58\u5728\u7248\u672c\u51b2\u7a81\uff1a$pending \u6761\u5f85\u540c\u6b65\u4efb\u52a1\u5df2\u4fdd\u7559\uff0c\u8bf7\u6838\u5bf9\u540e\u518d\u91cd\u8bd5\u3002';
    }
    if (statusCode != null) {
      return english
          ? 'Server returned HTTP $statusCode; sync incomplete. $pending pending tasks remain.'
          : '\u670d\u52a1\u5668\u8fd4\u56de HTTP $statusCode\uff0c\u540c\u6b65\u672a\u5b8c\u6210\uff1b$pending \u6761\u5f85\u540c\u6b65\u4efb\u52a1\u4ecd\u4fdd\u7559\uff0c\u8bf7\u68c0\u67e5\u670d\u52a1\u5668\u6216\u7a0d\u540e\u91cd\u8bd5\u3002';
    }
    return english
        ? 'Sync incomplete: showing local diaries; $pending pending tasks remain safe.'
        : '\u540c\u6b65\u672a\u5b8c\u6210\uff1a\u6b63\u5728\u663e\u793a\u672c\u5730\u65e5\u8bb0\uff0c$pending \u6761\u5f85\u540c\u6b65\u4efb\u52a1\u4ecd\u5b89\u5168\u4fdd\u7559\u3002';
  }

  String get stopRandomPlayback => english
      ? 'Stop random continuous playback'
      : '\u505c\u6b62\u968f\u673a\u8fde\u7eed\u64ad\u653e';
  String get startRandomPlayback => english
      ? 'Start random continuous playback'
      : '\u5f00\u59cb\u968f\u673a\u8fde\u7eed\u64ad\u653e';
  String get selectingRandomDiary => english
      ? 'Selecting the next random diary'
      : '\u6b63\u5728\u9009\u62e9\u4e0b\u4e00\u7bc7\u968f\u673a\u65e5\u8bb0';
  String currentDiary(String date, int views) => english
      ? 'Current: $date - Viewed $views times'
      : '\u5f53\u524d\uff1a$date \u00b7 \u67e5\u770b $views \u6b21';
  String get preparingAudio => english
      ? 'Preparing audio, please wait'
      : '\u6b63\u5728\u51c6\u5907\u97f3\u9891\uff0c\u8bf7\u7a0d\u5019';
  String get preparingPool => english
      ? 'Preparing random candidate pool'
      : '\u968f\u673a\u5019\u9009\u6c60\u51c6\u5907\u4e2d';
  String get preparingNextAudio => english
      ? 'Preparing audio for the next diary'
      : '\u6b63\u5728\u51c6\u5907\u4e0b\u4e00\u7bc7\u97f3\u9891';
  String playbackProgress(String stage, int count) => english
      ? '$stage - $count candidates, looping'
      : '$stage \u00b7 \u5019\u9009\u6c60 $count \u7bc7\uff0c\u5faa\u73af\u64ad\u653e';
  String get waitingBetweenRounds => english
      ? 'Waiting between rounds'
      : '\u4e24\u904d\u4e4b\u95f4\u7b49\u5f85\u4e2d';
  String get audioLoading =>
      english ? 'Loading audio' : '\u97f3\u9891\u52a0\u8f7d\u4e2d';
  String get playingFirstRound =>
      english ? 'Playing round 1' : '\u7b2c 1 \u904d\u64ad\u653e\u4e2d';
  String get playingSecondRound =>
      english ? 'Playing round 2' : '\u7b2c 2 \u904d\u64ad\u653e\u4e2d';
  String get playbackPaused => english ? 'Paused' : '\u5df2\u6682\u505c';
  String get playbackCompleted => english ? 'Completed' : '\u5df2\u5b8c\u6210';
  String get playbackReady =>
      english ? 'Ready to play' : '\u51c6\u5907\u64ad\u653e';
  String get connectionVerified => english
      ? 'Diary server connection verified'
      : '\u65e5\u8bb0\u670d\u52a1\u5668\u8fde\u63a5\u5df2\u9a8c\u8bc1';
  String get connectionValidationFailed => english
      ? 'Connection check failed. Verify the server address and password.'
      : '\u8fde\u63a5\u6821\u9a8c\u5931\u8d25\uff0c\u8bf7\u68c0\u67e5\u670d\u52a1\u5668\u5730\u5740\u4e0e\u5bc6\u7801\u3002';
  String get resumePlaybackTitle => english
      ? 'Resume previous playback?'
      : '\u6062\u590d\u4e0a\u6b21\u64ad\u653e\uff1f';
  String resumePlaybackMessage(int round, int seconds, String status) => english
      ? 'Previous playback: round $round at $seconds seconds, status "$status".'
      : '\u4e0a\u6b21\u5728\u7b2c $round \u904d\u64ad\u653e\u5230 $seconds \u79d2\uff0c\u72b6\u6001\u4e3a\u201c$status\u201d\u3002';
  String get playFromBeginning =>
      english ? 'Play from start' : '\u4ece\u5934\u64ad\u653e';
  String get continuePlayback =>
      english ? 'Resume playback' : '\u7ee7\u7eed\u64ad\u653e';
  String get batchDeleteDiariesTitle => english
      ? 'Delete selected diaries?'
      : '\u6279\u91cf\u5220\u9664\u65e5\u8bb0';
  String batchDeleteDiariesConfirm(int count) => english
      ? 'Move $count selected diaries to trash. Continue?'
      : '\u5c06\u9009\u4e2d\u7684 $count \u7bc7\u65e5\u8bb0\u79fb\u5165\u56de\u6536\u7ad9\uff0c\u662f\u5426\u7ee7\u7eed\uff1f';
  String get pendingServerChange => english
      ? 'Unsynced views or edits remain. Sync or resolve conflicts before switching servers.'
      : '\u8fd8\u6709\u672a\u540c\u6b65\u7684\u67e5\u770b\u6216\u7f16\u8f91\u8bb0\u5f55\uff0c\u8bf7\u5148\u540c\u6b65\u6216\u5904\u7406\u51b2\u7a81\uff0c\u4e0d\u53ef\u5207\u6362\u670d\u52a1\u5668\u3002';
  String get syncStateFailed => english
      ? 'Local sync status could not be updated. Try again later.'
      : '\u672c\u5730\u540c\u6b65\u72b6\u6001\u65e0\u6cd5\u66f4\u65b0\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5\u3002';
  String get batchDeleteFailed => english
      ? 'Batch deletion did not finish; unprocessed diaries were kept.'
      : '\u6279\u91cf\u5220\u9664\u672a\u5b8c\u6210\uff0c\u5df2\u4fdd\u7559\u672a\u5904\u7406\u65e5\u8bb0';
  String batchTagsUpdated(int count) => english
      ? 'Updated tags for $count diaries'
      : '\u5df2\u66f4\u65b0 $count \u7bc7\u65e5\u8bb0\u7684\u6807\u7b7e';
  String get batchTagsFailed => english
      ? 'Tag updates were not submitted; the selection was kept for retry.'
      : '\u6807\u7b7e\u66f4\u65b0\u672a\u63d0\u4ea4\uff0c\u5df2\u4fdd\u7559\u9009\u62e9\u4f9b\u91cd\u8bd5';
  String get preparingPlayback =>
      english ? 'Preparing audio' : '\u6b63\u5728\u51c6\u5907\u97f3\u9891';
  String get playbackStalled => english
      ? 'Playback made no progress. Check audio decoding or resync the audio.'
      : '\u97f3\u9891\u64ad\u653e\u65e0\u8fdb\u5ea6\uff0c\u8bf7\u68c0\u67e5\u8bbe\u5907\u97f3\u9891\u89e3\u7801\u6216\u91cd\u65b0\u540c\u6b65\u97f3\u9891';
  String get playbackFailed => english
      ? 'Audio could not play. Random playback stopped.'
      : '\u97f3\u9891\u65e0\u6cd5\u64ad\u653e\uff0c\u968f\u673a\u64ad\u653e\u5df2\u505c\u6b62';
  String get noRandomPlaybackCandidate => english
      ? 'No diaries match the current filters for random playback.'
      : '\u5f53\u524d\u7b5b\u9009\u6ca1\u6709\u53ef\u968f\u673a\u64ad\u653e\u7684\u65e5\u8bb0';
  String audioCacheStatus(AudioPreparationStage stage) => switch (stage) {
        AudioPreparationStage.checkingCache => english
            ? 'Checking audio cache'
            : '\u6b63\u5728\u68c0\u67e5\u8bed\u97f3\u7f13\u5b58',
        AudioPreparationStage.loadedOfflineCache => english
            ? 'Loaded audio from offline cache'
            : '\u5df2\u4ece\u79bb\u7ebf\u7f13\u5b58\u8bfb\u53d6\u97f3\u9891',
        AudioPreparationStage.generating =>
          english ? 'Generating audio' : '\u6b63\u5728\u751f\u6210\u97f3\u9891',
        AudioPreparationStage.downloading => english
            ? 'Downloading audio'
            : '\u6b63\u5728\u4e0b\u8f7d\u97f3\u9891',
        AudioPreparationStage.verifying =>
          english ? 'Verifying audio' : '\u6b63\u5728\u6821\u9a8c\u97f3\u9891',
        AudioPreparationStage.cached =>
          english ? 'Audio cached' : '\u97f3\u9891\u5df2\u7f13\u5b58',
      };
}
