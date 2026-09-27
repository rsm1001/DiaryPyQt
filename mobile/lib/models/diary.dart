class Diary {
  const Diary({
    required this.id,
    required this.date,
    required this.content,
    required this.contentHash,
    required this.version,
    required this.tags,
    required this.updatedAt,
    this.viewCount = 0,
    this.lastViewedAt,
    this.deletedAt,
  });

  final String id;
  final String date;
  final String content;
  final String contentHash;
  final int version;
  final List<String> tags;
  final String updatedAt;
  final int viewCount;
  final String? lastViewedAt;
  final String? deletedAt;

  factory Diary.fromJson(Map<String, dynamic> json) {
    return Diary(
      id: json['id'] as String,
      date: json['date'] as String,
      content: json['content'] as String,
      contentHash: json['content_hash'] as String? ?? '',
      version: json['version'] as int? ?? 1,
      tags: (json['tags'] as List<dynamic>? ?? const [])
          .map((tag) => tag.toString())
          .toList(growable: false),
      updatedAt: json['updated_at'] as String? ?? '',
      viewCount: (json['view_count'] as num?)?.toInt() ?? 0,
      lastViewedAt: json['last_viewed_at'] as String?,
      deletedAt: json['deleted_at'] as String?,
    );
  }

  Diary copyWith({int? viewCount, String? lastViewedAt}) => Diary(
        id: id,
        date: date,
        content: content,
        contentHash: contentHash,
        version: version,
        tags: tags,
        updatedAt: updatedAt,
        viewCount: viewCount ?? this.viewCount,
        lastViewedAt: lastViewedAt ?? this.lastViewedAt,
        deletedAt: deletedAt,
      );

  Map<String, dynamic> toJson() => {
        'id': id,
        'date': date,
        'content': content,
        'content_hash': contentHash,
        'version': version,
        'tags': tags,
        'updated_at': updatedAt,
        'view_count': viewCount,
        'last_viewed_at': lastViewedAt,
        'deleted_at': deletedAt,
      };
}
