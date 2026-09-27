import 'package:flutter_test/flutter_test.dart';

import 'package:diary_mobile/config/app_config.dart';

void main() {
  test('API base URL has a usable default', () {
    expect(AppConfig.normalizedApiBaseUrl, isNotEmpty);
  });
}
