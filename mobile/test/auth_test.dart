import 'dart:convert';

import 'package:diary_mobile/models/audio_asset.dart';
import 'package:diary_mobile/services/diary_api.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test('Basic credentials are sent for health, list, and audio downloads',
      () async {
    final requestedPaths = <String>[];
    final api = DiaryApi(
      baseUrl: 'https://203.195.195.218',
      password: 'test-only-password',
      client: MockClient((request) async {
        requestedPaths.add(request.url.path);
        expect(request.headers['Authorization'],
            'Basic ${base64Encode(utf8.encode('diary:test-only-password'))}');
        if (request.url.path == '/health') {
          return http.Response(
              jsonEncode({'status': 'ok', 'service': 'diary-server'}), 200);
        }
        return http.Response(jsonEncode({'items': []}), 200);
      }),
    );
    await api.checkConnection();
    expect(await api.fetchDiaries(), isEmpty);
    final asset = AudioAsset(
      id: 'asset',
      diaryId: 'diary',
      voiceId: 'voice',
      contentHash: 'hash',
      fileHash: 'hash',
      durationMs: 1000,
      downloadUrl: 'https://203.195.195.218/api/v1/audio-assets/asset/download',
    );
    await api.downloadAudio(asset);
    expect(requestedPaths,
        ['/health', '/api/v1/diaries', '/api/v1/audio-assets/asset/download']);
    api.dispose();
  });

  test('Unauthorized health check directs user to the connection password',
      () async {
    final api = DiaryApi(
      baseUrl: 'https://203.195.195.218',
      client: MockClient((request) async => http.Response('', 401)),
    );
    await expectLater(
      api.checkConnection(),
      throwsA(isA<DiaryApiException>()
          .having((error) => error.statusCode, 'statusCode', 401)),
    );
    api.dispose();
  });
}
