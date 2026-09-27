class ServerStatistics {
  const ServerStatistics({
    required this.totalDiaries,
    required this.totalViews,
    required this.averageViews,
    required this.mostViewedId,
    required this.mostViewedCount,
    required this.leastViewedId,
    required this.leastViewedCount,
  });

  final int totalDiaries;
  final int totalViews;
  final double averageViews;
  final String? mostViewedId;
  final int mostViewedCount;
  final String? leastViewedId;
  final int leastViewedCount;

  factory ServerStatistics.fromJson(Map<String, dynamic> json) =>
      ServerStatistics(
        totalDiaries: (json['total_diaries'] as num?)?.toInt() ?? 0,
        totalViews: (json['total_views'] as num?)?.toInt() ?? 0,
        averageViews: (json['average_views'] as num?)?.toDouble() ?? 0,
        mostViewedId: json['most_viewed_id'] as String?,
        mostViewedCount: (json['most_viewed_count'] as num?)?.toInt() ?? 0,
        leastViewedId: json['least_viewed_id'] as String?,
        leastViewedCount: (json['least_viewed_count'] as num?)?.toInt() ?? 0,
      );
}
