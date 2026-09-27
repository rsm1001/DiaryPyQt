import 'dart:async';

import 'package:diary_mobile/models/audio_asset.dart';
import 'package:diary_mobile/services/double_playback_service.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:just_audio/just_audio.dart';

class _FakePlayer implements AudioPlayer {
  final states = StreamController<PlayerState>.broadcast();
  Duration currentPosition = Duration.zero;

  @override
  Stream<Duration> get positionStream => const Stream.empty();
  @override
  Stream<Duration?> get durationStream => const Stream.empty();
  @override
  Stream<PlayerState> get playerStateStream => states.stream;
  @override
  Duration get position => currentPosition;
  @override
  Duration? get duration => const Duration(seconds: 2);
  @override
  ProcessingState get processingState => ProcessingState.ready;
  @override
  Future<Duration?> setAudioSource(AudioSource source,
          {bool preload = true,
          int? initialIndex,
          Duration? initialPosition}) async =>
      duration;
  @override
  Future<void> play() async {}
  @override
  Future<void> stop() async {
    currentPosition = Duration.zero;
  }

  @override
  Future<void> dispose() => states.close();
  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

void main() {
  test('only reports playing after position advances; stop cancels playback',
      () async {
    final player = _FakePlayer();
    final service = DoublePlaybackService(player: player);
    final asset = AudioAsset(
        id: 'asset',
        diaryId: 'diary',
        voiceId: 'voice',
        contentHash: 'hash',
        fileHash: 'hash',
        durationMs: 2000,
        downloadUrl: '');
    final playback =
        service.playDiary(diaryId: 'diary', source: 'local.mp3', asset: asset);
    await Future<void>.delayed(const Duration(milliseconds: 30));
    expect(service.snapshot.stage, PlaybackStage.buffering);
    player.currentPosition = const Duration(milliseconds: 100);
    await Future<void>.delayed(const Duration(milliseconds: 1100));
    expect(service.snapshot.stage, PlaybackStage.playingFirst);
    await service.stop();
    expect(await playback, isFalse);
    expect(service.snapshot.stage, PlaybackStage.idle);
    await service.dispose();
  });
}
