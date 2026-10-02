import 'package:flutter/painting.dart';

List<TextSpan> diaryHighlightSpans(
  String text,
  List<String> terms,
  TextStyle highlightStyle,
) {
  if (terms.isEmpty) return [TextSpan(text: text)];
  final lower = text.toLowerCase();
  final matches = terms.where((term) => term.isNotEmpty).toList()
    ..sort((a, b) => b.length.compareTo(a.length));
  if (matches.isEmpty) return [TextSpan(text: text)];
  final spans = <TextSpan>[];
  var start = 0;
  var offset = 0;
  while (offset < text.length) {
    final match = matches.where((term) => lower.startsWith(term, offset));
    if (match.isEmpty) {
      offset++;
      continue;
    }
    if (offset > start) {
      spans.add(TextSpan(text: text.substring(start, offset)));
    }
    final end = offset + match.first.length;
    spans.add(
        TextSpan(text: text.substring(offset, end), style: highlightStyle));
    start = end;
    offset = end;
  }
  if (start < text.length) spans.add(TextSpan(text: text.substring(start)));
  return spans;
}
