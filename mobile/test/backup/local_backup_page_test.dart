import 'package:diary_mobile/pages/diary_transfer_page.dart';
import 'package:diary_mobile/services/diary_api.dart';
import 'package:diary_mobile/services/local_store.dart';
import 'package:diary_mobile/services/sync_manager.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('本地备份、恢复与完整性校验入口独立于普通导入导出', (tester) async {
    final store = LocalStore();
    final api = DiaryApi(baseUrl: '');
    addTearDown(api.dispose);
    await tester.pumpWidget(MaterialApp(
        home: DiaryTransferPage(
      store: store,
      sync: SyncManager(store: store, api: api),
      onImported: () async {},
    )));
    expect(find.widgetWithText(ListTile, '导出本地完整备份'), findsOneWidget);
    expect(find.widgetWithText(ListTile, '恢复本地完整备份'), findsOneWidget);
    expect(find.text('检查本地数据库完整性'), findsOneWidget);
    expect(find.text('从 JSON 导入'), findsOneWidget);
    expect(find.text('从 CSV 导入'), findsOneWidget);
  });
}
