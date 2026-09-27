import 'package:diary_mobile/models/diary.dart';
import 'package:diary_mobile/services/diary_filter.dart';
import 'package:flutter_test/flutter_test.dart';

Diary entry(String id, String content, List<String> tags) => Diary(
      id: id,
      date: '2026-09-26',
      content: content,
      contentHash: 'sha256:test',
      version: 1,
      tags: tags,
      updatedAt: '2026-09-26T00:00:00Z',
    );

void main() {
  test('搜索正文与标签，标签筛选可叠加且不更改原列表', () {
    final diaries = [
      entry('1', '项目进展', ['工作']),
      entry('2', '阅读记录', ['生活']),
    ];
    expect(filterDiaries(diaries, ' 进展 ', null).map((d) => d.id), ['1']);
    expect(filterDiaries(diaries, '生活', null).map((d) => d.id), ['2']);
    expect(filterDiaries(diaries, '', '工作').map((d) => d.id), ['1']);
    expect(filterDiaries(diaries, '阅读', '工作'), isEmpty);
    expect(diaries.length, 2);
  });
}
