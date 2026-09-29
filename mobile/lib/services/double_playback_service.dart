import 'dart:async';

import 'package:just_audio/just_audio.dart';
import 'package:just_audio_background/just_audio_background.dart';

import '../models/audio_asset.dart';

enum PlaybackStage {
  idle,
  playingFirst,
  buffering,
  waiting,
  playingSecond,
  paused,
  completed
}

class PlaybackSnapshot {
  const PlaybackSnapshot(
      {required this.diaryId,
      required this.stage,
      required this.roundNumber,
      required this.remainingGap,
      this.position = Duration.zero,
      this.duration = Duration.zero});
  final String? diaryId;
  final PlaybackStage stage;
  final int roundNumber;
  final Duration remainingGap;
  final Duration position;
  final Duration duration;
}

class DoublePlaybackService {
  DoublePlaybackService({AudioPlayer? player})
      : _player = player ?? AudioPlayer() {
    _positionSubscription = _player.positionStream.listen((position) {
      _emit(_snapshot.stage, _snapshot.diaryId, _snapshot.roundNumber,
          _snapshot.remainingGap,
          position: position);
    });
    _durationSubscription = _player.durationStream.listen((duration) {
      _emit(_snapshot.stage, _snapshot.diaryId, _snapshot.roundNumber,
          _snapshot.remainingGap,
          duration: duration ?? Duration.zero);
    });
  }
  final AudioPlayer _player;
  final StreamController<PlaybackSnapshot> _stateController =
      StreamController.broadcast();
  late final StreamSubscription<Duration> _positionSubscription;
  late final StreamSubscription<Duration?> _durationSubscription;
  Timer? _gapTimer;
  PlaybackSnapshot _snapshot = const PlaybackSnapshot(
      diaryId: null,
      stage: PlaybackStage.idle,
      roundNumber: 0,
      remainingGap: Duration.zero);
  int _runToken = 0;
  bool _pausedDuringGap = false;
  Completer<void>? _gapCompleter;
  Completer<void>? _playCompleter;
  static const _stallTimeout = Duration(seconds: 20);
  static const _repeatGap = Duration(seconds: 3);

  Stream<PlaybackSnapshot> get stateStream => _stateController.stream;
  PlaybackSnapshot get snapshot => _snapshot;

  Future<bool> playDiary(
      {required String diaryId,
      required String source,
      required AudioAsset asset}) async {
    await stop();
    final token = ++_runToken;
    await _setSource(source, diaryId, asset);
    if (token != _runToken) return false;
    final firstDuration =
        _player.duration ?? Duration(milliseconds: asset.durationMs);
    _emit(PlaybackStage.buffering, diaryId, 1, Duration.zero,
        position: Duration.zero, duration: firstDuration);
    if (!await _playUntilCompleted(token)) return false;
    // Keep the repeat gap short; it must not scale with a long diary audio duration.
    const gap = _repeatGap;
    await _waitGap(diaryId, gap, token);
    if (token != _runToken) return false;
    await _setSource(source, diaryId, asset);
    if (token != _runToken) return false;
    _emit(PlaybackStage.buffering, diaryId, 2, Duration.zero,
        position: Duration.zero, duration: _player.duration ?? firstDuration);
    if (!await _playUntilCompleted(token)) return false;
    if (token == _runToken) {
      _emit(PlaybackStage.completed, diaryId, 2, Duration.zero);
      return true;
    }
    return false;
  }

  Future<bool> _playUntilCompleted(int token) async {
    final completer = Completer<void>();
    _playCompleter = completer;
    var lastPosition = _player.position;
    var lastProgress = DateTime.now();
    final round = _snapshot.roundNumber;
    final playingStage =
        round == 1 ? PlaybackStage.playingFirst : PlaybackStage.playingSecond;
    late final StreamSubscription<PlayerState> stateSubscription;
    stateSubscription = _player.playerStateStream.listen((state) {
      if (token != _runToken || completer.isCompleted) return;
      if (state.processingState == ProcessingState.completed) {
        completer.complete();
      } else if (state.processingState == ProcessingState.loading ||
          state.processingState == ProcessingState.buffering) {
        if (_snapshot.stage != PlaybackStage.paused) {
          _emit(
              PlaybackStage.buffering, _snapshot.diaryId, round, Duration.zero);
        }
      }
    });
    final watchdog = Timer.periodic(const Duration(seconds: 1), (_) {
      if (token != _runToken || completer.isCompleted) return;
      if (_snapshot.stage == PlaybackStage.paused) {
        lastProgress = DateTime.now();
        return;
      }
      final position = _player.position;
      if (position > lastPosition) {
        lastPosition = position;
        lastProgress = DateTime.now();
        if (_snapshot.stage == PlaybackStage.buffering) {
          _emit(playingStage, _snapshot.diaryId, round, Duration.zero);
        }
      } else if (DateTime.now().difference(lastProgress) >= _stallTimeout) {
        completer.completeError(StateError('Audio playback stalled'));
      }
    });
    try {
      if (_player.processingState == ProcessingState.completed) {
        completer.complete();
      } else {
        unawaited(_player.play().catchError((Object error, StackTrace stack) {
          if (!completer.isCompleted) completer.completeError(error, stack);
        }));
      }
      await completer.future;
      return token == _runToken;
    } finally {
      watchdog.cancel();
      await stateSubscription.cancel();
      if (identical(_playCompleter, completer)) _playCompleter = null;
    }
  }

