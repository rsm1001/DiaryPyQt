import 'dart:async';

import 'package:diary_mobile/models/audio_asset.dart';
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
    final prefetchStatuses = <String>[];
    final foregroundStatuses = <String>[];
    var startCount = 0;
    late void Function(String) reportProgress;

    final prefetch = registry.ensure(
      'diary|content|voice',
      (reportStatus) async {
        startCount++;
        reportProgress = reportStatus;
        reportProgress('正在生成音频');
        reportProgress('正在下载音频');
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
    expect(prefetchStatuses, ['正在生成音频', '正在下载音频']);
    expect(foregroundStatuses, ['正在下载音频']);
    reportProgress('正在校验音频');
    expect(foregroundStatuses, ['正在下载音频', '正在校验音频']);

    registry.clearStatusListener('diary|content|voice');
    completion.complete(_asset);
    expect(await playback, _asset);
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
