import 'dart:developer' as developer;

import 'package:flutter/material.dart';

import '../localization/app_strings.dart';
import '../models/diary.dart';
import '../services/local_store.dart';
import '../services/sync_manager.dart';
import 'random_deletion_policy.dart';
import 'random_deletion_service.dart';

class RandomDeletionPage extends StatefulWidget {
  const RandomDeletionPage({
    super.key,
    required this.service,
    required this.onChanged,
  });

  static Future<void> open(
    BuildContext context, {
    required LocalStore store,
    required SyncManager sync,
    required Future<void> Function() onChanged,
  }) =>
      Navigator.of(context).push(MaterialPageRoute<void>(
        builder: (_) => RandomDeletionPage(
          service: RandomDeletionService(store: store, sync: sync),
          onChanged: onChanged,
        ),
      ));
  final RandomDeletionService service;
  final Future<void> Function() onChanged;

  @override
  State<RandomDeletionPage> createState() => _RandomDeletionPageState();
}

class _RandomDeletionPageState extends State<RandomDeletionPage> {
  final _minController = TextEditingController();
  final _maxController = TextEditingController();
  final _seenIds = <String>{};
  List<String> _tags = const [];
  DateTime? _before;
  String? _tag;
  DeletionFilters _filters = const DeletionFilters();
  Diary? _candidate;
  String? _message;
  bool _busy = false;
  bool _loading = false;

  @override
  void initState() {
    super.initState();
    _loadTags();
  }

  @override
  void dispose() {
    _minController.dispose();
    _maxController.dispose();
    super.dispose();
  }

  Future<void> _loadTags() async {
    try {
      final entries = await widget.service.candidates();
      if (mounted) {
        setState(() {
          _tags =
              (entries.expand((diary) => diary.tags).toSet().toList()..sort());
        });
      }
    } catch (error, stack) {
      developer.log(
        '随机删除候选读取失败 request_id=${DateTime.now().microsecondsSinceEpoch}',
        name: 'diary.deletion',
        error: error,
        stackTrace: stack,
      );
      if (mounted) {
        setState(() => _message = AppStrings.of(context).localCandidateFailed);
      }
    }
  }

  void _filterChanged() {
    setState(() {
      _candidate = null;
      _seenIds.clear();
      _message = null;
    });
  }

  Future<void> _pickDate() async {
    final selected = await showDatePicker(
      context: context,
      initialDate: _before ?? DateTime.now(),
      firstDate: DateTime(1900),
      lastDate: DateTime.now(),
    );
    if (selected == null || !mounted) return;
    setState(() => _before = selected);
    _filterChanged();
  }

  Future<void> _applyFilters() async {
    final minText = _minController.text.trim();
    final maxText = _maxController.text.trim();
    final min = minText.isEmpty ? null : int.tryParse(minText);
    final max = maxText.isEmpty ? null : int.tryParse(maxText);
    final filters = DeletionFilters(
      before: _before,
      tag: _tag,
      minViews: min,
      maxViews: max,
    );
    if ((minText.isNotEmpty && min == null) ||
        (maxText.isNotEmpty && max == null) ||
        !filters.isValid) {
      setState(() => _message = AppStrings.of(context).invalidViewRange);
      return;
    }
    _filters = filters;
    _seenIds.clear();
    await _draw();
  }