  Future<void> _setSource(
      String source, String diaryId, AudioAsset asset) async {
    final item = MediaItem(
        id: asset.id,
        album: 'DiaryPyQt',
        title: diaryId,
        artist: asset.voiceId);
    final audioSource = source.startsWith('http')
        ? AudioSource.uri(Uri.parse(source), tag: item)
        : AudioSource.file(source, tag: item);
    await _player.setAudioSource(audioSource).timeout(_stallTimeout);
  }

  Future<void> _waitGap(String diaryId, Duration gap, int token) async {
    _pausedDuringGap = false;
    final completer = Completer<void>();
    _gapCompleter = completer;
    var remaining = gap;
    _emit(PlaybackStage.waiting, diaryId, 1, remaining);
    _gapTimer = Timer.periodic(const Duration(seconds: 1), (timer) {
      if (_pausedDuringGap) return;
      remaining -= const Duration(seconds: 1);
      _emit(PlaybackStage.waiting, diaryId, 1,
          remaining.isNegative ? Duration.zero : remaining);
      if (remaining <= Duration.zero && !completer.isCompleted) {
        timer.cancel();
        completer.complete();
      }
    });
    await completer.future;
    if (identical(_gapCompleter, completer)) {
      _gapCompleter = null;
    }
    if (token == _runToken) _gapTimer = null;
  }

  Future<void> pause() async {
    if (_snapshot.stage == PlaybackStage.waiting) {
      _pausedDuringGap = true;
      _emit(PlaybackStage.paused, _snapshot.diaryId, _snapshot.roundNumber,
          _snapshot.remainingGap);
    } else {
      await _player.pause();
      _emit(PlaybackStage.paused, _snapshot.diaryId, _snapshot.roundNumber,
          _snapshot.remainingGap);
    }
  }

  Future<void> resume() async {
    if (_snapshot.stage == PlaybackStage.paused &&
        _snapshot.remainingGap > Duration.zero) {
      _pausedDuringGap = false;
      _emit(PlaybackStage.waiting, _snapshot.diaryId, _snapshot.roundNumber,
          _snapshot.remainingGap);
    } else {
      await _player.play();
      _emit(
          _snapshot.roundNumber == 1
              ? PlaybackStage.playingFirst
              : PlaybackStage.playingSecond,
          _snapshot.diaryId,
          _snapshot.roundNumber,
          _snapshot.remainingGap);
    }
  }

  Future<void> stop() async {
    _runToken++;
    if (_playCompleter != null && !_playCompleter!.isCompleted) {
      _playCompleter!.complete();
    }
    _gapTimer?.cancel();
    if (_gapCompleter != null && !_gapCompleter!.isCompleted) {
      _gapCompleter!.complete();
    }
    _gapCompleter = null;
    _gapTimer = null;
    await _player.stop();
    _emit(PlaybackStage.idle, null, 0, Duration.zero,
        position: Duration.zero, duration: Duration.zero);
  }

  void _emit(PlaybackStage stage, String? diaryId, int round, Duration gap,
      {Duration? position, Duration? duration}) {
    _snapshot = PlaybackSnapshot(
        diaryId: diaryId,
        stage: stage,
        roundNumber: round,
        remainingGap: gap,
        position: position ?? _snapshot.position,
        duration: duration ?? _snapshot.duration);
    if (!_stateController.isClosed) _stateController.add(_snapshot);
  }

  Future<void> dispose() async {
    await _positionSubscription.cancel();
    await _durationSubscription.cancel();
    await stop();
    await _player.dispose();
    await _stateController.close();
  }
}
