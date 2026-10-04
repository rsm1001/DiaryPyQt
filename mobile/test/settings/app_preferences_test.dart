import 'dart:io';

import 'package:diary_mobile/models/app_preferences.dart';
import 'package:diary_mobile/pages/app_settings_page.dart';
import 'package:diary_mobile/models/diary.dart';
import 'package:diary_mobile/services/app_preferences_store.dart';
import 'package:diary_mobile/services/local_store.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:path/path.dart' as path;
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

void main() {
  sqfliteFfiInit();
  late Directory directory;
  late LocalStore store;

  setUp(() async {
    directory = await Directory.systemTemp.createTemp('app-preferences-');
    final database = await databaseFactoryFfi
        .openDatabase(path.join(directory.path, 'diary.db'));
    await LocalStore.createSchema(database, 5);
    store = LocalStore.withDatabase(database);
  });

  tearDown(() async {
    await store.close();
    await directory.delete(recursive: true);
  });

  test('preferences round trip and diary sorting stay local', () async {
    final preferences = AppPreferences.defaults.copyWith(
      themeMode: AppThemeMode.dark,
      language: AppLanguage.english,
      showTags: false,
      sortField: DiarySortField.views,
      sortDescending: false,
    );
    await store.saveAppPreferences(preferences);

    final loaded = await store.getAppPreferences();
    expect(loaded.toJson(), preferences.toJson());
    expect(
        loaded.compare(_diary(1, views: 2), _diary(2, views: 4)), lessThan(0));
  });

  testWidgets('settings page edits list fields without touching diary data',
      (tester) async {
    await tester.pumpWidget(const MaterialApp(
      home: AppSettingsPage(initial: AppPreferences.defaults),
    ));
    await tester.tap(find.text('显示标签'));
    await tester.tap(find.text('保存'));
    await tester.pumpAndSettle();

    expect(find.byType(AppSettingsPage), findsNothing);
  });
  test('corrupt preferences fall back to safe defaults', () async {
    final database = await store.database;
    await database.insert('sync_state', {
      'key': 'app_preferences',
      'value': '{not-json',
    });

    expect((await store.getAppPreferences()).toJson(),
        AppPreferences.defaults.toJson());
  });
}

Diary _diary(int id, {required int views}) => Diary(
      id: '$id',
      date: '2026-10-0$id',
      content: 'content',
      contentHash: 'hash',
      version: 1,
      tags: const [],
      updatedAt: '2026-10-0$id',
      viewCount: views,
    );
