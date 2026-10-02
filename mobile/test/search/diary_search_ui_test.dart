import 'package:diary_mobile/models/diary.dart';
import 'package:diary_mobile/pages/advanced_search_dialog.dart';
import 'package:diary_mobile/search/diary_highlight.dart';
import 'package:diary_mobile/services/diary_filter.dart';
import 'package:diary_mobile/services/double_playback_service.dart';
import 'package:diary_mobile/widgets/diary_list_body.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  final diaries = [
    const Diary(
        id: '1',
        date: '2026-09-29',
        content: '读书',
        contentHash: '',
        version: 1,
        tags: ['生活'],
        updatedAt: '',
        viewCount: 1),
    const Diary(
        id: '2',
        date: '2026-10-02',
        content: '项目进展',
        contentHash: '',
        version: 1,
        tags: ['工作', '重要'],
        updatedAt: '',
        viewCount: 8),
  ];
  const snapshot = PlaybackSnapshot(
      diaryId: null,
      stage: PlaybackStage.idle,
      roundNumber: 0,
      remainingGap: Duration.zero);

  test('高亮多关键词保留原文，重叠词不重复覆盖', () {
    const highlight = TextStyle(backgroundColor: Colors.yellow);
    final spans = diaryHighlightSpans('项目进展项目', ['项目', '进展', '项目进'], highlight);
    expect(spans.map((span) => span.text).join(), '项目进展项目');
    expect(
        spans.where((span) => span.style == highlight).map((span) => span.text),
        ['项目进', '项目']);
    expect(diaryHighlightSpans('无匹配', [], highlight).single.text, '无匹配');
  });

  testWidgets('断网缓存组合筛选后可一键清除，关键词在列表高亮', (tester) async {
    var query = '项目 进展';
    String? tag = '工作';
    var options = DiarySearchOptions(minViews: 5, tags: const ['重要']);
    final future = Future.value(diaries);
    await tester.pumpWidget(MaterialApp(
        home: Scaffold(
            body: StatefulBuilder(
      builder: (context, refresh) => DiaryListBody(
        diaries: future,
        searchQuery: query,
        selectedTag: tag,
        searchOptions: options,
        playingDiaryId: null,
        snapshot: snapshot,
        onSearch: (text) => refresh(() => query = text),
        onTag: (value) => refresh(() => tag = value),
        onClearFilters: () => refresh(() {
          query = '';
          tag = null;
          options = const DiarySearchOptions();
        }),
        onRefresh: () async {},
        onOpen: (_) async {},
        onPlay: (_) async {},
      ),
    ))));
    await tester.pumpAndSettle();
    expect(find.textContaining('项目进展'), findsOneWidget);
    expect(find.textContaining('读书'), findsNothing);
    final row = tester.widget<ListTile>(find.byType(ListTile).first);
    final subtitle = row.subtitle! as Text;
    final highlighted = (subtitle.textSpan! as TextSpan).children!.cast<TextSpan>()
        .where((span) => span.style?.backgroundColor != null);
    expect(highlighted.map((span) => span.text).join(), '项目进展');
    await tester.tap(find.text('清除全部筛选'));
    await tester.pumpAndSettle();
    expect(find.textContaining('读书'), findsOneWidget);
    expect(find.text('清除全部筛选'), findsNothing);
    expect(
        tester.widget<TextField>(find.byType(TextField)).controller!.text, '');
    expect(diaries.last.viewCount, 8);
  });

  testWidgets('高级搜索可组合多个标签并校验查看次数', (tester) async {
    DiarySearchOptions? result;
    await tester.pumpWidget(MaterialApp(
        home: Scaffold(
            body: Builder(
      builder: (context) => TextButton(
        onPressed: () async {
          result = await showAdvancedSearchDialog(
              context, const DiarySearchOptions(),
              availableTags: ['工作', '重要']);
        },
        child: const Text('打开搜索'),
      ),
    ))));
    await tester.tap(find.text('打开搜索'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));
    await tester.tap(find.text('工作'));
    await tester.tap(find.text('重要'));
    await tester.enterText(find.byType(TextField).first, '5');
    await tester.enterText(find.byType(TextField).last, '3');
    await tester.tap(find.text('应用'));
    await tester.pump();
    expect(find.text('高级搜索'), findsOneWidget);
    await tester.enterText(find.byType(TextField).last, '9');
    await tester.tap(find.text('应用'));
    await tester.pumpAndSettle();
    expect(result!.tags, ['工作', '重要']);
    expect(result!.minViews, 5);
    expect(result!.maxViews, 9);
  });
}
