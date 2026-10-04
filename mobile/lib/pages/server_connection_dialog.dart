import 'package:flutter/material.dart';

import '../config/app_config.dart';
import '../localization/app_strings.dart';

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
      setState(
          () => _validationError = AppStrings.of(context).invalidServerUrl);
      return;
    }
    Navigator.of(context).pop(ServerConnectionInput(
      url: candidate,
      password: _password.text.trim(),
    ));
  }

  @override
  Widget build(BuildContext context) {
    final strings = AppStrings.of(context);
    return AlertDialog(
      title: Text(strings.connectServer),
      content: Column(mainAxisSize: MainAxisSize.min, children: [
        TextField(
          controller: _url,
          keyboardType: TextInputType.url,
          autocorrect: false,
          decoration: InputDecoration(
            labelText: strings.serverAddress,
            hintText: AppConfig.normalizedApiBaseUrl,
            errorText: _validationError,
          ),
        ),
        const SizedBox(height: 8),
        TextField(
          controller: _password,
          obscureText: true,
          autocorrect: false,
          decoration: InputDecoration(
            labelText: strings.connectionPassword,
            hintText: strings.savedPasswordHint,
          ),
        ),
        const SizedBox(height: 8),
        Text(strings.httpsNote),
      ]),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: Text(strings.cancel),
        ),
        FilledButton(
          onPressed: _submit,
          child: Text(strings.testAndSave),
        ),
      ],
    );
  }
}
