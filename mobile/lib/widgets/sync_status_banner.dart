import 'package:flutter/material.dart';

import '../localization/app_strings.dart';

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
  Widget build(BuildContext context) {
    final strings = AppStrings.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      child: Row(children: [
        Icon(offline ? Icons.wifi_off : Icons.sync, size: 18),
        const SizedBox(width: 8),
        Expanded(
          child: Text(strings.syncBanner(offline, syncing, pendingCount)),
        ),
      ]),
    );
  }
}

String describeSyncFailure({
  required bool conflict,
  required int pending,
  int? statusCode,
}) {
  if (statusCode == 401 || statusCode == 403) {
    return '服务器身份验证失败（HTTP $statusCode）。请到右上角“更多→服务器设置”重新输入连接密码；$pending 条待同步任务仍保留。';
  }
  if (conflict) {
    return '存在版本冲突：$pending 条待同步任务已保留，请核对后再重试。';
  }
  if (statusCode != null) {
    return '服务器返回 HTTP $statusCode，同步未完成；$pending 条待同步任务仍保留，请检查服务器或稍后重试。';
  }
  return '同步未完成：正在显示本地日记，$pending 条待同步任务仍安全保留。';
}
