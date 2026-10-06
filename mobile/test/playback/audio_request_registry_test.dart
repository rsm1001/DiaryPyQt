import 'dart:async';

import 'package:diary_mobile/models/audio_asset.dart';
import 'package:diary_mobile/models/audio_preparation_stage.dart';
import 'package:diary_mobile/playback/audio_request_registry.dart';
import 'package:flutter_test/flutter_test.dart';

const _asset = AudioAsset(
  id: 'asset',
  diaryId: 'diary',
  voiceId: 'voice',
  contentHash: 'hash',
  fileHash: 'sha256:hash',
  durationMs: 100,
  downloadUrl: 'https://example.invalid/audio',
);

void main() {
  test('foreground playback subscribes to a background cache request',
      () async {
    final registry = AudioRequestRegistry();
    final completion = Completer<AudioAsset>();
    final prefetchStatuses = <AudioPreparationStage>[];
    final foregroundStatuses = <AudioPreparationStage>[];
    var startCount = 0;
    late void Function(AudioPreparationStage) reportProgress;

    final prefetch = registry.ensure(
      'diary|content|voice',
      (reportStatus) async {
        startCount++;
        reportProgress = reportStatus;
        reportProgress(AudioPreparationStage.generating);
        reportProgress(AudioPreparationStage.downloading);
        return completion.future;
      },
      onStatus: prefetchStatuses.add,
    );
    final playback = registry.ensure(
      'diary|content|voice',
      (_) async {
        startCount++;
        return _asset;
      },
      onStatus: foregroundStatuses.add,
    );

    expect(identical(prefetch, playback), isTrue);
    expect(startCount, 1);
    expect(prefetchStatuses, [
      AudioPreparationStage.generating,
      AudioPreparationStage.downloading,
    ]);
    expect(foregroundStatuses, [AudioPreparationStage.downloading]);
    reportProgress(AudioPreparationStage.verifying);
    expect(foregroundStatuses, [
      AudioPreparationStage.downloading,
      AudioPreparationStage.verifying,
    ]);

    registry.clearStatusListener('diary|content|voice');
    completion.complete(_asset);
    expect(await playback, _asset);
    expect(registry.contains('diary|content|voice'), isFalse);
    expect(
      await registry.ensure('diary|content|voice', (_) async {
        startCount++;
        return _asset;
      }),
      _asset,
    );
    expect(startCount, 2);
    registry.clear();
    expect(registry.contains('diary|content|voice'), isFalse);
  });

  test('failed shared request can be retried', () async {
    final registry = AudioRequestRegistry();
    final failed =
        registry.ensure('key', (_) async => throw StateError('failed'));
    await expectLater(failed, throwsStateError);
    expect(registry.contains('key'), isFalse);
    expect(await registry.ensure('key', (_) async => _asset), _asset);
  });
}
