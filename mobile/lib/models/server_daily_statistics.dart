class ServerDailyStatistics {
  const ServerDailyStatistics({
    required this.startDate,
    required this.endDate,
    required this.totalEvents,
    required this.activeDays,
    required this.dailyCounts,
  });

  final String startDate;
  final String endDate;
  final int totalEvents;
  final int activeDays;
  final Map<String, int> dailyCounts;

  factory ServerDailyStatistics.fromJson(Map<String, dynamic> json) =>
      ServerDailyStatistics(
        startDate: json['start_date'] as String,
        endDate: json['end_date'] as String,
        totalEvents: (json['total_events'] as num?)?.toInt() ?? 0,
        activeDays: (json['active_days'] as num?)?.toInt() ?? 0,
        dailyCounts: Map.unmodifiable(
          (json['daily_counts'] as Map<String, dynamic>? ?? const {})
              .map((key, value) => MapEntry(key, (value as num).toInt())),
        ),
      );
}
