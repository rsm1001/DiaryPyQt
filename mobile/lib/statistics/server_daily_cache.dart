import 'dart:convert';

import 'package:crypto/crypto.dart';
import 'package:sqflite/sqflite.dart';

import '../models/server_daily_statistics.dart';
import '../services/local_store.dart';

class CachedServerDailyStatistics {
  const CachedServerDailyStatistics({
    required this.statistics,
    required this.fetchedAt,
  });

  final ServerDailyStatistics statistics;
  final DateTime fetchedAt;
}

class ServerDailyCache {
  const ServerDailyCache(this.store);

  final LocalStore store;

  String _date(DateTime value) => '${value.year.toString().padLeft(4, '0')}-'
      '${value.month.toString().padLeft(2, '0')}-'
      '${value.day.toString().padLeft(2, '0')}';

  String _key(String scope, DateTime start, DateTime end) {
    final scoped = sha256.convert(utf8.encode(scope)).toString();
    return 'server_daily_cache_v1:$scoped:${_date(start)}:${_date(end)}';
  }

  bool _isCoherent(
      ServerDailyStatistics statistics, DateTime start, DateTime end) {
    final counts = statistics.dailyCounts;
    if (statistics.startDate != _date(start) ||
        statistics.endDate != _date(end) ||
        statistics.totalEvents < 0 ||
        statistics.activeDays != counts.length ||
        statistics.totalEvents !=
            counts.values.fold<int>(0, (total, count) => total + count) ||
        counts.entries.any((entry) =>
            entry.key.compareTo(statistics.startDate) < 0 ||
            entry.key.compareTo(statistics.endDate) > 0 ||
            entry.value <= 0)) {
      return false;
    }
    final yesterday = statistics.yesterdayTotalViews;
    final best = statistics.bestDayViews;
    return (statistics.yesterdayDate == null) == (yesterday == null) &&
        (yesterday == null || yesterday >= 0) &&
        (best == null ||
            (best >= 0 &&
                (statistics.bestDayDate == null) == (best == 0) &&
                (yesterday == null || best >= yesterday) &&
                counts.values.every((count) => best >= count)));
  }

  Future<CachedServerDailyStatistics?> load(
      String scope, DateTime start, DateTime end) async {
    final database = await store.database;
    final rows = await database.query('sync_state',
        columns: ['value'],
        where: 'key = ?',
        whereArgs: [_key(scope, start, end)],
        limit: 1);
    if (rows.isEmpty) return null;
    try {
      final payload = jsonDecode(rows.single['value'] as String);
      if (payload is! Map<String, dynamic>) return null;
      final fetchedAt = DateTime.tryParse(payload['fetched_at'] as String);
      final statistics = ServerDailyStatistics.fromJson(
          payload['statistics'] as Map<String, dynamic>);
      if (fetchedAt == null ||
          !fetchedAt.isUtc ||
          !_isCoherent(statistics, start, end)) {
        return null;
      }
      return CachedServerDailyStatistics(
          statistics: statistics, fetchedAt: fetchedAt);
    } on FormatException {
      return null;
    } on TypeError {
      return null;
    } on NoSuchMethodError {
      return null;
    }
  }

  Future<CachedServerDailyStatistics> save(
    String scope,
    DateTime start,
    DateTime end,
    ServerDailyStatistics statistics, {
    DateTime? fetchedAt,
  }) async {
    if (!_isCoherent(statistics, start, end)) {
      throw const FormatException('Invalid daily statistics');
    }
    final timestamp = (fetchedAt ?? DateTime.now()).toUtc();
    await (await store.database).insert(
      'sync_state',
      {
        'key': _key(scope, start, end),
        'value': jsonEncode({
          'fetched_at': timestamp.toIso8601String(),
          'statistics': statistics.toJson(),
        }),
      },
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
    return CachedServerDailyStatistics(
        statistics: statistics, fetchedAt: timestamp);
  }
}
