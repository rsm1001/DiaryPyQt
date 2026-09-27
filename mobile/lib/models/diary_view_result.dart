class DiaryViewResult {
  const DiaryViewResult({required this.viewCount, required this.viewedAt});

  final int viewCount;
  final String viewedAt;

  factory DiaryViewResult.fromJson(Map<String, dynamic> json) => DiaryViewResult(
        viewCount: (json['view_count'] as num?)?.toInt() ?? 0,
        viewedAt: json['viewed_at'] as String? ?? '',
      );
}
