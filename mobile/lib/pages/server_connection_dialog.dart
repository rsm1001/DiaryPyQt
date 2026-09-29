import 'package:flutter/material.dart';

import '../config/app_config.dart';

class ServerConnectionInput {
  const ServerConnectionInput({required this.url, required this.password});

  final String url;
  final String password;
}

Future<ServerConnectionInput?> showServerConnectionDialog(
        BuildContext context, String currentUrl) =>
    showDialog<ServerConnectionInput>(
      context: context,
      builder: (_) => _ServerConnectionDialog(currentUrl: currentUrl),
    );

class _ServerConnectionDialog extends StatefulWidget {
  const _ServerConnectionDialog({required this.currentUrl});

  final String currentUrl;

  @override
  State<_ServerConnectionDialog> createState() =>
      _ServerConnectionDialogState();
}

class _ServerConnectionDialogState extends State<_ServerConnectionDialog> {
  late final TextEditingController _url;
  final _password = TextEditingController();
  String? _validationError;

  @override
  void initState() {
    super.initState();
    _url = TextEditingController(text: widget.currentUrl);
  }

  @override
  void dispose() {
    _url.dispose();
    _password.dispose();
    super.dispose();
  }

  void _submit() {
    final candidate = _url.text.trim().replaceFirst(RegExp(r'/+$'), '');
    if (!AppConfig.isValidServerUrl(candidate)) {
      setState(() => _validationError = '请输入不含路径的 HTTPS 地址；HTTP 仅允许信任的私网入口');
      return;
    }
    Navigator.of(context).pop(ServerConnectionInput(
      url: candidate,
      password: _password.text.trim(),
    ));
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
        title: const Text('连接日记服务器'),
        content: Column(mainAxisSize: MainAxisSize.min, children: [
          TextField(
            controller: _url,
            keyboardType: TextInputType.url,
            autocorrect: false,
            decoration: InputDecoration(
              labelText: '服务器地址',
              hintText: AppConfig.normalizedApiBaseUrl,
              errorText: _validationError,
            ),
          ),
          const SizedBox(height: 8),
          TextField(
            controller: _password,
            obscureText: true,
            autocorrect: false,
            decoration: const InputDecoration(
              labelText: '连接密码',
              hintText: '使用电脑连接文件中的密码',
            ),
          ),
          const SizedBox(height: 8),
          const Text('公网连接请使用 HTTPS；留空密码可保留同一服务器的已存密码。'),
        ]),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('取消'),
          ),
          FilledButton(
            onPressed: _submit,
            child: const Text('测试并保存'),
          ),
        ],
      );
}
