import 'dart:convert';

import 'package:diary_mobile/models/diary.dart';
import 'package:diary_mobile/services/diary_transfer.dart';
import 'package:flutter_test/flutter_test.dart';

Diary sample(String id, String content) => Diary(
      id: id,
      date: '2026-09-29',
      content: content,
      contentHash: 'sha256:test',
      version: 1,
      viewCount: 42,
      lastViewedAt: '2026-09-29T12:00:00Z',
      tags: const ['work'],
      updatedAt: '2026-09-29T12:00:00Z',
    );

void main() {
  test('export retains view statistics; import only carries content', () {
    final backup = exportDiariesJson([sample('old-id', 'entry')]);
    final saved = jsonDecode(backup) as Map<String, dynamic>;
    expect((saved['diaries'] as List).single['view_count'], 42);
    final entries = parseDiaryImport(backup);
    expect(entries.single.date, '2026-09-29');
    expect(entries.single.content, 'entry');
    expect(entries.single.tags, ['work']);
  });

  test('legacy desktop JSON array and duplicates are supported', () {
    final entries = parseDiaryImport(jsonEncode([
      {'id': 99, 'date': '2020-01-01', 'content': 'old', 'view_count': 10},
      {'date': '2020-01-01', 'content': 'old'},
      {'date': '2020-01-02', 'content': 'new'},
    ]));
    final preview = previewDiaryImport(entries, [sample('existing', 'other')]);
    expect(preview.entries, hasLength(2));
    expect(preview.skipped, 1);
    expect(preview.entries.first.tags, isEmpty);
  });

  test('invalid entry aborts entire preview', () {
    expect(() => parseDiaryImport('not json'), throwsFormatException);
    expect(
        () => parseDiaryImport(jsonEncode([
              {'date': '2020-01-01', 'content': 'safe'},
              {'date': 'not a date', 'content': 'bad'},
            ])),
        throwsFormatException);
    expect(
        () => parseDiaryImport(jsonEncode([
              {
                'date': '2020-01-01',
                'content': 'safe',
                'tags': [9]
              },
            ])),
        throwsFormatException);
  });
}
