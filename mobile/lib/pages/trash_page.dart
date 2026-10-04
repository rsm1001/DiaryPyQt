import 'dart:async';
import 'dart:developer' as developer;
import 'dart:io';

import 'package:flutter/material.dart';

import '../localization/app_strings.dart';
import '../models/diary.dart';
import '../services/diary_api.dart';
import '../services/sync_manager.dart';
import '../trash/trash_batch.dart';

class TrashPage extends StatefulWidget {
  const TrashPage({
    super.key,
    required this.api,
    required this.sync,
    this.onChanged,
  });

  final DiaryApi api;
  final SyncManager sync;
  final Future<void> Function()? onChanged;

  @override
  State<TrashPage> createState() => _TrashPageState();
}

class _TrashPageState extends State<TrashPage> {
  final _selected = <String>{};
  List<Diary> _items = const [];
  String _query = '';
  String? _error;
  TrashBatchResult? _result;
  bool _loading = true;
  bool _busy = false;
  bool _selecting = false;

  @override
  void initState() {
    super.initState();
    unawaited(_load());
  }

  Future<void> _load({bool clearError = true}) async {
    if (_busy) return;
    setState(() => _loading = true);
    try {
      final items = await widget.api.fetchTrash();
      if (!mounted) return;
      setState(() {
        _items = items;
        _selected.retainAll(items.map((diary) => diary.id));
        if (clearError) _error = null;
      });
    } catch (error, stack) {
      developer.log(
        'trash_load_failed request_id=${DateTime.now().microsecondsSinceEpoch}',
        name: 'diary.trash',
        error: error,
        stackTrace: stack,
      );
      if (mounted) {
        setState(() => _error = AppStrings.of(context).trashReadError);
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _toggle(String id) {
    if (_busy) return;
    setState(() {
      _selecting = true;
      if (!_selected.add(id)) _selected.remove(id);
      if (_selected.isEmpty) _selecting = false;
    });
  }

  void _selectVisible() {
    if (_busy) return;
    setState(() {
      _selected.addAll(filterTrash(_items, _query).map((diary) => diary.id));
      _selecting = _selected.isNotEmpty;
    });
  }

  void _cancelSelection() => setState(() {
        _selected.clear();
        _selecting = false;
      });

  Future<bool> _confirm(String title, String message) async {
    final strings = AppStrings.of(context);
    return await showDialog<bool>(
          context: context,
          builder: (dialogContext) => AlertDialog(
            title: Text(title),
            content: Text(message),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(dialogContext, false),
                child: Text(strings.cancel),
              ),
              FilledButton(
                onPressed: () => Navigator.pop(dialogContext, true),
                child: Text(strings.confirmContinue),
              ),
            ],
          ),
        ) ??
        false;
  }

  Future<bool> _confirmClear() async {
    final strings = AppStrings.of(context);
    if (!await _confirm(
        strings.clearTrashTitle, strings.clearTrashConfirm(_items.length))) {
      return false;
    }
    if (!mounted) return false;
    var typed = false;
    return await showDialog<bool>(
          context: context,
          builder: (dialogContext) => StatefulBuilder(
            builder: (context, refresh) => AlertDialog(
              title: Text(strings.confirmAgain),
              content: TextField(
                decoration:
                    InputDecoration(labelText: strings.typeClearToConfirm),
                onChanged: (value) => refresh(() => typed = value.trim() ==
                    (strings.english ? 'EMPTY' : '\u6e05\u7a7a')),
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(dialogContext, false),
                  child: Text(strings.cancel),
                ),
                FilledButton(
                  onPressed:
                      typed ? () => Navigator.pop(dialogContext, true) : null,
                  child: Text(strings.permanentlyEmpty),
                ),
              ],
            ),
          ),
        ) ??
        false;
  }

  Future<TrashOutcome> _restore(Diary diary) async {
    final strings = AppStrings.of(context);
    await widget.sync.restoreDiary(diary);
    final conflicts = await widget.sync.getConflicts();
    if (conflicts.any((item) => item.diaryId == diary.id)) {
      throw StateError(strings.restoreConflict);
    }
    final pending = await widget.sync.store.getOutbox();
    if (pending.any(
        (row) => row['entity_id'] == diary.id && row['action'] == 'restore')) {
      return TrashOutcome.deferred;
    }
    return TrashOutcome.completed;
  }

