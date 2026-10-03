import 'dart:convert';

import 'package:diary_mobile/models/diary.dart';
import 'package:diary_mobile/services/diary_api.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

Map<String, dynamic> diaryJson(int index) => {
      'id': 'trash-$index',
      'date': '2026-10-03',
      'content': '正文$index',
      'content_hash': 'hash:$index',
      'version': 2,
      'tags': <String>[],
      'updated_at': '',
      'deleted_at': '2026-10-03T00:00:00Z',
    };

void main() {
  test('回收站分页取得全部数据，清空不能遗漏第 501 篇', () async {
    final offsets = <String>[];
    final api = DiaryApi(
        baseUrl: 'https://example.invalid',
        client: MockClient((request) async {
          offsets.add(request.url.queryParameters['offset']!);
          final from = int.parse(request.url.queryParameters['offset']!);
          final items = List.generate(
              from == 0 ? 500 : 1, (index) => diaryJson(from + index));
          return http.Response.bytes(
              utf8.encode(jsonEncode({'items': items})), 200,
              headers: {'content-type': 'application/json; charset=utf-8'});
        }));
    addTearDown(api.dispose);
    final trash = await api.fetchTrash();
    expect(trash.length, 501);
    expect(trash.last.id, 'trash-500');
    expect(offsets, ['0', '500']);
  });

  test('永久删除只使用版本校验入口；冲突不降级为旧接口', () async {
    final requests = <http.Request>[];
    final api = DiaryApi(
        baseUrl: 'https://example.invalid',
        client: MockClient((request) async {
          requests.add(request);
          return http.Response('', 409);
        }));
    addTearDown(api.dispose);
    final diary = Diary.fromJson(diaryJson(4));
    await expectLater(
        api.permanentlyDeleteDiary(diary),
        throwsA(isA<DiaryApiException>()
            .having((error) => error.conflict, '版本冲突', true)));
    expect(requests, hasLength(1));
    expect(requests.single.url.path, '/api/v1/trash/trash-4/versions/2');
  });
}
