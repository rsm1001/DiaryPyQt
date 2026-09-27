import 'dart:convert';

class DiaryTag {
  const DiaryTag(
      {required this.id, required this.name, required this.createdAt});

  final String id;
  final String name;
  final String createdAt;

  factory DiaryTag.fromJson(Map<String, dynamic> json) => DiaryTag(
        id: json['id'] as String,
        name: json['name'] as String,
        createdAt: json['created_at'] as String? ?? '',
      );

  Map<String, dynamic> toJson() => <String, dynamic>{
        'id': id,
        'name': name,
        'created_at': createdAt,
      };

  @override
  String toString() => jsonEncode(toJson());
}
