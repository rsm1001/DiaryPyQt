import 'dart:math';

import 'package:diary_mobile/deletion/random_deletion_policy.dart';
import 'package:diary_mobile/models/diary.dart';
import 'package:flutter_test/flutter_test.dart';

Diary entry(String id,
        {String date = '2026-09-30',
        int views = 0,
        List<String> tags = const [],
        String? deletedAt}) =>
    Diary(
      id: id,
      date: date,
      content: '内容$id',
      contentHash: 'hash:$id',
      version: 2,
      tags: tags,
      updatedAt: date,
      viewCount: views,
      deletedAt: deletedAt,
    );

void main() {
  const policy = RandomDeletionPolicy();
  final now = DateTime(2026, 10, 3);

  test('日期、查看次数和标签筛选只保留安全候选，不修改原数据', () {
    final old = entry('old', date: '2021-01-01', views: 20, tags: ['工作', '重要']);
    final entries = [
      old,
      entry('new', date: '2026-10-02', views: 1, tags: ['工作']),
      entry('future', date: '2026-10-05', views: 100, tags: ['工作']),
      entry('local-draft', date: '2021-01-01', views: 100, tags: ['工作']),
      entry('removed',
          date: '2021-01-01',
          views: 100,
          tags: ['工作'],
          deletedAt: '2026-09-01'),
    ];
    final filtered = policy.candidates(entries,
        filters: DeletionFilters(
            before: DateTime(2025, 12, 31),
            minViews: 10,
            maxViews: 30,
            tag: '工作'),
        now: now);
    expect(filtered, [old]);
    expect(
        policy
            .candidates(entries, excluded: {'old'}, now: now)
            .map((diary) => diary.id),
        ['new']);
    expect(entries.length, 5);
    expect(old.viewCount, 20);
    expect(old.deletedAt, isNull);
  });

  test('删除权重单独偏好较旧且查看较多的日记，不读取播放历史', () {
    final older = entry('older', date: '2020-01-01', views: 40);
    final middle = entry('middle', date: '2023-01-01', views: 10);
    final recent = entry('recent', date: '2026-10-02', views: 1);
    final weights = policy.weights([older, middle, recent], now: now);
    expect(weights['older'], greaterThan(weights['middle']!));
    expect(weights['middle'], greaterThan(weights['recent']!));
    expect(policy.draw([older, middle, recent], now: now, random: Random(1)),
        isNotNull);
    expect(policy.weights([recent, middle, older], now: now)['older'],
        weights['older']);
  });

  test('同龄日记依据查看次数评分，同分获得相同权重', () {
    final many = entry('many', views: 20);
    final few = entry('few', views: 1);
    final equal = entry('equal', views: 20);
    final weights = policy.weights([few, many, equal], now: now);
    expect(weights['many'], weights['equal']);
    expect(weights['many'], greaterThan(weights['few']!));
    expect(policy.weights([many], now: now)['many'], 0.5);
    expect(policy.draw([], now: now), isNull);
  });

  test('非法查看范围拒绝；未来和非法日期不参与删除抽取', () {
    expect(
        () => policy.candidates([entry('a')],
            filters: const DeletionFilters(minViews: 5, maxViews: 1), now: now),
        throwsFormatException);
    expect(
        policy.candidates(
            [entry('a', date: 'future'), entry('b', date: '2026-10-04')],
            now: now),
        isEmpty);
  });
}
