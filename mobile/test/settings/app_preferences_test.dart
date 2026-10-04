import 'dart:io';

import 'package:diary_mobile/models/app_preferences.dart';
import 'package:diary_mobile/pages/app_settings_page.dart';
import 'package:diary_mobile/models/diary.dart';
import 'package:diary_mobile/services/app_preferences_store.dart';
import 'package:diary_mobile/services/local_store.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
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
    await tester.pumpWidget(MaterialApp(
      locale: Locale('zh', 'CN'),
      supportedLocales: const [Locale('zh', 'CN'), Locale('en', 'US')],
      localizationsDelegates: GlobalMaterialLocalizations.delegates,
      home: AppSettingsPage(initial: AppPreferences.defaults),
    ));
    await tester.tap(find.text('显示标签'));
    await tester.tap(find.text('保存'));
    await tester.pumpAndSettle();

    expect(find.byType(AppSettingsPage), findsNothing);
  });
  testWidgets('theme language and date visibility save together',
      (tester) async {
    AppPreferences? result;
    await tester.pumpWidget(MaterialApp(
      locale: const Locale('zh', 'CN'),
      supportedLocales: const [Locale('zh', 'CN'), Locale('en', 'US')],
      localizationsDelegates: GlobalMaterialLocalizations.delegates,
      home: Builder(
        builder: (context) => Scaffold(
          body: TextButton(
            onPressed: () async {
              result = await Navigator.of(context).push<AppPreferences>(
                MaterialPageRoute(
                  builder: (_) =>
                      const AppSettingsPage(initial: AppPreferences.defaults),
                ),
              );
            },
            child: const Text('Open preferences'),
          ),
        ),
      ),
    ));
    await tester.tap(find.text('Open preferences'));
    await tester.pumpAndSettle();
    await tester.tap(find.byType(DropdownButtonFormField<AppThemeMode>));
    await tester.pumpAndSettle();
    await tester.tap(find.text('\u6df1\u8272').last);
    await tester.pumpAndSettle();
    await tester.tap(find.byType(DropdownButtonFormField<AppLanguage>));
    await tester.pumpAndSettle();
    await tester.tap(find.text('English').last);
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.text('\u663e\u793a\u65e5\u671f'));
    await tester.tap(find.text('\u663e\u793a\u65e5\u671f'));
    await tester.tap(find.text('\u4fdd\u5b58'));
    await tester.pumpAndSettle();
    expect(result?.themeMode, AppThemeMode.dark);
    expect(result?.language, AppLanguage.english);
    expect(result?.showDate, isFalse);
  });
  testWidgets('English locale updates settings labels', (tester) async {
    await tester.pumpWidget(MaterialApp(
      locale: const Locale('en', 'US'),
      supportedLocales: const [Locale('zh', 'CN'), Locale('en', 'US')],
      localizationsDelegates: GlobalMaterialLocalizations.delegates,
      home: const AppSettingsPage(initial: AppPreferences.defaults),
    ));
    expect(find.text('Theme, language and list display'), findsOneWidget);
    expect(find.text('Show tags'), findsOneWidget);
  });
  test('theme and language survive database reopen without sync mutations',
      () async {
    final saved = AppPreferences.defaults.copyWith(
      themeMode: AppThemeMode.dark,
      language: AppLanguage.english,
      showDate: false,
      sortField: DiarySortField.views,
    );
    await store.saveAppPreferences(saved);
    await store.close();
    final reopened = await databaseFactoryFfi
        .openDatabase(path.join(directory.path, 'diary.db'));
    store = LocalStore.withDatabase(reopened);

    expect((await store.getAppPreferences()).toJson(), saved.toJson());
    expect(await store.getOutbox(), isEmpty);
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
