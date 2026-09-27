class AudioAsset {
  const AudioAsset({
    required this.id,
    required this.diaryId,
    required this.voiceId,
    required this.contentHash,
    required this.fileHash,
    required this.durationMs,
    required this.downloadUrl,
    this.localPath,
  });

  final String id;
  final String diaryId;
  final String voiceId;
  final String contentHash;
  final String fileHash;
  final int durationMs;
  final String downloadUrl;
  final String? localPath;

  AudioAsset copyWith({String? localPath}) => AudioAsset(
        id: id,
        diaryId: diaryId,
        voiceId: voiceId,
        contentHash: contentHash,
        fileHash: fileHash,
        durationMs: durationMs,
        downloadUrl: downloadUrl,
        localPath: localPath ?? this.localPath,
      );

  factory AudioAsset.fromJson(Map<String, dynamic> json, String baseUrl) {
    final path = json['download_url'] as String? ?? '';
    final url = path.startsWith('http') ? path : '$baseUrl$path';
    return AudioAsset(
      id: json['id'] as String,
      diaryId: json['diary_id'] as String,
      voiceId: json['voice_id'] as String? ?? '',
      contentHash: json['content_hash'] as String? ?? '',
      fileHash: json['file_hash'] as String? ?? '',
      durationMs: json['duration_ms'] as int? ?? 0,
      downloadUrl: url,
    );
  }
}
