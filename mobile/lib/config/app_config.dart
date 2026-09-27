class AppConfig {
  static const apiBaseUrl = String.fromEnvironment(
    'DIARY_API_BASE_URL',
    defaultValue: 'https://203.195.195.218',
  );

  static const legacyApiBaseUrls = [
    'http://100.125.111.63:8020',
    'http://203.195.195.218',
  ];

  static bool shouldMigrateLegacyUrl(String? url) =>
      url != null && legacyApiBaseUrls.contains(url);

  static String get normalizedApiBaseUrl {
    if (apiBaseUrl.endsWith('/')) {
      return apiBaseUrl.substring(0, apiBaseUrl.length - 1);
    }
    return apiBaseUrl;
  }
}
