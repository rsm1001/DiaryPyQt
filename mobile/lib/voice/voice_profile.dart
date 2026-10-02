class VoiceProfile {
  const VoiceProfile({
    required this.id,
    required this.name,
    required this.language,
    required this.offlineSupported,
  });

  final String id;
  final String name;
  final String language;
  final bool offlineSupported;

  factory VoiceProfile.fromJson(Map<String, dynamic> json) => VoiceProfile(
        id: json['id'] as String,
        name: json['name'] as String,
        language: json['language'] as String? ?? '',
        offlineSupported: json['offline_supported'] as bool? ?? false,
      );
}
