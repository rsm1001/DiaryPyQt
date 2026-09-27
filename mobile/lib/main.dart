import 'package:flutter/material.dart';
import 'package:just_audio_background/just_audio_background.dart';

import 'pages/diary_list_page.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await JustAudioBackground.init(
    androidNotificationChannelId: 'com.diarypyqt.playback',
    androidNotificationChannelName: 'Diary playback',
    androidNotificationOngoing: true,
  );
  runApp(const DiaryMobileApp());
}

class DiaryMobileApp extends StatelessWidget {
  const DiaryMobileApp({super.key});
  @override
  Widget build(BuildContext context) => MaterialApp(
        title: 'DiaryPyQt',
        theme: ThemeData(
            colorScheme: ColorScheme.fromSeed(seedColor: Colors.indigo),
            useMaterial3: true),
        home: const DiaryListPage(),
      );
}