  Future<void> _run(
    List<Diary> diaries, {
    required bool purge,
    bool clearAll = false,
  }) async {
    if (_busy || _loading || diaries.isEmpty) return;
    final strings = AppStrings.of(context);
    if (purge &&
        !await (clearAll
            ? _confirmClear()
            : _confirm(strings.confirmPurgeTitle,
                strings.purgeConfirm(diaries.length)))) {
      return;
    }
    if (!mounted) return;
    setState(() {
      _busy = true;
      _error = null;
      _result = null;
    });
    final result = await const TrashBatchService().run(
      diaries,
      (diary) async {
        if (!purge) return _restore(diary);
        await widget.api.permanentlyDeleteDiary(diary);
        return TrashOutcome.completed;
      },
      onFailure: (diary, error) => developer.log(
        'trash_item_failed request_id=${DateTime.now().microsecondsSinceEpoch} diary_id=${diary.id}',
        name: 'diary.trash',
        error: error,
      ),
      isInterrupted: (error) =>
          error is SocketException ||
          error is TimeoutException ||
          error is DiaryApiException && error.network,
      isUnsupported: purge
          ? (error) =>
              error is DiaryApiException &&
              (error.statusCode == 404 || error.statusCode == 405)
          : null,
    );
    if (!mounted) return;
    setState(() {
      _result = result;
      _items = _items
          .where((diary) => !result.completedIds.contains(diary.id))
          .toList(growable: false);
      _selected.removeAll(result.completedIds);
      if (_selected.isEmpty) _selecting = false;
      _busy = false;
      if (result.unsupportedVersionedDelete) {
        _error = strings.unsupportedDelete;
      } else if (result.unprocessed > 0) {
        _error = strings.interruptedTrash;
      }
    });
    if (result.completed > 0 && !purge) {
      try {
        await widget.onChanged?.call();
      } catch (error, stack) {
        developer.log(
          'trash_refresh_failed request_id=${DateTime.now().microsecondsSinceEpoch}',
          name: 'diary.trash',
          error: error,
          stackTrace: stack,
        );
      }
    }
    developer.log(
      'trash_batch_finished request_id=${DateTime.now().microsecondsSinceEpoch} '
      'completed=${result.completed} failed=${result.failed} '
      'unprocessed=${result.unprocessed}',
      name: 'diary.trash',
    );
    if (mounted) await _load(clearError: false);
  }

  @override
  Widget build(BuildContext context) {
    final strings = AppStrings.of(context);
    final visible = filterTrash(_items, _query);
    final selected = _items
        .where((diary) => _selected.contains(diary.id))
        .toList(growable: false);
    return Scaffold(
      appBar: AppBar(
        title: Text(_selecting
            ? strings.selectedTrashCount(_selected.length)
            : strings.trashTitle),
        leading: _selecting
            ? IconButton(
                tooltip: strings.cancel,
                onPressed: _busy ? null : _cancelSelection,
                icon: const Icon(Icons.close),
              )
            : null,
        actions: [
          if (_selecting)
            IconButton(
              tooltip: strings.selectCurrentResults,
              onPressed: _busy ? null : _selectVisible,
              icon: const Icon(Icons.select_all),
            ),
          IconButton(
            tooltip: strings.refreshTrash,
            onPressed: _busy ? null : _load,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: Column(children: [
        if (_loading || _busy) const LinearProgressIndicator(),
        Padding(
          padding: const EdgeInsets.fromLTRB(12, 6, 12, 3),
          child: TextField(
            onChanged: (value) => setState(() => _query = value),
            decoration: InputDecoration(
              prefixIcon: const Icon(Icons.search),
              hintText: strings.trashSearchHint,
            ),
          ),
        ),
        if (_error != null)
          MaterialBanner(content: Text(_error!), actions: [
            TextButton(
              onPressed: _busy ? null : _load,
              child: Text(strings.retryTrash),
            ),
          ]),
        if (_result != null)
          Padding(
            padding: const EdgeInsets.all(8),
            child: Text(strings.batchResult(
                _result!.completed, _result!.failed, _result!.unprocessed)),
          ),
        if (_items.isNotEmpty)
          Row(children: [
            TextButton.icon(
              onPressed: _busy ? null : _selectVisible,
              icon: const Icon(Icons.select_all),
              label: Text(strings.selectResults),
            ),
            const Spacer(),
            TextButton(
              onPressed: _busy
                  ? null
                  : () => _run(_items, purge: true, clearAll: true),
              child: Text(strings.clearTrash),
            ),
          ]),
        if (_selecting)
          Wrap(spacing: 8, children: [
            FilledButton(
              onPressed: _busy || selected.isEmpty
                  ? null
                  : () => _run(selected, purge: false),
              child: Text(strings.batchRestore),
            ),
            OutlinedButton(
              onPressed: _busy || selected.isEmpty
                  ? null
                  : () => _run(selected, purge: true),
              child: Text(strings.batchPurge),
            ),
          ]),
        Expanded(
          child: _loading && _items.isEmpty
              ? const Center(child: CircularProgressIndicator())
              : visible.isEmpty
                  ? Center(
                      child: Text(_items.isEmpty
                          ? strings.emptyTrash
                          : strings.noMatchingTrash))
                  : ListView.builder(
                      itemCount: visible.length,
                      itemBuilder: (context, index) {
                        final diary = visible[index];
                        return Card(
                          child: ListTile(
                            selected: _selected.contains(diary.id),
                            onTap: _selecting ? () => _toggle(diary.id) : null,
                            onLongPress: _busy ? null : () => _toggle(diary.id),
                            leading: _selecting
                                ? Checkbox(
                                    value: _selected.contains(diary.id),
                                    onChanged:
                                        _busy ? null : (_) => _toggle(diary.id),
                                  )
                                : null,
                            title: Text(diary.date),
                            subtitle: Text(diary.content,
                                maxLines: 3, overflow: TextOverflow.ellipsis),
                            trailing: _selecting
                                ? null
                                : PopupMenuButton<String>(
                                    enabled: !_busy,
                                    onSelected: (action) =>
                                        _run([diary], purge: action == 'purge'),
                                    itemBuilder: (_) => [
                                      PopupMenuItem(
                                          value: 'restore',
                                          child: Text(strings.restore)),
                                      PopupMenuItem(
                                          value: 'purge',
                                          child: Text(strings.purge)),
                                    ],
                                  ),
                          ),
                        );
                      },
                    ),
        ),
      ]),
    );
  }
}
