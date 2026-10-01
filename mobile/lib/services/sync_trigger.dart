import 'dart:async';

import 'package:connectivity_plus/connectivity_plus.dart';

class SyncTrigger {
  SyncTrigger({
    required Stream<List<ConnectivityResult>> changes,
    required Future<void> Function() refresh,
    required void Function(Object, StackTrace) onError,
    this.onOfflineChanged,
    this.shouldRetry,
    this.retryDelay = const Duration(seconds: 5),
  })  : _changes = changes,
        _refresh = refresh,
        _onError = onError;

  final Stream<List<ConnectivityResult>> _changes;
  final Future<void> Function() _refresh;
  final void Function(Object, StackTrace) _onError;
  final void Function(bool offline)? onOfflineChanged;
  final bool Function(Object error)? shouldRetry;
  final Duration retryDelay;
  StreamSubscription<List<ConnectivityResult>>? _subscription;
  Future<void>? _pending;
  bool _offline = false;
  bool _rerun = false;
  bool _disposed = false;
  Timer? _retryTimer;
  int _retryCount = 0;

  void start() {
    if (_disposed || _subscription != null) return;
    _subscription = _changes.listen((results) {
      final offline =
          results.isEmpty || results.contains(ConnectivityResult.none);
      if (offline != _offline) onOfflineChanged?.call(offline);
      if (!offline && _offline) unawaited(request());
      _offline = offline;
    }, onError: (Object error, StackTrace stack) => _onError(error, stack));
  }

  Future<void> request() {
    if (_disposed) return Future<void>.value();
    _retryTimer?.cancel();
    _retryTimer = null;
    if (_pending != null) {
      _rerun = true;
      return _pending!;
    }
    final pending = _run();
    _pending = pending;
    return pending;
  }

  void scheduleRetry(Object error) {
    if (_disposed || (shouldRetry != null && !shouldRetry!(error))) return;
    if (_retryTimer != null) return;
    final multiplier = 1 << _retryCount.clamp(0, 4).toInt();
    _retryCount++;
    _retryTimer = Timer(retryDelay * multiplier, () {
      _retryTimer = null;
      unawaited(request());
    });
  }

  Future<void> _run() async {
    do {
      _rerun = false;
      try {
        await _refresh();
        _retryCount = 0;
      } catch (error, stack) {
        _onError(error, stack);
        scheduleRetry(error);
      }
    } while (_rerun && !_disposed);
    _pending = null;
  }

  Future<void> dispose() async {
    _disposed = true;
    _retryTimer?.cancel();
    _retryTimer = null;
    await _subscription?.cancel();
  }
}
