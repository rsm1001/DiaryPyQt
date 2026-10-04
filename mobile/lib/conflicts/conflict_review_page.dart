import 'dart:developer' as developer;

import 'package:flutter/material.dart';

import '../localization/app_strings.dart';
import '../services/sync_manager.dart';
import 'diary_conflict.dart';

class ConflictReviewPage extends StatefulWidget {
  const ConflictReviewPage({
    super.key,
    required this.sync,
    required this.onResolved,
  });

  final SyncManager sync;
  final Future<void> Function() onResolved;

  @override
  State<ConflictReviewPage> createState() => _ConflictReviewPageState();
}

class _ConflictReviewPageState extends State<ConflictReviewPage> {
  late Future<List<DiaryConflict>> _conflicts;
  String? _message;
  String? _busyId;

  @override
  void initState() {
    super.initState();
    _conflicts = widget.sync.getConflicts();
  }

  void _reload() {
    final conflicts = widget.sync.getConflicts();
    setState(() {
      _conflicts = conflicts;
    });
  }

  Future<void> _refresh(DiaryConflict conflict) async {
    if (_busyId != null) return;
    setState(() => _busyId = conflict.diaryId);
    try {
      await widget.sync.refreshConflict(conflict);
      if (mounted) {
        setState(() => _message = AppStrings.of(context).serverVersionUpdated);
      }
    } catch (error, stack) {
      developer.log(
        'conflict_refresh_failed request_id=${DateTime.now().microsecondsSinceEpoch}',
        name: 'diary.conflict',
        error: error,
        stackTrace: stack,
      );
      if (mounted) {
        setState(
            () => _message = AppStrings.of(context).serverVersionUnavailable);
      }
    } finally {
      if (mounted) {
        setState(() => _busyId = null);
        _reload();
      }
    }
  }

  Future<void> _resolve(DiaryConflict conflict, bool keepLocal) async {
    if (_busyId != null || conflict.remote == null) return;
    final strings = AppStrings.of(context);
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title:
            Text(keepLocal ? strings.keepLocalTitle : strings.useServerTitle),
        content: Text(
            keepLocal ? strings.keepLocalMessage : strings.useServerMessage),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: Text(strings.cancel),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(dialogContext, true),
            child: Text(strings.confirm),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    setState(() => _busyId = conflict.diaryId);
    try {
      await widget.sync.resolveConflict(conflict, keepLocal: keepLocal);
      if (mounted) setState(() => _message = strings.conflictHandled);
      try {
        await widget.onResolved();
      } catch (error, stack) {
        developer.log(
          'conflict_refresh_after_resolve_failed request_id=${DateTime.now().microsecondsSinceEpoch}',
          name: 'diary.conflict',
          error: error,
          stackTrace: stack,
        );
        if (mounted) setState(() => _message = strings.conflictRefreshFailed);
      }
    } catch (error, stack) {
      developer.log(
        'conflict_resolve_failed request_id=${DateTime.now().microsecondsSinceEpoch}',
        name: 'diary.conflict',
        error: error,
        stackTrace: stack,
      );
      if (mounted) setState(() => _message = strings.conflictHandleFailed);
    } finally {
      if (mounted) {
        setState(() => _busyId = null);
        _reload();
      }
    }
  }

  String _summary(String content) =>
      content.length > 160 ? '${content.substring(0, 160)}?' : content;

  Widget _details(DiaryConflict conflict, bool local, AppStrings strings) {
    final diary = local ? conflict.local : conflict.remote;
    if (diary == null) return Text(strings.serverUnavailableBeforeReview);
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(
        strings.versionLabel(
            local
                ? (strings.english ? 'Local' : '本地')
                : (strings.english ? 'Server' : '服务器'),
            diary.version),
        style: const TextStyle(fontWeight: FontWeight.bold),
      ),
      Text(strings.updatedLabel(
          diary.updatedAt.isEmpty ? strings.unknown : diary.updatedAt)),
      Text(strings
          .tagsLabel(diary.tags.isEmpty ? strings.none : diary.tags.join('?'))),
      Text(strings.summaryLabel(_summary(diary.content))),
      if (diary.deletedAt != null) Text(strings.deletedOrRestoring),
    ]);
  }

  @override
  Widget build(BuildContext context) {
    final strings = AppStrings.of(context);
    return Scaffold(
      appBar: AppBar(
        title: Text(strings.conflictReview),
        actions: [
          IconButton(
            tooltip: strings.refreshConflicts,
            onPressed: _reload,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: FutureBuilder<List<DiaryConflict>>(
        future: _conflicts,
        builder: (context, snapshot) {
          if (!snapshot.hasData &&
              snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError) {
            return Center(child: Text(strings.conflictLoadFailed));
          }
          final conflicts = snapshot.data ?? const <DiaryConflict>[];
          return ListView(padding: const EdgeInsets.all(16), children: [
            if (_message != null)
              Padding(padding: const EdgeInsets.all(8), child: Text(_message!)),
            if (conflicts.isEmpty) ...[
              Text(strings.noConflicts),
            ] else
              for (final conflict in conflicts)
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(12),
                    child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            strings.conflictTitle(
                              conflict.local.date,
                              conflict.action == 'restore'
                                  ? strings.restoreAction
                                  : conflict.action == 'delete'
                                      ? strings.deleteAction
                                      : strings.editAction,
                            ),
                            style: Theme.of(context).textTheme.titleMedium,
                          ),
                          const SizedBox(height: 8),
                          _details(conflict, true, strings),
                          const Divider(height: 24),
                          _details(conflict, false, strings),
                          if (conflict.remote?.deletedAt != null &&
                              conflict.action != 'restore')
                            Text(strings.serverDeletedWarning),
                          if (conflict.remote?.deletedAt == null &&
                              conflict.action == 'restore')
                            Text(strings.serverRestoredWarning),
                          const SizedBox(height: 8),
                          Wrap(spacing: 8, runSpacing: 8, children: [
                            OutlinedButton(
                              onPressed: _busyId == null
                                  ? () => _refresh(conflict)
                                  : null,
                              child: Text(strings.refreshServerVersion),
                            ),
                            OutlinedButton(
                              onPressed: _busyId == null
                                  ? () => setState(
                                      () => _message = strings.conflictDeferred)
                                  : null,
                              child: Text(strings.deferConflict),
                            ),
                            FilledButton(
                              onPressed: _busyId == null &&
                                      conflict.remote != null &&
                                      (conflict.action == 'restore'
                                          ? conflict.remote!.deletedAt != null
                                          : conflict.remote!.deletedAt == null)
                                  ? () => _resolve(conflict, true)
                                  : null,
                              child: Text(strings.keepLocal),
                            ),
                            FilledButton(
                              onPressed:
                                  _busyId == null && conflict.remote != null
                                      ? () => _resolve(conflict, false)
                                      : null,
                              child: Text(strings.useServer),
                            ),
                          ]),
                        ]),
                  ),
                ),
          ]);
        },
      ),
    );
  }
}
