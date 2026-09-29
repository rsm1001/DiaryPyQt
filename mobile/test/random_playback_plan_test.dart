import 'dart:math';

import 'package:diary_mobile/models/diary.dart';
import 'package:diary_mobile/services/random_playback_plan.dart';
import 'package:flutter_test/flutter_test.dart';

Diary diary(String id) => Diary(
      id: id,
      date: '2026-09-28',
      content: id,
      contentHash: 'sha256:$id',
      version: 1,
      tags: const [],
      updatedAt: '2026-09-28T00:00:00Z',
    );

void main() {
  test('planned random playback samples with replacement', () {
    final planner = RandomPlaybackPlanner(horizon: 6, random: Random(1));
    planner.reset([diary('only')]);

    final plan = <String>[];
    for (var index = 0; index < 6; index++) {
      plan.add(planner.takeNext()!.id);
    }

    expect(plan, everyElement('only'));
    expect(planner.candidateCount, 1);
  });

  test('duplicate plan entries remain separate playback occurrences', () {
    final planner = RandomPlaybackPlanner(horizon: 3, random: Random(2));
    planner.reset([diary('a'), diary('b')]);
    final first = planner.takeNext()!;
    planner.requeue(first);

    final plan = planner.peek(limit: 3);
    expect(plan.where((item) => item.id == first.id), isNotEmpty);
    expect(planner.candidateCount, 2);
  });
}
