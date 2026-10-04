import 'package:diary_mobile/statistics/monthly_diary_heatmap.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('English heatmap keeps server and device views distinct',
      (tester) async {
    await tester.pumpWidget(MaterialApp(
      locale: const Locale('en', 'US'),
      supportedLocales: const [Locale('zh', 'CN'), Locale('en', 'US')],
      localizationsDelegates: GlobalMaterialLocalizations.delegates,
      home: Scaffold(
        body: SingleChildScrollView(
          child: MonthlyDiaryHeatmap(
            month: DateTime(2026, 10),
            deviceViews: const {'2026-10-01': 1},
            serverViews: const {'2026-10-01': 2},
            cachedDiaries: const {'2026-10-01': 1},
          ),
        ),
      ),
    ));
    expect(find.text('Mon'), findsOneWidget);
    expect(find.textContaining('Color shows server history'), findsOneWidget);
    expect(
      find.byTooltip(
          '2026-10-01: 2 server views, 1 new device views, 1 cached diaries'),
      findsOneWidget,
    );
  });
}
