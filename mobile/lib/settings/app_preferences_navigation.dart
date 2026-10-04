import 'dart:developer' as developer;

import 'package:flutter/material.dart';

import '../localization/app_strings.dart';
import '../models/app_preferences.dart';
import '../pages/app_settings_page.dart';

Future<AppPreferences?> openAppPreferences(
  BuildContext context, {
  required AppPreferences initial,
  required Future<void> Function(AppPreferences) save,
}) async {
  final updated = await Navigator.of(context).push<AppPreferences>(
    MaterialPageRoute(builder: (_) => AppSettingsPage(initial: initial)),
  );
  if (updated == null || !context.mounted) return null;
  final requestId = DateTime.now().microsecondsSinceEpoch;
  try {
    await save(updated);
    developer.log('preferences_saved request_id=$requestId',
        name: 'diary.settings');
    return context.mounted ? updated : null;
  } catch (error, stack) {
    developer.log('preferences_save_failed request_id=$requestId',
        name: 'diary.settings', error: error.runtimeType, stackTrace: stack);
    if (context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(AppStrings.of(context).preferencesSaveFailed)),
      );
    }
    return null;
  }
}
