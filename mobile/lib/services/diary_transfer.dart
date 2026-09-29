import 'dart:convert';

import '../models/diary.dart';

class DiaryImportEntry {
  const DiaryImportEntry(
      {required this.date, required this.content, required this.tags});

  final String date;
  final String content;
  final List<String> tags;
}

class DiaryImportPreview {
  const DiaryImportPreview({required this.entries, required this.skipped});

  final List<DiaryImportEntry> entries;
  final int skipped;
}

String exportDiariesJson(List<Diary> diaries) =>
    const JsonEncoder.withIndent('  ').convert({
      'format_version': 1,
      'diaries': diaries.map((diary) => diary.toJson()).toList(growable: false),
    });

List<DiaryImportEntry> parseDiaryImport(String source) {
  final dynamic decoded;
  try {
    decoded = jsonDecode(source);
  } on FormatException {
    throw const FormatException('Invalid diary JSON');
  }
  final items = decoded is List
      ? decoded
      : decoded is Map<String, dynamic>
          ? decoded['diaries']
          : null;
  if (items is! List || items.length > 2000) {
    throw const FormatException('Invalid diary list or too many entries');
  }
  return List<DiaryImportEntry>.unmodifiable(items.map((raw) {
    if (raw is! Map || raw['date'] is! String || raw['content'] is! String) {
      throw const FormatException('Missing diary date or content');
    }
    final date = (raw['date'] as String).trim();
    final content = (raw['content'] as String).trim();
    if (date.isEmpty || content.isEmpty || DateTime.tryParse(date) == null) {
      throw const FormatException('Invalid diary date or content');
    }
    final tags = raw['tags'];
    if (tags != null &&
        (tags is! List || tags.any((item) => item is! String))) {
      throw const FormatException('Invalid diary tags');
    }
    return DiaryImportEntry(
      date: date,
      content: content,
      tags: List<String>.unmodifiable(
        (tags as List? ?? const [])
            .cast<String>()
            .map((tag) => tag.trim())
            .where((tag) => tag.isNotEmpty)
            .toSet(),
      ),
    );
  }));
}

DiaryImportPreview previewDiaryImport(
  List<DiaryImportEntry> entries,
  List<Diary> current,
) {
  final keys = current.map((diary) => _key(diary.date, diary.content)).toSet();
  final unique = <DiaryImportEntry>[];
  var skipped = 0;
  for (final entry in entries) {
    if (keys.add(_key(entry.date, entry.content))) {
      unique.add(entry);
    } else {
      skipped++;
    }
  }
  return DiaryImportPreview(
      entries: List.unmodifiable(unique), skipped: skipped);
}

String _key(String date, String content) =>
    jsonEncode([date.trim(), content.trim()]);
