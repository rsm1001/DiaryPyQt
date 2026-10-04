import 'package:diary_mobile/models/app_preferences.dart';
import 'package:diary_mobile/settings/app_preferences_navigation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';

Widget _harness({
  required Future<void> Function(AppPreferences) save,
  required ValueChanged<AppPreferences?> onResult,
}) =>
    MaterialApp(
      locale: const Locale('en', 'US'),
      supportedLocales: const [Locale('zh', 'CN'), Locale('en', 'US')],
      localizationsDelegates: GlobalMaterialLocalizations.delegates,
      home: Builder(
        builder: (context) => Scaffold(
          body: TextButton(
            onPressed: () async {
              onResult(await openAppPreferences(
                context,
                initial: AppPreferences.defaults,
                save: save,
              ));
            },
            child: const Text('Open preferences'),
          ),
        ),
      ),
    );

void main() {
  testWidgets('preferences are returned only after saving succeeds',
      (tester) async {
    AppPreferences? result;
    var saved = false;
    await tester.pumpWidget(_harness(
      save: (_) async => saved = true,
      onResult: (value) => result = value,
    ));
    await tester.tap(find.text('Open preferences'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Save'));
    await tester.pumpAndSettle();
    expect(saved, isTrue);
    expect(result?.toJson(), AppPreferences.defaults.toJson());
  });

  testWidgets('failed preference save reports an error without applying it',
      (tester) async {
    AppPreferences? result;
    await tester.pumpWidget(_harness(
      save: (_) async => throw StateError('storage unavailable'),
      onResult: (value) => result = value,
    ));
    await tester.tap(find.text('Open preferences'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Save'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));
    expect(result, isNull);
    expect(find.text('Settings could not be saved. Please try again.'),
        findsOneWidget);
  });
}
