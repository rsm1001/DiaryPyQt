import 'dart:developer' as developer;

import 'package:flutter/material.dart';

import '../backup/local_backup.dart';
import '../backup/local_store_backup.dart';
import '../localization/app_strings.dart';

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

  Future<void> _checkLocalIntegrity() async {
    final strings = AppStrings.of(context);
    if (_busy) return;
    setState(() => _busy = true);
    try {
      final healthy = await widget.store.checkLocalIntegrity();
      final pending = (await widget.store.getOutbox()).length;
      final conflicts = (await widget.store.getConflicts()).length;
      if (mounted) {
        setState(() => _message = healthy
            ? strings.integrityPassed(pending, conflicts)
            : strings.integrityUnhealthy);
      }
    } catch (error, stack) {
      developer.log(
        'local_integrity_check_failed request_id=${DateTime.now().microsecondsSinceEpoch}',
        name: 'diary.backup',
        error: error,
        stackTrace: stack,
      );
      if (mounted) setState(() => _message = strings.integrityCheckFailed);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _backupLocal() async {
    final strings = AppStrings.of(context);
    if (_busy) return;
    setState(() => _busy = true);
    try {
      final backup = await widget.store.exportLocalBackup();
      final saved = await widget.documents.saveBackup(backup.encode());
      if (mounted && saved) {
        final data = backup.payload['data'] as Map<String, dynamic>;
        setState(() => _message =
            strings.backupExported((data['diaries'] as List).length));
      }
    } catch (error, stack) {
      developer.log(
        'local_backup_export_failed request_id=${DateTime.now().microsecondsSinceEpoch}',
        name: 'diary.backup',
        error: error.runtimeType,
        stackTrace: stack,
      );
      if (mounted) setState(() => _message = strings.backupExportFailed);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _restoreLocalBackup() async {
    final strings = AppStrings.of(context);
    if (_busy) return;
    setState(() => _busy = true);
    var restored = false;
    try {
      final source = await widget.documents.pickBackup();
      if (source == null || !mounted) return;
      final backup = LocalBackup.parse(source);
      final data = backup.payload['data'] as Map<String, dynamic>;
      final pending = await widget.store.hasPendingLocalChanges();
      if (!mounted) return;
      final confirmed = await showDialog<bool>(
        context: context,
        builder: (dialogContext) => AlertDialog(
          title: Text(strings.confirmRestoreBackup),
          content: Text(strings.restorePreview(
            (data['diaries'] as List).length,
            (data['outbox'] as List).length,
            (data['conflicts'] as List).length,
            (data['playback_records'] as List).length,
            pending,
          )),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialogContext, false),
              child: Text(strings.cancel),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(dialogContext, true),
              child: Text(strings.confirmRestore),
            ),
          ],
        ),
      );
      if (confirmed != true || !mounted) return;
      final counts = await widget.store.restoreLocalBackup(backup);
      restored = true;
      await widget.onImported();
      if (mounted) {
        setState(() => _message = strings.restoreCompleted(
            counts['diaries'] ?? 0,
            counts['outbox'] ?? 0,
            counts['conflicts'] ?? 0));
      }
    } catch (error, stack) {
      developer.log(
        'local_backup_restore_failed request_id=${DateTime.now().microsecondsSinceEpoch}',
        name: 'diary.backup',
        error: error.runtimeType,
        stackTrace: stack,
      );
      if (mounted) {
        setState(() => _message =
            restored ? strings.restoreRefreshFailed : strings.restoreFailed);
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _export({bool csv = false}) async {
    final strings = AppStrings.of(context);
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
      if (mounted) setState(() => _message = strings.exportFailed);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _import({bool csv = false}) async {
    final strings = AppStrings.of(context);
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
          title: Text(strings.confirmImport),
          content: Text(strings.importPreview(
            preview.entries.length,
            preview.skipped,
            preview.errors,
          )),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialogContext, false),
              child: Text(strings.cancel),
            ),
            FilledButton(
              onPressed: preview.errors > 0 || preview.entries.isEmpty
                  ? null
                  : () => Navigator.pop(dialogContext, true),
              child: Text(strings.import),
            ),
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
      if (mounted) setState(() => _message = strings.importFailed);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final strings = AppStrings.of(context);
    return Scaffold(
      appBar: AppBar(title: Text(strings.transferTitle)),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        if (_busy) const LinearProgressIndicator(),
        ListTile(
          leading: const Icon(Icons.verified_outlined),
          title: Text(strings.checkIntegrity),
          subtitle: Text(strings.integrityNote),
          onTap: _busy ? null : _checkLocalIntegrity,
        ),
        ListTile(
          leading: const Icon(Icons.archive_outlined),
          title: Text(strings.exportBackup),
          subtitle: Text(strings.exportBackupNote),
          onTap: _busy ? null : _backupLocal,
        ),
        ListTile(
          leading: const Icon(Icons.unarchive_outlined),
          title: Text(strings.restoreBackup),
          subtitle: Text(strings.restoreBackupNote),
          onTap: _busy ? null : _restoreLocalBackup,
        ),
        ListTile(
          leading: const Icon(Icons.upload_file),
          title: Text(strings.exportJson),
          subtitle: Text(strings.exportJsonNote),
          onTap: _busy ? null : () => _export(),
        ),
        ListTile(
          leading: const Icon(Icons.download),
          title: Text(strings.importJson),
          subtitle: Text(strings.importJsonNote),
          onTap: _busy ? null : () => _import(),
        ),
        ListTile(
          leading: const Icon(Icons.table_view),
          title: Text(strings.exportCsv),
          subtitle: Text(strings.exportCsvNote),
          onTap: _busy ? null : () => _export(csv: true),
        ),
        ListTile(
          leading: const Icon(Icons.file_open),
          title: Text(strings.importCsv),
          subtitle: Text(strings.importCsvNote),
          onTap: _busy ? null : () => _import(csv: true),
        ),
        Padding(
          padding: const EdgeInsets.all(12),
          child: Text(strings.transferNote),
        ),
        if (_message != null)
          Padding(
            padding: const EdgeInsets.all(12),
            child: Text(_message!),
          ),
      ]),
    );
  }
}
