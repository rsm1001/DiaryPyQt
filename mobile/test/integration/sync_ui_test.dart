import 'package:diary_mobile/models/diary.dart';
import 'package:diary_mobile/services/double_playback_service.dart';
import 'package:diary_mobile/widgets/diary_list_body.dart';
import 'package:diary_mobile/widgets/random_playback_panel.dart';
import 'package:diary_mobile/widgets/sync_status_banner.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

const snapshot = PlaybackSnapshot(
  diaryId: null,
  stage: PlaybackStage.idle,
  roundNumber: 0,
  remainingGap: Duration.zero,
);

Diary sample() => const Diary(
      id: 'entry-id',
      date: '2026-09-27',
      content: '测试日记',
      contentHash: 'sha256:sample',
      version: 1,
      tags: ['工作'],
      updatedAt: '2026-09-27T00:00:00Z',
    );

void main() {
  test('同步冲突和网络错误展示不同提示', () {
    expect(describeSyncFailure(conflict: true, pending: 2),
        contains('\u7248\u672c\u51b2\u7a81'));
    expect(describeSyncFailure(conflict: false, pending: 3), contains('3 条'));
  });

  testWidgets('离线和待同步任务状态保持可见', (tester) async {
    await tester.pumpWidget(const MaterialApp(
      home: Scaffold(
        body: SyncStatusBanner(offline: true, syncing: false, pendingCount: 2),
      ),
    ));
    expect(find.text('已离线，2 条记录待同步'), findsOneWidget);
    await tester.pumpWidget(const MaterialApp(
      home: Scaffold(
        body: SyncStatusBanner(offline: false, syncing: true, pendingCount: 2),
      ),
    ));
    expect(find.text('正在同步，2 条记录待处理'), findsOneWidget);
  });

  testWidgets('日记列表在同步状态之外仍可查看和播放', (tester) async {
    var opened = 0;
    var played = 0;
    String? search;
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: DiaryListBody(
          diaries: Future.value([sample()]),
          searchQuery: '',
          selectedTag: null,
          playingDiaryId: null,
          snapshot: snapshot,
          onSearch: (value) => search = value,
          onTag: (_) {},
          onRefresh: () async {},
          onOpen: (_) async => opened++,
          onPlay: (_) async => played++,
        ),
      ),
    ));
    await tester.pumpAndSettle();
    expect(find.textContaining('测试日记'), findsOneWidget);
    await tester.enterText(find.byType(TextField), '工作');
    expect(search, '工作');
    await tester.tap(find.byIcon(Icons.play_arrow));
    expect(played, 1);
    await tester.tap(find.text('2026-09-27'));
    expect(opened, 1);
  });

  testWidgets('随机播放面板维持播放进度与停止控制', (tester) async {
    var starts = 0;
    var stops = 0;
    Future<void> start() async => starts++;
    Future<void> stop() async => stops++;
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: RandomPlaybackPanel(
          active: false,
          current: null,
          remaining: 0,
          snapshot: snapshot,
          onStart: start,
          onStop: stop,
        ),
      ),
    ));
    await tester.tap(find.text('开始随机连续播放'));
    expect(starts, 1);
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: RandomPlaybackPanel(
          active: true,
          current: sample(),
          remaining: 2,
          snapshot: const PlaybackSnapshot(
            diaryId: 'entry-id',
            stage: PlaybackStage.waiting,
            roundNumber: 1,
            remainingGap: Duration(seconds: 3),
            position: Duration(seconds: 1),
            duration: Duration(seconds: 10),
          ),
          onStart: start,
          onStop: stop,
        ),
      ),
    ));
    expect(find.textContaining('两遍之间等待中'), findsOneWidget);
    expect(find.text('1s / 10s'), findsOneWidget);
    await tester.tap(find.text('停止随机连续播放'));
    expect(stops, 1);
  });

  testWidgets('???????????????', (tester) async {
    String? selectedId;
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: DiaryListBody(
          diaries: Future.value([sample()]),
          searchQuery: '',
          selectedTag: null,
          playingDiaryId: null,
          snapshot: snapshot,
          selectionMode: true,
          selectedIds: const {},
          onToggleSelection: (id) => selectedId = id,
          onSearch: (_) {},
          onTag: (_) {},
          onRefresh: () async {},
          onOpen: (_) async {},
          onPlay: (_) async {},
        ),
      ),
    ));
    await tester.pumpAndSettle();
    await tester.tap(find.byType(Checkbox));
    expect(selectedId, 'entry-id');
  });
}
