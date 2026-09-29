class AppConfig {
  static const apiBaseUrl = String.fromEnvironment(
    'DIARY_API_BASE_URL',
    defaultValue: 'https://203.195.195.218',
  );

  static const legacyApiBaseUrls = [
    'http://100.125.111.63:8020',
    'http://203.195.195.218',
  ];

  static bool isValidServerUrl(String value) {
    final parsed = Uri.tryParse(value);
    if (parsed == null ||
        !parsed.hasAuthority ||
        parsed.host.isEmpty ||
        parsed.userInfo.isNotEmpty ||
        parsed.path.isNotEmpty ||
        parsed.hasQuery ||
        parsed.hasFragment) {
      return false;
    }
    if (parsed.scheme == 'https') return true;
    if (parsed.scheme != 'http') return false;
    if (parsed.host == '10.0.2.2' || parsed.host == '127.0.0.1') {
      return true;
    }
    return legacyApiBaseUrls.any((url) {
      final oldHost = Uri.parse(url).host;
      return oldHost.startsWith('100.') && oldHost == parsed.host;
    });
  }

  static bool shouldMigrateLegacyUrl(String? url) =>
      url != null && legacyApiBaseUrls.contains(url);

  static String get normalizedApiBaseUrl {
    if (apiBaseUrl.endsWith('/')) {
      return apiBaseUrl.substring(0, apiBaseUrl.length - 1);
    }
    return apiBaseUrl;
  }
}
