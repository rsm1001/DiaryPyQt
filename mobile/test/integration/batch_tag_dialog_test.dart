import 'package:diary_mobile/pages/batch_tag_dialog.dart';
import 'package:diary_mobile/tags/batch_tag_policy.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('batch tag dialog requires a tag before add', (tester) async {
    BatchTagSelection? selection;
    await tester.pumpWidget(MaterialApp(
      locale: const Locale('zh', 'CN'),
      supportedLocales: const [Locale('zh', 'CN'), Locale('en', 'US')],
      localizationsDelegates: GlobalMaterialLocalizations.delegates,
      home: Scaffold(
        body: TextButton(
          onPressed: () async {
            selection = await showBatchTagDialog(
              tester.element(find.byType(Scaffold)),
              diaryCount: 2,
              availableTags: ['work'],
            );
          },
          child: const Text('open'),
        ),
      ),
    ));
    await tester.tap(find.text('open'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('\u5e94\u7528'));
    await tester.pumpAndSettle();
    expect(selection, isNull);
    expect(find.text('\u8bf7\u9009\u62e9\u6216\u8f93\u5165\u6807\u7b7e'),
        findsOneWidget);
    await tester.tap(find.text('work'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('\u5e94\u7528'));
    await tester.pumpAndSettle();
    expect(selection!.mode, BatchTagMode.add);
    expect(selection!.tags, ['work']);
  });
}
