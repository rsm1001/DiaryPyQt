import 'package:sqflite/sqflite.dart';

class DeviceViewHistory {
  const DeviceViewHistory({
    required this.totalEvents,
    required this.pendingEvents,
    required this.dailyCounts,
  });

  final int totalEvents;
  final int pendingEvents;
  final Map<String, int> dailyCounts;
}

class DeviceViewRepository {
  const DeviceViewRepository(this.database);

  final Database database;

  static Future<void> createSchema(DatabaseExecutor db) async {
    await db.execute('CREATE TABLE IF NOT EXISTS device_view_events ('
        'event_id TEXT PRIMARY KEY, viewed_at_ms INTEGER NOT NULL, '
        'synced INTEGER NOT NULL DEFAULT 0)');
    await db.execute('CREATE INDEX IF NOT EXISTS device_view_events_by_time '
        'ON device_view_events (viewed_at_ms)');
  }

  static Future<void> record(
      Transaction transaction, String eventId, String viewedAt) async {
    final timestamp = DateTime.tryParse(viewedAt);
    if (timestamp == null) throw const FormatException('查看事件时间无效');
    await transaction.insert('device_view_events', {
      'event_id': eventId,
      'viewed_at_ms': timestamp.millisecondsSinceEpoch,
      'synced': 0,
    });
  }

  static Future<void> markSynced(Transaction transaction, String eventId) =>
      transaction.update('device_view_events', {'synced': 1},
          where: 'event_id = ?', whereArgs: [eventId]);

  Future<DeviceViewHistory> month(DateTime month) async {
    final start = DateTime(month.year, month.month).millisecondsSinceEpoch;
    final end = DateTime(month.year, month.month + 1).millisecondsSinceEpoch;
    return database.transaction((transaction) async {
      final totals = await transaction.rawQuery('SELECT COUNT(*) AS total, '
          'COALESCE(SUM(CASE WHEN synced = 0 THEN 1 ELSE 0 END), 0) AS pending '
          'FROM device_view_events');
      final events = await transaction.query('device_view_events',
          columns: ['viewed_at_ms'],
          where: 'viewed_at_ms >= ? AND viewed_at_ms < ?',
          whereArgs: [start, end]);
      final daily = <String, int>{};
      for (final event in events) {
        final date =
            DateTime.fromMillisecondsSinceEpoch(event['viewed_at_ms'] as int);
        final key = '${date.year.toString().padLeft(4, '0')}-'
            '${date.month.toString().padLeft(2, '0')}-'
            '${date.day.toString().padLeft(2, '0')}';
        daily[key] = (daily[key] ?? 0) + 1;
      }
      return DeviceViewHistory(
        totalEvents: totals.single['total'] as int,
        pendingEvents: totals.single['pending'] as int,
        dailyCounts: Map.unmodifiable(daily),
      );
    });
  }
}
