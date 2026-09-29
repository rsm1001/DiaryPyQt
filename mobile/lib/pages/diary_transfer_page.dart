import 'dart:developer' as developer;

import 'package:flutter/material.dart';

import '../platform/diary_document_adapter.dart';
import '../services/diary_transfer.dart';
import '../services/local_store.dart';
import '../services/sync_manager.dart';

class DiaryTransferPage extends StatefulWidget {
  const DiaryTransferPage({
    super.key,
    required this.store,
    required this.sync,
    required this.onImported,
    this.documents = const DiaryDocumentAdapter(),
  });

  final LocalStore store;
  final SyncManager sync;
  final Future<void> Function() onImported;
  final DiaryDocumentAdapter documents;

  @override
  State<DiaryTransferPage> createState() => _DiaryTransferPageState();
}

class _DiaryTransferPageState extends State<DiaryTransferPage> {
  bool _busy = false;
  String? _message;

  Future<void> _export() async {
    if (_busy) return;
    setState(() => _busy = true);
    try {
      final diaries = await widget.store.getDiaries();
      final saved = await widget.documents.saveJson(exportDiariesJson(diaries));
      if (mounted && saved) {
        setState(() => _message =
            '\u5df2\u5bfc\u51fa ${diaries.length} \u7bc7\u65e5\u8bb0');
      }
    } catch (error, stack) {
      developer.log(
          'diary_export_failed request_id=${DateTime.now().microsecondsSinceEpoch}',
          name: 'diary.transfer',
          error: error,
          stackTrace: stack);
      if (mounted) {
        setState(() => _message =
            '\u5bfc\u51fa\u5931\u8d25\uff0c\u8bf7\u68c0\u67e5\u6587\u4ef6\u6743\u9650');
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _import() async {
    if (_busy) return;
    setState(() => _busy = true);
    try {
      final source = await widget.documents.pickJson();
      if (source == null || !mounted) return;
      final parsed = parseDiaryImport(source);
      final preview =
          previewDiaryImport(parsed, await widget.store.getDiaries());
      if (!mounted) return;
      final confirmed = await showDialog<bool>(
        context: context,
        builder: (dialogContext) => AlertDialog(
          title: const Text('\u786e\u8ba4\u5bfc\u5165'),
          content: Text(
            '\u53ef\u65b0\u5efa ${preview.entries.length} \u7bc7\uff0c\u8df3\u8fc7 ${preview.skipped} \u7bc7\u91cd\u590d\u3002\n'
            '\u4ec5\u5bfc\u5165\u65e5\u671f\u3001\u6b63\u6587\u548c\u6807\u7b7e\uff1b\u5386\u53f2\u67e5\u770b\u6b21\u6570\u4e0d\u4f1a\u88ab\u91cd\u590d\u5bfc\u5165\u3002',
          ),
          actions: [
            TextButton(
                onPressed: () => Navigator.pop(dialogContext, false),
                child: const Text('\u53d6\u6d88')),
            FilledButton(
                onPressed: () => Navigator.pop(dialogContext, true),
                child: const Text('\u5bfc\u5165')),
          ],
        ),
      );
      if (confirmed != true || !mounted) return;
      final count = await widget.sync.importDiaries(preview.entries);
      await widget.onImported();
      if (mounted) {
        setState(() => _message =
            '\u5df2\u5bfc\u5165 $count \u7bc7\uff0c\u5176\u4f59\u5df2\u8df3\u8fc7');
      }
    } catch (error, stack) {
      developer.log(
          'diary_import_failed request_id=${DateTime.now().microsecondsSinceEpoch}',
          name: 'diary.transfer',
          error: error,
          stackTrace: stack);
      if (mounted) {
        setState(() => _message =
            '\u5bfc\u5165\u5931\u8d25\uff1a\u4ec5\u63a5\u53d7\u6709\u6548\u7684 JSON \u65e5\u8bb0\u6587\u4ef6');
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar:
            AppBar(title: const Text('\u65e5\u8bb0\u5bfc\u5165\u5bfc\u51fa')),
        body: ListView(padding: const EdgeInsets.all(16), children: [
          if (_busy) const LinearProgressIndicator(),
          ListTile(
            leading: const Icon(Icons.upload_file),
            title: const Text('\u5bfc\u51fa JSON \u5907\u4efd'),
            subtitle: const Text(
                '\u5bfc\u51fa\u5f53\u524d\u7f13\u5b58\u7684\u65e5\u8bb0\uff0c\u5305\u542b\u67e5\u770b\u6b21\u6570'),
            onTap: _busy ? null : _export,
          ),
          ListTile(
            leading: const Icon(Icons.download),
            title: const Text('\u4ece JSON \u5bfc\u5165'),
            subtitle: const Text(
                '\u65b0\u5efa\u4e0d\u91cd\u590d\u7684\u65e5\u8bb0\uff0c\u652f\u6301\u65ad\u7f51\u5f85\u540c\u6b65'),
            onTap: _busy ? null : _import,
          ),
          const Padding(
            padding: EdgeInsets.all(12),
            child: Text(
                '\u5bfc\u5165\u4e0d\u8986\u76d6\u5df2\u6709\u65e5\u8bb0\uff0c\u4e0d\u5bfc\u5165\u65e7 ID \u6216\u5386\u53f2\u67e5\u770b\u7edf\u8ba1\u3002'),
          ),
          if (_message != null)
            Padding(
              padding: const EdgeInsets.all(12),
              child: Text(_message!),
            ),
        ]),
      );
}
