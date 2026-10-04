import 'package:diary_mobile/config/app_config.dart';
import 'package:diary_mobile/pages/server_connection_dialog.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('仅接受 HTTPS 或配置中的私有 HTTP 入口', () {
    expect(AppConfig.isValidServerUrl('https://example.invalid'), isTrue);
    expect(
        AppConfig.isValidServerUrl(AppConfig.legacyApiBaseUrls.first), isTrue);
    expect(
        AppConfig.isValidServerUrl(AppConfig.legacyApiBaseUrls.last), isFalse);
    expect(AppConfig.isValidServerUrl('http://example.invalid'), isFalse);
    expect(AppConfig.isValidServerUrl('https://example.invalid/path'), isFalse);
    expect(AppConfig.isValidServerUrl('https://user@example.invalid'), isFalse);
    expect(AppConfig.isValidServerUrl('https://'), isFalse);
  });

  testWidgets('连接对话框在校验通过后才返回地址和新密码', (tester) async {
    ServerConnectionInput? selected;
    await tester.pumpWidget(MaterialApp(
      locale: const Locale('zh', 'CN'),
      supportedLocales: const [Locale('zh', 'CN'), Locale('en', 'US')],
      localizationsDelegates: GlobalMaterialLocalizations.delegates,
      home: Builder(
        builder: (context) => Scaffold(
          body: TextButton(
            onPressed: () async {
              selected = await showServerConnectionDialog(
                  context, AppConfig.normalizedApiBaseUrl);
            },
            child: const Text('设置'),
          ),
        ),
      ),
    ));
    await tester.tap(find.text('设置'));
    await tester.pumpAndSettle();
    await tester.enterText(
        find.byType(TextField).first, 'http://example.invalid');
    await tester.tap(find.text('测试并保存'));
    await tester.pumpAndSettle();
    expect(find.textContaining('HTTPS 地址'), findsOneWidget);
    expect(selected, isNull);
    await tester.enterText(
        find.byType(TextField).first, 'https://example.invalid');
    await tester.enterText(find.byType(TextField).last, 'test-only-password');
    await tester.tap(find.text('测试并保存'));
    await tester.pumpAndSettle();
    expect(selected?.url, 'https://example.invalid');
    expect(selected?.password, 'test-only-password');
  });
}
