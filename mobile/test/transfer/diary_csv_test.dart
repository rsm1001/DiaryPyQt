import 'dart:convert';

import 'package:diary_mobile/models/diary.dart';
import 'package:diary_mobile/transfer/diary_csv.dart';
import 'package:diary_mobile/transfer/diary_transfer.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  final diary = Diary(
    id: 'old-id',
    date: '2026-09-29',
    content: '一行,"引号"\n下一行',
    contentHash: 'sha256:test',
    version: 1,
    tags: const ['工作', '生活'],
    updatedAt: '2026-09-29T12:00:00Z',
    viewCount: 42,
  );

  test('与电脑端字段兼容，处理引号、多行、中文和历史查看次数', () {
    final csv = exportDiariesCsv([diary]);
    expect(csv, contains('"view_count"'));
    final result = parseDiariesCsv('\uFEFF$csv');
    expect(result.errors, 0);
    expect(result.entries.single.content, diary.content);
    expect(result.entries.single.tags, diary.tags);
    expect(result.entries.single.date, diary.date);
    expect(result.entries.single.content, isNot(contains('42')));
  });

  test('重复日记按日期和正文判定，查看次数不参与去重', () {
    final source = 'date,content,view_count,tags\n'
        '2026-09-29,"一行,""引号""\n下一行",999,"[""工作""]"\n';
    final parsed = parseDiariesCsv(source);
    final preview =
        previewDiaryImport(parsed.entries, [diary], errors: parsed.errors);
    expect(preview.skipped, 1);
    expect(preview.entries, isEmpty);
  });

  test('缺列、空文件、超大文件和 CSV 格式错误均拒绝', () {
    expect(() => parseDiariesCsv(''), throwsFormatException);
    expect(() => parseDiariesCsv('date,tags\n2026-09-29,a'),
        throwsFormatException);
    expect(() => parseDiariesCsv('date,content\n"unterminated'),
        throwsFormatException);
    expect(() => parseDiariesCsv('date,content\n'), throwsFormatException);
    expect(() => parseDiariesCsv('a' * (5 * 1024 * 1024 + 1)),
        throwsFormatException);
  });

  test('非法日期、查看次数和标签计入错误，不把有效行直接导入', () {
    final csv = 'date,content,tags,view_count\n'
        '2026-02-29,bad,,0\n'
        '2026-09-29,valid,"[""工作""]",8\n'
        '2026-09-30,nope,,minus\n'
        '2026-10-01,invalid,"[1]",0\n';
    final parsed = parseDiariesCsv(csv);
    final preview =
        previewDiaryImport(parsed.entries, [], errors: parsed.errors);
    expect(preview.errors, 3);
    expect(preview.entries, hasLength(1));
    expect(preview.entries.single.tags, ['工作']);
  });

  test('导出时为公式前缀添加防护', () {
    final risky = Diary(
      id: 'id',
      date: diary.date,
      content: '=1+2',
      contentHash: '',
      version: 1,
      tags: const ['@command'],
      updatedAt: '',
    );
    final csv = exportDiariesCsv([risky]);
    expect(csv, contains('"\'=1+2"'));
    expect(parseDiariesCsv(csv).entries.single.tags, ['@command']);
    expect(jsonEncode(parseDiariesCsv(csv).entries.single.content),
        contains("'=1+2"));
  });
}
