import 'package:diary_mobile/models/app_preferences.dart';
import 'package:diary_mobile/models/diary.dart';
import 'package:diary_mobile/services/double_playback_service.dart';
import 'package:diary_mobile/widgets/diary_list_body.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';

const _snapshot = PlaybackSnapshot(
  diaryId: null,
  stage: PlaybackStage.idle,
  roundNumber: 0,
  remainingGap: Duration.zero,
);

Diary _diary(String id, String date, String content, int views) => Diary(
      id: id,
      date: date,
      content: content,
      contentHash: 'hash:$id',
      version: 1,
      tags: const ['personal'],
      updatedAt: date,
      viewCount: views,
    );

void main() {
  testWidgets('hidden list fields keep search, opening, playback and selection',
      (tester) async {
    final diaries = List<Diary>.unmodifiable([
      _diary('one', '2026-10-01', 'searchable secret', 8),
    ]);
    String? opened;
    String? played;
    String? selected;
    await tester.pumpWidget(MaterialApp(
      locale: const Locale('en', 'US'),
      supportedLocales: const [Locale('zh', 'CN'), Locale('en', 'US')],
      localizationsDelegates: GlobalMaterialLocalizations.delegates,
      home: Scaffold(
        body: DiaryListBody(
          diaries: Future.value(diaries),
          searchQuery: 'secret',
          selectedTag: null,
          playingDiaryId: null,
          snapshot: _snapshot,
          preferences: const AppPreferences(
            showDate: false,
            showViews: false,
            showTags: false,
            showPreview: false,
          ),
          onSearch: (_) {},
          onTag: (_) {},
          onRefresh: () async {},
          onOpen: (diary) async => opened = diary.id,
          onPlay: (diary) async => played = diary.id,
          onToggleSelection: (id) => selected = id,
        ),
      ),
    ));
    await tester.pumpAndSettle();
    expect(find.text('Diary'), findsOneWidget);
    expect(find.text('2026-10-01'), findsNothing);
    expect(find.text('searchable secret'), findsNothing);
    expect(find.text('List fields are hidden'), findsOneWidget);
    await tester.tap(find.byIcon(Icons.play_arrow));
    await tester.tap(find.text('Diary'));
    await tester.longPress(find.text('Diary'));
    expect((played, opened, selected), ('one', 'one', 'one'));
    expect(diaries.single.content, 'searchable secret');
  });

  testWidgets('view sorting does not mutate cached diary ordering',
      (tester) async {
    final diaries = List<Diary>.unmodifiable([
      _diary('new', '2026-10-02', 'new entry', 1),
      _diary('old', '2026-09-30', 'old entry', 9),
    ]);
    Future<void> build(AppPreferences preferences) => tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: DiaryListBody(
                diaries: Future.value(diaries),
                searchQuery: '',
                selectedTag: null,
                playingDiaryId: null,
                snapshot: _snapshot,
                preferences: preferences,
                onSearch: (_) {},
                onTag: (_) {},
                onRefresh: () async {},
                onOpen: (_) async {},
                onPlay: (_) async {},
              ),
            ),
          ),
        );
    List<String> visibleDates() => tester
        .widgetList<ListTile>(find.descendant(
          of: find.byType(Card),
          matching: find.byType(ListTile),
        ))
        .map((tile) => (tile.title! as Text).textSpan!.toPlainText())
        .toList();
    await build(const AppPreferences(sortField: DiarySortField.views));
    await tester.pumpAndSettle();
    expect(visibleDates(), ['2026-09-30', '2026-10-02']);
    await build(const AppPreferences(sortField: DiarySortField.date));
    await tester.pumpAndSettle();
    expect(visibleDates(), ['2026-10-02', '2026-09-30']);
    expect(diaries.map((diary) => diary.id), ['new', 'old']);
  });
}
