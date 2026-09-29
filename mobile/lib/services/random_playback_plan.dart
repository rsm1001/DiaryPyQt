import 'dart:math';

import '../models/diary.dart';
import 'random_selector.dart';

class RandomPlaybackPlanner {
  RandomPlaybackPlanner({
    this.horizon = 8,
    Random? random,
  }) : _random = random ?? Random();

  final int horizon;
  final Random _random;
  final WeightedRandomSelector _selector = const WeightedRandomSelector();
  List<Diary> _candidates = const [];
  Map<String, RandomUsage> _virtualUsage = const {};
  final List<Diary> _plan = [];

  int get candidateCount => _candidates.length;

  void reset(
    List<Diary> candidates, {
    Map<String, RandomUsage> usage = const {},
  }) {
    _candidates = List.unmodifiable(candidates);
    _virtualUsage = Map.unmodifiable(usage);
    _plan.clear();
  }

  void replenish() {
    if (_candidates.isEmpty) return;
    while (_plan.length < horizon) {
      final diary = _selector.select(
        _candidates,
        usage: _virtualUsage,
        random: _random,
      );
      if (diary == null) return;
      _plan.add(diary);
      _virtualUsage = withRandomSelectionRecorded(
        _virtualUsage,
        diary.id,
        DateTime.now().toUtc(),
      );
    }
  }

  Diary? takeNext() {
    replenish();
    if (_plan.isEmpty) return null;
    return _plan.removeAt(0);
  }

  void requeue(Diary diary) {
    _plan.add(diary);
  }

  List<Diary> peek({int limit = 3}) => List.unmodifiable(
        _plan.take(limit).toList(growable: false),
      );

  void clear() {
    _candidates = const [];
    _virtualUsage = const {};
    _plan.clear();
  }
}
