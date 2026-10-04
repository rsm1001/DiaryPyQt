import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:just_audio_background/just_audio_background.dart';

import 'models/app_preferences.dart';
import 'pages/diary_list_page.dart';
import 'services/app_preferences_store.dart';
import 'services/local_store.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await JustAudioBackground.init(
    androidNotificationChannelId: 'com.diarypyqt.playback',
    androidNotificationChannelName: 'Diary playback',
    androidNotificationOngoing: true,
  );
  runApp(const DiaryMobileApp());
}

class DiaryMobileApp extends StatefulWidget {
  const DiaryMobileApp({super.key});

  @override
  State<DiaryMobileApp> createState() => _DiaryMobileAppState();
}

class _DiaryMobileAppState extends State<DiaryMobileApp> {
  AppPreferences _preferences = AppPreferences.defaults;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _loadPreferences();
  }

  Future<void> _loadPreferences() async {
    final store = LocalStore();
    try {
      final preferences = await store.getAppPreferences();
      if (mounted) {
        setState(() {
          _preferences = preferences;
          _loading = false;
        });
      }
    } finally {
      await store.close();
      if (mounted && _loading) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) => MaterialApp(
        title: 'DiaryPyQt',
        theme: ThemeData(
            colorScheme: ColorScheme.fromSeed(seedColor: Colors.indigo),
            useMaterial3: true),
        darkTheme: ThemeData(
            colorScheme: ColorScheme.fromSeed(
                seedColor: Colors.indigo, brightness: Brightness.dark),
            useMaterial3: true),
        themeMode: switch (_preferences.themeMode) {
          AppThemeMode.system => ThemeMode.system,
          AppThemeMode.light => ThemeMode.light,
          AppThemeMode.dark => ThemeMode.dark,
        },
        locale:
            Locale(_preferences.language == AppLanguage.english ? 'en' : 'zh'),
        localizationsDelegates: GlobalMaterialLocalizations.delegates,
        supportedLocales: const [Locale('zh', 'CN'), Locale('en', 'US')],
        home: _loading
            ? const Scaffold(body: Center(child: CircularProgressIndicator()))
            : DiaryListPage(
                preferences: _preferences,
                onPreferencesChanged: (value) =>
                    setState(() => _preferences = value),
              ),
      );
}
