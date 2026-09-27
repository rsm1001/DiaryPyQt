import 'dart:convert';

import 'package:diary_mobile/services/diary_api.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test('server check verifies service identity and paginates all diaries',
      () async {
    final offsets = <int>[];
    final client = MockClient((request) async {
      if (request.url.path == '/health') {
        return http.Response(
            jsonEncode({'status': 'ok', 'service': 'diary-server'}), 200);
      }
      expect(request.url.path, '/api/v1/diaries');
      final offset = int.parse(request.url.queryParameters['offset']!);
      offsets.add(offset);
      final count = offset == 0 ? 500 : 1;
      return http.Response(
          jsonEncode({
            'items': List.generate(
                count,
                (i) => {
                      'id': 'id-${offset + i}',
                      'date': '2026-09-26',
                      'content': 'entry',
                      'content_hash': 'hash',
                      'version': 1,
                      'tags': <String>[],
                      'updated_at': '2026-09-26T00:00:00Z'
                    })
          }),
          200);
    });
    final api = DiaryApi(client: client, baseUrl: 'http://127.0.0.1:8010/');
    await api.checkConnection();
    final entries = await api.fetchDiaries();
    expect(entries.length, 501);
    expect(entries.last.id, 'id-500');
    expect(offsets, [0, 500]);
    api.dispose();
  });
}
