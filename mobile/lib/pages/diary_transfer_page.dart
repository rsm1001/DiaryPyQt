import 'dart:developer' as developer;

import 'package:flutter/material.dart';

import '../platform/diary_document_adapter.dart';
import '../transfer/diary_csv.dart';
import '../transfer/diary_transfer.dart';
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

  Future<void> _export({bool csv = false}) async {
    if (_busy) return;
    setState(() => _busy = true);
    try {
      final diaries = await widget.store.getDiaries();
      final saved = csv
          ? await widget.documents.saveCsv(exportDiariesCsv(diaries))
          : await widget.documents.saveJson(exportDiariesJson(diaries));
      if (mounted && saved) {
        setState(() => _message = '已导出 ${diaries.length} 篇日记');
      }
    } catch (error, stack) {
      developer.log(
          'diary_export_failed request_id=${DateTime.now().microsecondsSinceEpoch}',
          name: 'diary.transfer',
          error: error,
          stackTrace: stack);
      if (mounted) setState(() => _message = '导出失败，请检查文件权限');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _import({bool csv = false}) async {
    if (_busy) return;
    setState(() => _busy = true);
    try {
      final source = csv
          ? await widget.documents.pickCsv()
          : await widget.documents.pickJson();
      if (source == null || !mounted) return;
      final parsedCsv = csv ? parseDiariesCsv(source) : null;
      final parsed = parsedCsv?.entries ?? parseDiaryImport(source);
      final preview = previewDiaryImport(
        parsed,
        await widget.store.getDiaries(),
        errors: parsedCsv?.errors ?? 0,
      );
      if (!mounted) return;
      final confirmed = await showDialog<bool>(
        context: context,
        builder: (dialogContext) => AlertDialog(
          title: const Text('确认导入'),
          content: Text(
            '可新建 ${preview.entries.length} 篇，跳过 ${preview.skipped} 篇重复，错误 ${preview.errors} 篇。\n'
            '仅导入日期、正文和标签；历史查看次数不会被重复导入。'
            '${preview.errors > 0 ? '\n请修复错误行后重新导入，整批数据尚未写入。' : ''}',
          ),
          actions: [
            TextButton(
                onPressed: () => Navigator.pop(dialogContext, false),
                child: const Text('取消')),
            FilledButton(
                onPressed: preview.errors > 0 || preview.entries.isEmpty
                    ? null
                    : () => Navigator.pop(dialogContext, true),
                child: const Text('导入')),
          ],
        ),
      );
      if (confirmed != true || !mounted) return;
      final count = await widget.sync.importDiaries(preview.entries);
      await widget.onImported();
      if (mounted) {
        setState(() => _message = '已导入 $count 篇，其余已跳过');
      }
    } catch (error, stack) {
      developer.log(
          'diary_import_failed request_id=${DateTime.now().microsecondsSinceEpoch}',
          name: 'diary.transfer',
          error: error,
          stackTrace: stack);
      if (mounted) setState(() => _message = '导入失败：请检查文件格式和大小');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('日记导入导出')),
        body: ListView(padding: const EdgeInsets.all(16), children: [
          if (_busy) const LinearProgressIndicator(),
          ListTile(
            leading: const Icon(Icons.upload_file),
            title: const Text('导出 JSON 备份'),
            subtitle: const Text('导出当前缓存的日记，包含查看次数'),
            onTap: _busy ? null : () => _export(),
          ),
          ListTile(
            leading: const Icon(Icons.download),
            title: const Text('从 JSON 导入'),
            subtitle: const Text('新建不重复的日记，支持断网待同步'),
            onTap: _busy ? null : () => _import(),
          ),
          ListTile(
            leading: const Icon(Icons.table_view),
            title: const Text('导出 CSV'),
            subtitle: const Text('导出本地日记，与电脑端 CSV 字段兼容'),
            onTap: _busy ? null : () => _export(csv: true),
          ),
          ListTile(
            leading: const Icon(Icons.file_open),
            title: const Text('从 CSV 导入'),
            subtitle: const Text('先预览再导入；有错误行时整批拒绝'),
            onTap: _busy ? null : () => _import(csv: true),
          ),
          const Padding(
            padding: EdgeInsets.all(12),
            child: Text('导入不覆盖已有日记，不导入旧 ID 或历史查看统计。CSV 不是数据库备份。'),
          ),
          if (_message != null)
            Padding(
              padding: const EdgeInsets.all(12),
              child: Text(_message!),
            ),
        ]),
      );
}
