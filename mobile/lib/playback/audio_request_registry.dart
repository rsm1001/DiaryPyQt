import 'package:flutter/foundation.dart';

import '../models/audio_asset.dart';

class AudioRequestRegistry {
  final Map<String, Future<AudioAsset>> _requests = {};
  final Map<String, String> _latestStatus = {};
  final Map<String, ValueChanged<String>> _statusListeners = {};

  Future<AudioAsset> ensure(
    String key,
    Future<AudioAsset> Function(ValueChanged<String> reportStatus) start, {
    ValueChanged<String>? onStatus,
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
    tracked = request.catchError((Object error, StackTrace stack) {
      if (identical(_requests[key], tracked)) {
        _requests.remove(key);
        _latestStatus.remove(key);
        _statusListeners.remove(key);
      }
      Error.throwWithStackTrace(error, stack);
    });
    _requests[key] = tracked;
    return tracked;
  }

  bool contains(String key) => _requests.containsKey(key);

  void clearStatusListener(String key) => _statusListeners.remove(key);

  void clear() {
    _requests.clear();
    _latestStatus.clear();
    _statusListeners.clear();
  }
}
