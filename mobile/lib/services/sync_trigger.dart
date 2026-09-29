import 'dart:async';

import 'package:connectivity_plus/connectivity_plus.dart';

class SyncTrigger {
  SyncTrigger({
    required Stream<List<ConnectivityResult>> changes,
    required Future<void> Function() refresh,
    required void Function(Object, StackTrace) onError,
    this.onOfflineChanged,
  })  : _changes = changes,
        _refresh = refresh,
        _onError = onError;

  final Stream<List<ConnectivityResult>> _changes;
  final Future<void> Function() _refresh;
  final void Function(Object, StackTrace) _onError;
  final void Function(bool offline)? onOfflineChanged;
  StreamSubscription<List<ConnectivityResult>>? _subscription;
  Future<void>? _pending;
  bool _offline = false;
  bool _rerun = false;
  bool _disposed = false;

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
    if (_pending != null) {
      _rerun = true;
      return _pending!;
    }
    final pending = _run();
    _pending = pending;
    return pending;
  }

  Future<void> _run() async {
    do {
      _rerun = false;
      try {
        await _refresh();
      } catch (error, stack) {
        _onError(error, stack);
      }
    } while (_rerun && !_disposed);
    _pending = null;
  }

  Future<void> dispose() async {
    _disposed = true;
    await _subscription?.cancel();
  }
}
