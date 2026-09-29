import 'package:flutter/material.dart';

class SyncStatusBanner extends StatelessWidget {
  const SyncStatusBanner({
    super.key,
    required this.offline,
    required this.syncing,
    required this.pendingCount,
  });

  final bool offline;
  final bool syncing;
  final int pendingCount;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
        child: Row(children: [
          Icon(offline ? Icons.wifi_off : Icons.sync, size: 18),
          const SizedBox(width: 8),
          Expanded(
            child: Text(offline
                ? '已离线，$pendingCount 条记录待同步'
                : syncing
                    ? '正在同步，$pendingCount 条记录待处理'
                    : '$pendingCount 条记录待同步'),
          ),
        ]),
      );
}

String describeSyncFailure({required bool conflict, required int pending}) =>
    conflict
        ? '存在版本冲突：$pending 条待同步任务已保留，请核对后再重试。'
        : '同步未完成：正在显示本地日记，$pending 条待同步任务仍安全保留。';
