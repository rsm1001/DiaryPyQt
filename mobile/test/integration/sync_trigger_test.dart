import 'dart:async';

import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:diary_mobile/services/sync_trigger.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('离线转在线只自动同步一次', () async {
    final changes = StreamController<List<ConnectivityResult>>();
    var requests = 0;
    final trigger = SyncTrigger(
      changes: changes.stream,
      refresh: () async => requests++,
      onError: (error, stack) => fail('不应失败'),
    )..start();
    changes.add([ConnectivityResult.none]);
    changes.add([ConnectivityResult.wifi]);
    await Future<void>.delayed(Duration.zero);
    expect(requests, 1);
    changes.add([ConnectivityResult.mobile]);
    await Future<void>.delayed(Duration.zero);
    expect(requests, 1);
    await trigger.dispose();
    await changes.close();
  });

  test('Retries after server recovery without Wi-Fi changes', () async {
    final changes = StreamController<List<ConnectivityResult>>();
    final recovered = Completer<void>();
    var attempts = 0;
    final failures = <Object>[];
    final trigger = SyncTrigger(
      changes: changes.stream,
      retryDelay: const Duration(milliseconds: 20),
      refresh: () async {
        attempts++;
        if (attempts == 1) throw StateError('server unreachable');
        recovered.complete();
      },
      onError: (error, stack) => failures.add(error),
    )..start();
    changes.add([ConnectivityResult.wifi]);
    await Future<void>.delayed(Duration.zero);
    expect(attempts, 0);
    await trigger.request();
    expect(attempts, 1);
    expect(failures, hasLength(1));
    await recovered.future.timeout(const Duration(seconds: 2));
    expect(attempts, 2);
    await trigger.dispose();
    await changes.close();
  });

  test('Conflicts do not retry and disposal cancels retries', () async {
    final changes = StreamController<List<ConnectivityResult>>();
    var attempts = 0;
    final trigger = SyncTrigger(
      changes: changes.stream,
      retryDelay: const Duration(milliseconds: 20),
      shouldRetry: (error) => error is! StateError,
      refresh: () async {
        attempts++;
        throw StateError('version conflict');
      },
      onError: (error, stack) {},
    )..start();
    await trigger.request();
    await Future<void>.delayed(const Duration(milliseconds: 60));
    expect(attempts, 1);
    trigger.scheduleRetry(Exception('network failure'));
    await trigger.dispose();
    await Future<void>.delayed(const Duration(milliseconds: 60));
    expect(attempts, 1);
    await changes.close();
  });

  test('前台恢复可主动同步且释放后不再监听', () async {
    final changes = StreamController<List<ConnectivityResult>>();
    var requests = 0;
    final trigger = SyncTrigger(
      changes: changes.stream,
      refresh: () async => requests++,
      onError: (error, stack) => fail('不应失败'),
    )..start();
    await trigger.request();
    expect(requests, 1);
    await trigger.dispose();
    changes.add([ConnectivityResult.none]);
    changes.add([ConnectivityResult.wifi]);
    await Future<void>.delayed(Duration.zero);
    expect(requests, 1);
    await changes.close();
  });

  test('同步中多次请求只追加一次尾随同步', () async {
    final changes = StreamController<List<ConnectivityResult>>();
    final first = Completer<void>();
    final second = Completer<void>();
    var requests = 0;
    final trigger = SyncTrigger(
      changes: changes.stream,
      refresh: () async {
        requests++;
        if (requests == 1) {
          await first.future;
        } else {
          await second.future;
        }
      },
      onError: (error, stack) => fail('不应失败'),
    );
    trigger.start();
    final running = trigger.request();
    final next = trigger.request();
    expect(identical(running, next), isTrue);
    expect(requests, 1);
    first.complete();
    await Future<void>.delayed(Duration.zero);
    expect(requests, 2);
    second.complete();
    await running;
    await next;
    expect(requests, 2);
    await trigger.dispose();
    await changes.close();
  });

  test('同步失败后仍可继续重试', () async {
    final changes = StreamController<List<ConnectivityResult>>();
    var requests = 0;
    final failures = <Object>[];
    final trigger = SyncTrigger(
      changes: changes.stream,
      refresh: () async {
        requests++;
        if (requests == 1) throw StateError('模拟失败');
      },
      onError: (error, stack) => failures.add(error),
    );
    trigger.start();
    await trigger.request();
    await trigger.request();
    expect(requests, 2);
    expect(failures, hasLength(1));
    await trigger.dispose();
    await changes.close();
  });
}
