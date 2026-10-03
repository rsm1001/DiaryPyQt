class PlaybackRecord {
  const PlaybackRecord({
    required this.id,
    required this.deviceId,
    required this.diaryId,
    required this.voiceId,
    required this.roundNumber,
    required this.positionMs,
    required this.status,
    required this.updatedAt,
  });

  final String id;
  final String deviceId;
  final String diaryId;
  final String voiceId;
  final int roundNumber;
  final int positionMs;
  final String status;
  final String updatedAt;

  factory PlaybackRecord.fromJson(Map<String, dynamic> json) => PlaybackRecord(
        id: json['id'] as String? ?? '',
        deviceId: json['device_id'] as String,
        diaryId: json['diary_id'] as String,
        voiceId: json['voice_id'] as String,
        roundNumber: (json['round_number'] as num).toInt(),
        positionMs: (json['position_ms'] as num).toInt(),
        status: json['status'] as String,
        updatedAt: json['updated_at'] as String,
      );

  Map<String, dynamic> toJson() => {
        'id': id,
        'device_id': deviceId,
        'diary_id': diaryId,
        'voice_id': voiceId,
        'round_number': roundNumber,
        'position_ms': positionMs,
        'status': status,
        'updated_at': updatedAt,
      };
}
