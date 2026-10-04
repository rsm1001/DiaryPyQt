class ServerDailyStatistics {
  const ServerDailyStatistics({
    required this.startDate,
    required this.endDate,
    required this.totalEvents,
    required this.activeDays,
    required this.dailyCounts,
    this.yesterdayDate,
    this.yesterdayTotalViews,
    this.bestDayDate,
    this.bestDayViews,
  });

  final String startDate;
  final String endDate;
  final int totalEvents;
  final int activeDays;
  final Map<String, int> dailyCounts;
  final String? yesterdayDate;
  final int? yesterdayTotalViews;
  final String? bestDayDate;
  final int? bestDayViews;

  factory ServerDailyStatistics.fromJson(Map<String, dynamic> json) =>
      ServerDailyStatistics(
        startDate: json['start_date'] as String,
        endDate: json['end_date'] as String,
        totalEvents: (json['total_events'] as num?)?.toInt() ?? 0,
        activeDays: (json['active_days'] as num?)?.toInt() ?? 0,
        yesterdayDate: json['yesterday_date'] as String?,
        yesterdayTotalViews: (json['yesterday_total_views'] as num?)?.toInt(),
        bestDayDate: json['best_day_date'] as String?,
        bestDayViews: (json['best_day_views'] as num?)?.toInt(),
        dailyCounts: Map.unmodifiable(
          (json['daily_counts'] as Map<String, dynamic>? ?? const {})
              .map((key, value) => MapEntry(key, (value as num).toInt())),
        ),
      );
  Map<String, dynamic> toJson() => {
        'start_date': startDate,
        'end_date': endDate,
        'total_events': totalEvents,
        'active_days': activeDays,
        'daily_counts': dailyCounts,
        'yesterday_date': yesterdayDate,
        'yesterday_total_views': yesterdayTotalViews,
        'best_day_date': bestDayDate,
        'best_day_views': bestDayViews,
      };
}
