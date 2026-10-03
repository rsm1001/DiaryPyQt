import 'dart:convert';

import 'package:diary_mobile/services/diary_api.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test('逐条获取远端版本用于冲突审核，不使用旧缓存冒充远端', () async {
    final api = DiaryApi(
        baseUrl: 'https://example.invalid',
        client: MockClient((request) async {
          expect(request.method, 'GET');
          expect(request.url.path, '/api/v1/diaries/diary-1');
          return http.Response.bytes(
              utf8.encode(jsonEncode({
                'id': 'diary-1',
                'date': '2026-09-27',
                'content': '服务器正文',
                'tags': ['服务器标签'],
                'content_hash': 'hash',
                'version': 4,
                'updated_at': '2026-09-28T10:00:00Z',
              })),
              200,
              headers: {'content-type': 'application/json; charset=utf-8'});
        }));
    final remote = await api.fetchDiary('diary-1');
    expect(remote.content, '服务器正文');
    expect(remote.version, 4);
    expect(remote.tags, ['服务器标签']);
    api.dispose();
  });

  test('服务器未找到日记时保留状态码供回收站查找', () async {
    final api = DiaryApi(
        baseUrl: 'https://example.invalid',
        client: MockClient((request) async => http.Response('', 404)));
    await expectLater(
        api.fetchDiary('deleted'),
        throwsA(isA<DiaryApiException>()
            .having((error) => error.statusCode, 'statusCode', 404)));
    api.dispose();
  });
}
