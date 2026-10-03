import 'dart:developer' as developer;

import 'package:flutter/material.dart';

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
      if (mounted) setState(() => _message = '本地候选读取失败，请稍后重试。');
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
      setState(() => _message = '查看次数请输入非负整数，且最少不大于最多。');
      return;
    }
    _filters = filters;
    _seenIds.clear();
    await _draw();
  }

  Future<void> _draw() async {
    if (_busy || _loading) return;
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
          _message =
              _seenIds.isEmpty ? '没有符合筛选条件的可删除日记。' : '当前筛选的候选已看完，可重置抽取记录。';
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
      if (mounted) setState(() => _message = '本地抽取失败，请检查缓存后重试。');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _deleteCandidate() async {
    final candidate = _candidate;
    if (_busy || candidate == null) return;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('确认移入回收站？'),
        content: Text('日期：${candidate.date}\n'
            '查看次数：${candidate.viewCount}\n'
            '标签：${candidate.tags.isEmpty ? '无' : candidate.tags.join('、')}\n\n'
            '${_preview(candidate.content)}\n\n'
            '此操作不会永久删除，服务器未确认时只保存待同步任务。'),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(dialogContext, false),
              child: const Text('取消')),
          FilledButton(
              onPressed: () => Navigator.pop(dialogContext, true),
              child: const Text('移入回收站')),
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
          RandomDeletionResult.confirmed => '服务器已确认移入回收站。',
          RandomDeletionResult.queued => '删除任务已保存待同步，服务器尚未确认。',
          RandomDeletionResult.conflict => '版本冲突：已保留删除意图，请到同步冲突审核处理；服务器未删除。',
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
          setState(() => _message = '删除状态已保存，但列表刷新失败，请手动刷新。');
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
        setState(() => _message = '删除未确认成功；请核对日记和同步状态后重试。');
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
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('随机删除候选')),
        body: ListView(padding: const EdgeInsets.all(16), children: [
          const Text('候选来自本设备缓存，不代表服务器全部日记。仅提交移入回收站，不会永久删除。'),
          const SizedBox(height: 12),
          ListTile(
            contentPadding: EdgeInsets.zero,
            title: Text(_before == null
                ? '创建日期不限'
                : '创建日期不晚于 ${_before!.toIso8601String().substring(0, 10)}'),
            trailing: Row(mainAxisSize: MainAxisSize.min, children: [
              if (_before != null)
                IconButton(
                    tooltip: '清除日期条件',
                    onPressed: _busy
                        ? null
                        : () {
                            setState(() => _before = null);
                            _filterChanged();
                          },
                    icon: const Icon(Icons.close)),
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
                    decoration: const InputDecoration(labelText: '最少查看次数'))),
            const SizedBox(width: 12),
            Expanded(
                child: TextField(
                    controller: _maxController,
                    keyboardType: TextInputType.number,
                    onChanged: (_) => _filterChanged(),
                    decoration: const InputDecoration(labelText: '最多查看次数'))),
          ]),
          if (_tags.isNotEmpty)
            DropdownButton<String?>(
              value: _tags.contains(_tag) ? _tag : null,
              items: [
                const DropdownMenuItem<String?>(
                    value: null, child: Text('全部标签')),
                ..._tags.map((tag) =>
                    DropdownMenuItem<String?>(value: tag, child: Text(tag))),
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
              label: const Text('应用筛选并抽取'),
            ),
            OutlinedButton(
                onPressed:
                    _busy || _loading || _candidate == null ? null : _draw,
                child: const Text('重新抽取')),
            TextButton(
                onPressed: _busy || _loading || _seenIds.isEmpty
                    ? null
                    : () {
                        _seenIds.clear();
                        _draw();
                      },
                child: const Text('重置抽取记录')),
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
                    Text('待确认候选',
                        style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: 8),
                    Text('日期：${_candidate!.date}'),
                    Text('查看次数：${_candidate!.viewCount}'),
                    Text(
                        '标签：${_candidate!.tags.isEmpty ? '无' : _candidate!.tags.join('、')}'),
                    Text('正文摘要：${_preview(_candidate!.content)}'),
                    const SizedBox(height: 12),
                    Row(children: [
                      TextButton(
                          onPressed: _busy
                              ? null
                              : () => setState(() => _candidate = null),
                          child: const Text('取消')),
                      const Spacer(),
                      FilledButton(
                          onPressed: _busy ? null : _deleteCandidate,
                          child: const Text('移入回收站')),
                    ]),
                  ]),
            )),
          ],
        ]),
      );
}
