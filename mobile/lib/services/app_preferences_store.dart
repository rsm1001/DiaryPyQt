import 'dart:convert';

import 'package:sqflite/sqflite.dart';

import '../models/app_preferences.dart';
import 'local_store.dart';

extension AppPreferencesStore on LocalStore {
  static const _key = 'app_preferences';

  Future<AppPreferences> getAppPreferences() async {
    final rows = await (await database).query(
      'sync_state',
      where: 'key = ?',
      whereArgs: [_key],
      limit: 1,
    );
    if (rows.isEmpty) return AppPreferences.defaults;
    try {
      final decoded = jsonDecode(rows.first['value']! as String);
      if (decoded is! Map) return AppPreferences.defaults;
      return AppPreferences.fromJson(Map<String, dynamic>.from(decoded));
    } on FormatException {
      return AppPreferences.defaults;
    } on TypeError {
      return AppPreferences.defaults;
    }
  }

  Future<void> saveAppPreferences(AppPreferences preferences) async {
    await (await database).insert(
      'sync_state',
      {'key': _key, 'value': jsonEncode(preferences.toJson())},
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }
}
