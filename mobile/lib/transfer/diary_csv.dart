import 'dart:convert';

import '../models/diary.dart';
import 'diary_transfer.dart';

class DiaryCsvParseResult {
  const DiaryCsvParseResult(this.entries, this.errors);

  final List<DiaryImportEntry> entries;
  final int errors;
}

const _fields = [
  'id',
  'date',
  'content',
  'view_count',
  'last_viewed_at',
  'updated_at',
  'tags'
];

String exportDiariesCsv(List<Diary> diaries) {
  final rows = <List<String>>[_fields];
  for (final diary in diaries) {
    rows.add([
      diary.id,
      diary.date,
      diary.content,
      '${diary.viewCount}',
      diary.lastViewedAt ?? '',
      diary.updatedAt,
      jsonEncode(diary.tags),
    ]);
  }
  return '${rows.map((row) => row.map(_csvCell).join(',')).join('\r\n')}\r\n';
}

String _csvCell(String value) {
  // 防止电子表格把日记正文或标签作为公式执行。
  final safe =
      value.isNotEmpty && '=+-@\t\r'.contains(value[0]) ? "'$value" : value;
  return '"${safe.replaceAll('"', '""')}"';
}

DiaryCsvParseResult parseDiariesCsv(String source) {
  if (utf8.encode(source).length > 5 * 1024 * 1024) {
    throw const FormatException('CSV 文件超过 5 MB');
  }
  final rows = _parseRows(source.replaceFirst('\uFEFF', ''));
  if (rows.isEmpty || rows.first.isEmpty) {
    throw const FormatException('CSV 文件为空');
  }
  final header = rows.first.map((value) => value.trim()).toList();
  if (header.toSet().length != header.length ||
      !header.contains('date') ||
      !header.contains('content')) {
    throw const FormatException('CSV 缺少日期或正文字段');
  }
  final entries = <DiaryImportEntry>[];
  var errors = 0;
  for (final row in rows.skip(1)) {
    if (row.length != header.length || entries.length >= 2000) {
      errors++;
      continue;
    }
    final fields = Map.fromIterables(header, row);
    final date = (fields['date'] ?? '').trim();
    final content = (fields['content'] ?? '').trim();
    final parsedDate = DateTime.tryParse(date);
    final viewCount = (fields['view_count'] ?? '').trim();
    if (!RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(date) ||
        parsedDate == null ||
        parsedDate.year.toString().padLeft(4, '0') != date.substring(0, 4) ||
        parsedDate.month.toString().padLeft(2, '0') != date.substring(5, 7) ||
        parsedDate.day.toString().padLeft(2, '0') != date.substring(8, 10) ||
        content.isEmpty ||
        (viewCount.isNotEmpty &&
            (int.tryParse(viewCount) == null || int.parse(viewCount) < 0))) {
      errors++;
      continue;
    }
    try {
      entries.add(DiaryImportEntry(
          date: date,
          content: content,
          tags: _parseTags(fields['tags'] ?? '')));
    } on FormatException {
      errors++;
    }
  }
  if (rows.length == 1) throw const FormatException('CSV 文件没有日记');
  return DiaryCsvParseResult(List.unmodifiable(entries), errors);
}

List<String> _parseTags(String value) {
  final raw = value.trim();
  if (raw.isEmpty) return const [];
  if (!raw.startsWith('[')) {
    return raw
        .split(',')
        .map((tag) => tag.trim())
        .where((tag) => tag.isNotEmpty)
        .toSet()
        .toList();
  }
  final parsed = jsonDecode(raw);
  if (parsed is! List) throw const FormatException('标签格式无效');
  return parsed
      .map((tag) {
        final name = tag is Map ? tag['name'] : tag;
        if (name is! String) throw const FormatException('标签格式无效');
        return name.trim();
      })
      .where((tag) => tag.isNotEmpty)
      .toSet()
      .toList();
}

List<List<String>> _parseRows(String source) {
  final rows = <List<String>>[];
  var row = <String>[];
  var cell = StringBuffer();
  var quoted = false;
  var closed = false;
  for (var index = 0; index < source.length; index++) {
    final char = source[index];
    if (quoted) {
      if (char == '"') {
        if (index + 1 < source.length && source[index + 1] == '"') {
          cell.write('"');
          index++;
        } else {
          quoted = false;
          closed = true;
        }
      } else {
        cell.write(char);
      }
    } else if (char == '"' && cell.isEmpty && !closed) {
      quoted = true;
    } else if (char == ',') {
      row.add(cell.toString());
      cell = StringBuffer();
      closed = false;
    } else if (char == '\n' || char == '\r') {
      row.add(cell.toString());
      rows.add(row);
      row = <String>[];
      cell = StringBuffer();
      closed = false;
      if (char == '\r' &&
          index + 1 < source.length &&
          source[index + 1] == '\n') {
        index++;
      }
    } else {
      if (closed || char == '"') throw const FormatException('CSV 引号格式无效');
      cell.write(char);
    }
  }
  if (quoted) throw const FormatException('CSV 引号未闭合');
  if (cell.isNotEmpty || row.isNotEmpty) {
    row.add(cell.toString());
    rows.add(row);
  }
  return rows;
}
