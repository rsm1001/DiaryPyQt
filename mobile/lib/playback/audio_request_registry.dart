import 'package:flutter/foundation.dart';

import '../models/audio_asset.dart';
import '../models/audio_preparation_stage.dart';

class AudioRequestRegistry {
  final Map<String, Future<AudioAsset>> _requests = {};
  final Map<String, AudioPreparationStage> _latestStatus = {};
  final Map<String, ValueChanged<AudioPreparationStage>> _statusListeners = {};

  Future<AudioAsset> ensure(
    String key,
    Future<AudioAsset> Function(
            ValueChanged<AudioPreparationStage> reportStatus)
        start, {
    ValueChanged<AudioPreparationStage>? onStatus,
  }) {
    if (onStatus != null) {
      _statusListeners[key] = onStatus;
      final latest = _latestStatus[key];
      if (latest != null) onStatus(latest);
    }
    final existing = _requests[key];
    if (existing != null) return existing;

    final request = start((status) {
      _latestStatus[key] = status;
      _statusListeners[key]?.call(status);
    });
    late final Future<AudioAsset> tracked;
    tracked = request.then(
      (asset) {
        _removeIfCurrent(key, tracked);
        return asset;
      },
      onError: (Object error, StackTrace stack) {
        _removeIfCurrent(key, tracked);
        Error.throwWithStackTrace(error, stack);
      },
    );
    _requests[key] = tracked;
    return tracked;
  }

  void _removeIfCurrent(String key, Future<AudioAsset> request) {
    if (!identical(_requests[key], request)) return;
    _requests.remove(key);
    _latestStatus.remove(key);
    _statusListeners.remove(key);
  }

  bool contains(String key) => _requests.containsKey(key);

  void clearStatusListener(String key) => _statusListeners.remove(key);

  void clear() {
    _requests.clear();
    _latestStatus.clear();
    _statusListeners.clear();
  }
}
