import 'package:diary_mobile/models/diary.dart';
import 'package:diary_mobile/search/diary_search_index.dart';
import 'package:diary_mobile/services/diary_filter.dart';
import 'package:flutter_test/flutter_test.dart';

Diary entry(
        String id, String date, String content, List<String> tags, int views) =>
    Diary(
      id: id,
      date: date,
      content: content,
      contentHash: '',
      version: 1,
      tags: tags,
      updatedAt: date,
      viewCount: views,
    );

void main() {
  final diaries = [
    entry('old', '2026-09-26', '散步 看电影', ['生活', '运动'], 8),
    entry('new', '2026-10-02', '项目进展：完成一半', ['工作', '重要'], 6),
    entry('other', '2026-10-02', '项目验收', ['工作'], 2),
  ];

  test('多关键词可跨正文、日期和标签，并保留原始顺序', () {
    final index = DiarySearchIndex(diaries);
    expect(index.search('  项目  重要 ', null).map((diary) => diary.id), ['new']);
    expect(index.search('2026-10  项目', null).map((diary) => diary.id),
        ['new', 'other']);
    expect(index.search('项目 散步', null), isEmpty);
    expect(index.search('', null), diaries);
    expect(diaries[1].viewCount, 6);
    expect(diaries[1].content, '项目进展：完成一半');
  });

  test('关键词、日期、查看次数、多标签和单标签可以叠加', () {
    final index = DiarySearchIndex(diaries);
    final options = DiarySearchOptions(
      from: DateTime(2026, 10, 2),
      to: DateTime(2026, 10, 2),
      minViews: 6,
      maxViews: 6,
      tags: const ['工作', '重要'],
    );
    expect(
        index.search('项目', '工作', options: options).map((d) => d.id), ['new']);
    expect(index.search('项目', '生活', options: options), isEmpty);
    expect(
        index.search('项目', null,
            options: DiarySearchOptions(
              from: DateTime(2026, 10, 3),
            )),
        isEmpty);
    expect(
        index.search('项目', null,
            options: DiarySearchOptions(
              minViews: 7,
            )),
        isEmpty);
    expect(
        filterDiaries(diaries, '项目', '工作', options: options)
            .map((diary) => diary.id),
        ['new']);
    expect(options.isActive, isTrue);
    expect(const DiarySearchOptions().isActive, isFalse);
    expect(index.search('', null), diaries);
  });

  test('缓存列表变化时重建索引，保留未同步本地编辑与查看数据', () {
    final original = DiarySearchIndex(diaries);
    final local = entry('local-1', '2026-10-02', '断网写作', ['离线'], 0);
    final refreshed = DiarySearchIndex([...diaries, local]);
    expect(original.search('断网', null), isEmpty);
    expect(refreshed.search('断网 写作', null).single.id, 'local-1');
    expect(refreshed.search('断网', null).single.viewCount, 0);
    expect(diaries.length, 3);
  });

  test('本地倒排索引在大量缓存中按短词和多词准确定位', () {
    final many = List.generate(
        2000, (i) => entry('$i', '2026-10-02', '普通日记内容 $i', ['记录'], i));
    many[1430] = entry('target', '2026-10-02', '唯一的火车站', ['旅途'], 3);
    final index = DiarySearchIndex(many);
    expect(index.search('火车 旅途', null).single.id, 'target');
    expect(index.search('车', '旅途').single.id, 'target');
    expect(index.search('火车 船', null), isEmpty);
  });
}
