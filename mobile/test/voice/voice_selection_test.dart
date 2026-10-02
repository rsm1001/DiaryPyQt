import 'dart:convert';

import 'package:diary_mobile/services/diary_api.dart';
import 'package:diary_mobile/services/local_store.dart';
import 'package:diary_mobile/voice/voice_selection_page.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

class _MemoryVoiceStore extends LocalStore {
  String? saved;
  String? serverDefault;
  @override
  Future<void> saveDefaultVoice(String serverUrl, String voiceId) async {
    serverDefault = voiceId;
  }

  @override
  Future<void> saveSelectedVoice(String serverUrl, String voiceId) async {
    saved = voiceId;
  }
}

void main() {
  test('语音列表经认证接口读取，解析名称和语言', () async {
    final api = DiaryApi(
        baseUrl: 'https://example.invalid',
        client: MockClient((request) async {
          expect(request.url.path, '/api/v1/voices');
          return http.Response.bytes(
              utf8.encode(jsonEncode({
                'items': [
                  {
                    'id': 'voice-a',
                    'name': '中文女声',
                    'language': 'zh-CN',
                    'offline_supported': false
                  },
                ]
              })),
              200,
              headers: {'content-type': 'application/json; charset=utf-8'});
        }));
    final voices = await api.fetchVoices();
    expect(voices.single.id, 'voice-a');
    expect(voices.single.name, '中文女声');
    expect(voices.single.language, 'zh-CN');
    api.dispose();
  });

  testWidgets('列表不可用时保留当前选择，刷新成功才允许选择', (tester) async {
    final store = _MemoryVoiceStore();
    var unavailable = true;
    final api = DiaryApi(
        baseUrl: 'https://example.invalid',
        client: MockClient((request) async {
          if (unavailable) return http.Response('', 503);
          return http.Response.bytes(
              utf8.encode(jsonEncode({
                'items': [
                  {
                    'id': 'voice-a',
                    'name': '中文女声',
                    'language': 'zh-CN',
                    'offline_supported': false
                  },
                  {
                    'id': 'voice-b',
                    'name': '中文男声',
                    'language': 'zh-CN',
                    'offline_supported': true
                  },
                ]
              })),
              200,
              headers: {'content-type': 'application/json; charset=utf-8'});
        }));
    addTearDown(api.dispose);
    String? chosen;
    await tester.pumpWidget(MaterialApp(
        home: Builder(
            builder: (context) => Scaffold(
                    body: Column(children: [
                  TextButton(
                      onPressed: () async {
                        chosen = await Navigator.of(context).push<String>(
                            MaterialPageRoute(
                                builder: (_) => VoiceSelectionPage(
                                    api: api,
                                    store: store,
                                    serverUrl: 'https://example.invalid',
                                    currentVoiceId: 'voice-a')));
                      },
                      child: const Text('打开语音包')),
                ])))));
    await tester.tap(find.text('打开语音包'));
    await tester.pumpAndSettle();
    expect(find.text('语音包列表不可用，保留当前设置。'), findsOneWidget);
    expect(find.textContaining('voice-a'), findsOneWidget);
    expect(store.saved, isNull);
    unavailable = false;
    await tester.tap(find.byTooltip('刷新语音包'));
    await tester.pumpAndSettle();
    expect(find.text('中文男声'), findsOneWidget);
    await tester.tap(find.text('中文男声'));
    await tester.pumpAndSettle();
    expect(store.serverDefault, 'voice-a');
    expect(store.saved, 'voice-b');
    expect(chosen, 'voice-b');
  });
}