  Future<void> _draw() async {
    if (_busy || _loading) return;
    final strings = AppStrings.of(context);
    setState(() {
      _loading = true;
      _candidate = null;
      _message = null;
    });
    try {
      final diary = await widget.service.draw(
        filters: _filters,
        excluded: _seenIds,
      );
      if (!mounted) return;
      setState(() {
        _candidate = diary;
        if (diary == null) {
          _message = _seenIds.isEmpty
              ? strings.noDeletionCandidates
              : strings.candidatesExhausted;
        } else {
          _seenIds.add(diary.id);
        }
      });
    } catch (error, stack) {
      developer.log(
        '随机删除抽取失败 request_id=${DateTime.now().microsecondsSinceEpoch}',
        name: 'diary.deletion',
        error: error,
        stackTrace: stack,
      );
      if (mounted) setState(() => _message = strings.deletionDrawFailed);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _deleteCandidate() async {
    final strings = AppStrings.of(context);
    final candidate = _candidate;
    if (_busy || candidate == null) return;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(strings.confirmMoveTrash),
        content: Text(strings.deletionPreview(
          candidate.date,
          candidate.viewCount,
          candidate.tags.isEmpty ? strings.none : candidate.tags.join('\u3001'),
          _preview(candidate.content),
        )),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(dialogContext, false),
              child: Text(strings.cancel)),
          FilledButton(
              onPressed: () => Navigator.pop(dialogContext, true),
              child: Text(strings.moveToTrash)),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    setState(() => _busy = true);
    try {
      final outcome = await widget.service.moveToTrash(candidate);
      if (!mounted) return;
      setState(() {
        _candidate = null;
        _message = switch (outcome) {
          RandomDeletionResult.confirmed => strings.confirmedTrash,
          RandomDeletionResult.queued => strings.queuedTrash,
          RandomDeletionResult.conflict => strings.conflictTrash,
        };
      });
      try {
        await widget.onChanged();
      } catch (error, stack) {
        developer.log(
          '随机删除后列表刷新失败 request_id=${DateTime.now().microsecondsSinceEpoch}',
          name: 'diary.deletion',
          error: error,
          stackTrace: stack,
        );
        if (mounted) {
          setState(() => _message = strings.deletionRefreshFailed);
        }
      }
    } catch (error, stack) {
      developer.log(
        '随机删除失败 request_id=${DateTime.now().microsecondsSinceEpoch} diary_id=${candidate.id}',
        name: 'diary.deletion',
        error: error,
        stackTrace: stack,
      );
      if (mounted) {
        setState(() => _message = strings.deletionUnconfirmed);
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  String _preview(String content) {
    final characters = content.runes.toList();
    if (characters.length <= 180) return content;
    return '${String.fromCharCodes(characters.take(180))}…';
  }

  @override
  Widget build(BuildContext context) {
    final strings = AppStrings.of(context);
    return Scaffold(
      appBar: AppBar(title: Text(strings.randomDeleteTitle)),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        Text(strings.randomDeleteNote),
        const SizedBox(height: 12),
        ListTile(
          contentPadding: EdgeInsets.zero,
          title: Text(_before == null
              ? strings.noDateLimit
              : strings
                  .dateBefore(_before!.toIso8601String().substring(0, 10))),
          trailing: Row(mainAxisSize: MainAxisSize.min, children: [
            if (_before != null)
              IconButton(
                tooltip: strings.clearDateFilter,
                onPressed: _busy
                    ? null
                    : () {
                        setState(() => _before = null);
                        _filterChanged();
                      },
                icon: const Icon(Icons.close),
              ),
            const Icon(Icons.date_range),
          ]),
          onTap: _busy ? null : _pickDate,
        ),
        Row(children: [
          Expanded(
            child: TextField(
              controller: _minController,
              keyboardType: TextInputType.number,
              onChanged: (_) => _filterChanged(),
              decoration: InputDecoration(labelText: strings.minimumViews),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: TextField(
              controller: _maxController,
              keyboardType: TextInputType.number,
              onChanged: (_) => _filterChanged(),
              decoration: InputDecoration(labelText: strings.maximumViews),
            ),
          ),
        ]),
        if (_tags.isNotEmpty)
          DropdownButton<String?>(
            value: _tags.contains(_tag) ? _tag : null,
            items: [
              DropdownMenuItem<String?>(
                value: null,
                child: Text(strings.allTagsOption),
              ),
              ..._tags.map((tag) => DropdownMenuItem<String?>(
                    value: tag,
                    child: Text(tag),
                  )),
            ],
            onChanged: _busy
                ? null
                : (value) {
                    setState(() => _tag = value);
                    _filterChanged();
                  },
          ),
        const SizedBox(height: 12),
        Wrap(spacing: 8, runSpacing: 8, children: [
          FilledButton.icon(
            onPressed: _busy || _loading ? null : _applyFilters,
            icon: const Icon(Icons.filter_alt),
            label: Text(strings.applyAndDraw),
          ),
          OutlinedButton(
            onPressed: _busy || _loading || _candidate == null ? null : _draw,
            child: Text(strings.redraw),
          ),
          TextButton(
            onPressed: _busy || _loading || _seenIds.isEmpty
                ? null
                : () {
                    _seenIds.clear();
                    _draw();
                  },
            child: Text(strings.resetDraw),
          ),
        ]),
        if (_loading || _busy) const LinearProgressIndicator(),
        if (_message != null)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 12),
            child: Text(_message!),
          ),
        if (_candidate != null) ...[
          const SizedBox(height: 16),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(strings.pendingCandidate,
                      style: Theme.of(context).textTheme.titleMedium),
                  const SizedBox(height: 8),
                  Text(strings.dateLabelShort(_candidate!.date)),
                  Text(strings.viewsLabel(_candidate!.viewCount)),
                  Text(strings.tagsValue(_candidate!.tags.isEmpty
                      ? strings.none
                      : _candidate!.tags.join('?'))),
                  Text(strings.summaryValue(_preview(_candidate!.content))),
                  const SizedBox(height: 12),
                  Row(children: [
                    TextButton(
                      onPressed: _busy
                          ? null
                          : () => setState(() => _candidate = null),
                      child: Text(strings.cancel),
                    ),
                    const Spacer(),
                    FilledButton(
                      onPressed: _busy ? null : _deleteCandidate,
                      child: Text(strings.moveToTrash),
                    ),
                  ]),
                ],
              ),
            ),
          ),
        ],
      ]),
    );
  }
}
