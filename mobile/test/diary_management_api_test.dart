import 'dart:convert';

import 'package:diary_mobile/models/diary.dart';
import 'package:diary_mobile/services/diary_api.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

Map<String, dynamic> diaryJson({int version = 1}) => {
      'id': 'entry-id',
      'date': '2026-09-26',
      'content': 'entry',
      'content_hash': 'sha256:sample',
      'version': version,
      'tags': ['work'],
      'updated_at': '2026-09-26T00:00:00Z',
    };

void main() {
  test('diary CRUD uses version and request authentication', () async {
    final requests = <http.Request>[];
    final client = MockClient((request) async {
      requests.add(request);
      if (request.method == 'DELETE') return http.Response('', 204);
      return http.Response.bytes(
        utf8.encode(jsonEncode(diaryJson(version: requests.length))),
        request.method == 'POST' ? 201 : 200,
        headers: {'content-type': 'application/json; charset=utf-8'},
      );
    });
    final api = DiaryApi(
        client: client,
        baseUrl: 'https://example.invalid',
        password: 'unit-test');
    final created = await api
        .createDiary(date: '2026-09-26', content: 'entry', tags: ['work']);
    final updated = await api
        .updateDiary(created, content: 'updated', tags: ['work', 'life']);
    await api.deleteDiary(updated);

    expect(
        requests.map((request) => request.method), ['POST', 'PATCH', 'DELETE']);
    expect(requests[1].url.path, '/api/v1/diaries/entry-id');
    expect(jsonDecode(requests[1].body)['version'], created.version);
    expect(requests[2].url.queryParameters['version'], '${updated.version}');
    for (final request in requests) {
      final headers = {
        for (final header in request.headers.entries)
          header.key.toLowerCase(): header.value,
      };
      expect(headers['authorization'],
          'Basic ${base64Encode(utf8.encode('diary:unit-test'))}');
      expect(headers['x-request-id'], isNotEmpty);
    }
    api.dispose();
  });

  test('version conflict is reported as failure', () async {
    final api = DiaryApi(
      client: MockClient((request) async => http.Response('', 409)),
      baseUrl: 'https://example.invalid',
    );
    final diary = Diary.fromJson(diaryJson());
    await expectLater(
      api.updateDiary(diary, content: 'offline edit', tags: ['work']),
      throwsA(isA<DiaryApiException>()
          .having((error) => error.message, 'message', isNotEmpty)),
    );
    api.dispose();
  });

  test('view event returns server count', () async {
    final api = DiaryApi(
      client: MockClient((request) async => http.Response.bytes(
            utf8.encode(jsonEncode({
              'diary_id': 'entry-id',
              'view_count': 7,
              'viewed_at': '2026-09-26T00:00:00Z'
            })),
            200,
            headers: {'content-type': 'application/json; charset=utf-8'},
          )),
      baseUrl: 'https://example.invalid',
    );
    final result = await api.recordView(Diary.fromJson(diaryJson()));
    expect(result.viewCount, 7);
    expect(result.viewedAt, '2026-09-26T00:00:00Z');
    api.dispose();
  });

  test('statistics API parses server view counts', () async {
    final api = DiaryApi(
      client: MockClient((request) async => http.Response.bytes(
            utf8.encode(jsonEncode({
              'total_diaries': 303,
              'total_views': 17,
              'average_views': 0.056,
              'most_viewed_id': 'entry-id',
              'most_viewed_count': 4,
              'least_viewed_id': 'other-id',
              'least_viewed_count': 0,
            })),
            200,
            headers: {'content-type': 'application/json; charset=utf-8'},
          )),
      baseUrl: 'https://example.invalid',
    );
    final statistics = await api.fetchStatistics();
    expect(statistics.totalDiaries, 303);
    expect(statistics.totalViews, 17);
    expect(statistics.mostViewedId, 'entry-id');
    api.dispose();
  });

  test('trash API supports list, restore, and permanent delete', () async {
    final requests = <http.Request>[];
    final client = MockClient((request) async {
      requests.add(request);
      if (request.method == 'GET') {
        return http.Response.bytes(
          utf8.encode(jsonEncode({
            'items': [diaryJson()]
          })),
          200,
          headers: {'content-type': 'application/json; charset=utf-8'},
        );
      }
      if (request.method == 'DELETE') return http.Response('', 204);
      return http.Response.bytes(
        utf8.encode(jsonEncode(diaryJson(version: 2))),
        200,
        headers: {'content-type': 'application/json; charset=utf-8'},
      );
    });
    final api = DiaryApi(client: client, baseUrl: 'https://example.invalid');
    final trash = await api.fetchTrash();
    await api.restoreDiary(trash.single);
    await api.permanentlyDeleteDiary(trash.single);
    expect(
        requests.map((request) => request.method), ['GET', 'POST', 'DELETE']);
    api.dispose();
  });

  test('tag API supports list, create, rename, and delete', () async {
    final requests = <http.Request>[];
    final client = MockClient((request) async {
      requests.add(request);
      if (request.method == 'GET') {
        return http.Response.bytes(
          utf8.encode(jsonEncode({
            'items': [
              {
                'id': 'tag-1',
                'name': 'study',
                'created_at': '2026-09-26T00:00:00Z'
              }
            ]
          })),
          200,
          headers: {'content-type': 'application/json; charset=utf-8'},
        );
      }
      if (request.method == 'DELETE') return http.Response('', 204);
      return http.Response.bytes(
        utf8.encode(jsonEncode({
          'id': 'tag-1',
          'name': 'research',
          'created_at': '2026-09-26T00:00:00Z'
        })),
        request.method == 'POST' ? 201 : 200,
        headers: {'content-type': 'application/json; charset=utf-8'},
      );
    });
    final api = DiaryApi(client: client, baseUrl: 'https://example.invalid');
    expect((await api.fetchTags()).single.name, 'study');
    final created = await api.createTag('research');
    final renamed = await api.updateTag(created, 'research');
    await api.deleteTag(renamed);
    expect(requests.map((request) => request.method),
        ['GET', 'POST', 'PATCH', 'DELETE']);
    api.dispose();
  });
}
