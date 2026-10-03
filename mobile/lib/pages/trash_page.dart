import 'dart:async';
import 'dart:developer' as developer;
import 'dart:io';

import 'package:flutter/material.dart';

import '../models/diary.dart';
import '../services/diary_api.dart';
import '../services/sync_manager.dart';
import '../trash/trash_batch.dart';

class TrashPage extends StatefulWidget {
  const TrashPage(
      {super.key, required this.api, required this.sync, this.onChanged});
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
          '回收站读取失败 request_id=${DateTime.now().microsecondsSinceEpoch}',
          name: 'diary.trash',
          error: error,
          stackTrace: stack);
      if (mounted) setState(() => _error = '回收站读取失败；已保留当前列表，请检查网络后重试。');
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

  Future<bool> _confirm(String title, String message) async =>
      await showDialog<bool>(
          context: context,
          builder: (dialogContext) =>
              AlertDialog(title: Text(title), content: Text(message), actions: [
                TextButton(
                    onPressed: () => Navigator.pop(dialogContext, false),
                    child: const Text('取消')),
                FilledButton(
                    onPressed: () => Navigator.pop(dialogContext, true),
                    child: const Text('继续')),
              ])) ??
      false;

  Future<bool> _confirmClear() async {
    if (!await _confirm(
        '清空整个回收站？', '将永久删除当前列表中的 ${_items.length} 篇日记。此操作不可恢复，是否继续？')) {
      return false;
    }
    if (!mounted) return false;
    var typed = false;
    return await showDialog<bool>(
            context: context,
            builder: (dialogContext) => StatefulBuilder(
                builder: (context, refresh) => AlertDialog(
                      title: const Text('再次确认永久删除'),
                      content: TextField(
                        decoration:
                            const InputDecoration(labelText: '请输入“清空”以确认'),
                        onChanged: (value) =>
                            refresh(() => typed = value.trim() == '清空'),
                      ),
                      actions: [
                        TextButton(
                            onPressed: () =>
                                Navigator.pop(dialogContext, false),
                            child: const Text('取消')),
                        FilledButton(
                            onPressed: typed
                                ? () => Navigator.pop(dialogContext, true)
                                : null,
                            child: const Text('永久清空')),
                      ],
                    ))) ??
        false;
  }

  Future<TrashOutcome> _restore(Diary diary) async {
    await widget.sync.restoreDiary(diary);
    final conflicts = await widget.sync.getConflicts();
    if (conflicts.any((item) => item.diaryId == diary.id)) {
      throw StateError('恢复版本冲突，等待人工审核');
    }
    final pending = await widget.sync.store.getOutbox();
    if (pending.any(
        (row) => row['entity_id'] == diary.id && row['action'] == 'restore')) {
      return TrashOutcome.deferred;
    }
    return TrashOutcome.completed;
  }

  Future<void> _run(List<Diary> diaries,
      {required bool purge, bool clearAll = false}) async {
    if (_busy || _loading || diaries.isEmpty) return;
    if (purge &&
        !await (clearAll
            ? _confirmClear()
            : _confirm(
                '确认永久删除？', '将永久删除 ${diaries.length} 篇日记，无法恢复。请确认没有选错。'))) {
      return;
    }
    if (!mounted) return;
    setState(() {
      _busy = true;
      _error = null;
      _result = null;
    });
    final result = await const TrashBatchService().run(diaries, (diary) async {
      if (!purge) return _restore(diary);
      await widget.api.permanentlyDeleteDiary(diary);
      return TrashOutcome.completed;
    },
        onFailure: (diary, error) => developer.log(
            '回收站单篇操作失败 request_id=${DateTime.now().microsecondsSinceEpoch} diary_id=${diary.id}',
            name: 'diary.trash',
            error: error),
        isInterrupted: (error) =>
            error is SocketException ||
            error is TimeoutException ||
            error is DiaryApiException && error.network,
        isUnsupported: purge
            ? (error) =>
                error is DiaryApiException &&
                (error.statusCode == 404 || error.statusCode == 405)
            : null);
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
        _error = '版本校验删除接口不可用或日记已被移除；未继续删除其余项目，请检查服务器版本。';
      } else if (result.unprocessed > 0) {
        _error = '操作中断或已离线排队，其余项目未处理；请稍后重试。';
      }
    });
    if (result.completed > 0 && !purge) {
      try {
        await widget.onChanged?.call();
      } catch (error, stack) {
        developer.log(
            '回收站恢复后列表刷新失败 request_id=${DateTime.now().microsecondsSinceEpoch}',
            name: 'diary.trash',
            error: error,
            stackTrace: stack);
      }
    }
    developer.log(
        '回收站批量操作 request_id=${DateTime.now().microsecondsSinceEpoch} '
        'completed=${result.completed} failed=${result.failed} '
        'unprocessed=${result.unprocessed}',
        name: 'diary.trash');
    if (mounted) await _load(clearError: false);
  }

  @override
  Widget build(BuildContext context) {
    final visible = filterTrash(_items, _query);
    final selected = _items
        .where((diary) => _selected.contains(diary.id))
        .toList(growable: false);
    return Scaffold(
      appBar: AppBar(
        title: Text(_selecting ? '已选择 ${_selected.length} 篇' : '回收站'),
        leading: _selecting
            ? IconButton(
                tooltip: '取消选择',
                onPressed: _busy ? null : _cancelSelection,
                icon: const Icon(Icons.close))
            : null,
        actions: [
          if (_selecting)
            IconButton(
                tooltip: '选择当前筛选结果',
                onPressed: _busy ? null : _selectVisible,
                icon: const Icon(Icons.select_all)),
          IconButton(
              tooltip: '刷新回收站',
              onPressed: _busy ? null : _load,
              icon: const Icon(Icons.refresh)),
        ],
      ),
      body: Column(children: [
        if (_loading || _busy) const LinearProgressIndicator(),
        Padding(
          padding: const EdgeInsets.fromLTRB(12, 6, 12, 3),
          child: TextField(
            onChanged: (value) => setState(() => _query = value),
            decoration: const InputDecoration(
              prefixIcon: Icon(Icons.search),
              hintText: '按日期或正文搜索，空格分隔关键词',
            ),
          ),
        ),
        if (_error != null)
          MaterialBanner(content: Text(_error!), actions: [
            TextButton(
                onPressed: _busy ? null : _load, child: const Text('重试读取')),
          ]),
        if (_result != null)
          Padding(
            padding: const EdgeInsets.all(8),
            child: Text('成功 ${_result!.completed} 篇，失败 ${_result!.failed} 篇，'
                '未处理 ${_result!.unprocessed} 篇。失败和未处理项目仍可单独重试。'),
          ),
        if (_items.isNotEmpty)
          Row(children: [
            TextButton.icon(
                onPressed: _busy ? null : _selectVisible,
                icon: const Icon(Icons.select_all),
                label: const Text('选择筛选结果')),
            const Spacer(),
            TextButton(
                onPressed: _busy
                    ? null
                    : () => _run(_items, purge: true, clearAll: true),
                child: const Text('清空回收站')),
          ]),
        if (_selecting)
          Wrap(spacing: 8, children: [
            FilledButton(
                onPressed: _busy || selected.isEmpty
                    ? null
                    : () => _run(selected, purge: false),
                child: const Text('批量恢复')),
            OutlinedButton(
                onPressed: _busy || selected.isEmpty
                    ? null
                    : () => _run(selected, purge: true),
                child: const Text('批量永久删除')),
          ]),
        Expanded(
            child: _loading && _items.isEmpty
                ? const Center(child: CircularProgressIndicator())
                : visible.isEmpty
                    ? Center(
                        child: Text(_items.isEmpty ? '回收站暂无日记' : '没有匹配的日记'))
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
                                        _busy ? null : (_) => _toggle(diary.id))
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
                                    itemBuilder: (_) => const [
                                      PopupMenuItem(
                                          value: 'restore', child: Text('恢复')),
                                      PopupMenuItem(
                                          value: 'purge', child: Text('永久删除')),
                                    ],
                                  ),
                          ));
                        })),
      ]),
    );
  }
}
