import 'dart:developer' as developer;

import 'package:flutter/material.dart';

import '../models/diary.dart';
import '../services/diary_api.dart';
import '../services/sync_manager.dart';

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
  late Future<List<Diary>> _trash;
  String? _error;

  @override
  void initState() {
    super.initState();
    _trash = widget.api.fetchTrash();
  }

  void _reload() => setState(() {
        _error = null;
        _trash = widget.api.fetchTrash();
      });

  Future<void> _restore(Diary diary) async {
    try {
      await widget.sync.restoreDiary(diary);
      final conflicts = await widget.sync.getConflicts();
      final pending = await widget.sync.store.getOutbox();
      if (!mounted) return;
      if (conflicts.any((item) => item.diaryId == diary.id)) {
        setState(() => _error = '恢复版本冲突，已保留请求，请前往同步冲突审核。');
      } else if (pending.any((row) =>
          row['entity_id'] == diary.id && row['action'] == 'restore')) {
        setState(() => _error = '恢复请求已离线保存，联网后将继续同步。');
      } else {
        _reload();
        await widget.onChanged?.call();
      }
    } catch (error, stack) {
      developer.log(
          '回收站恢复失败 request_id=${DateTime.now().microsecondsSinceEpoch}',
          name: 'diary.trash',
          error: error,
          stackTrace: stack);
      if (mounted) setState(() => _error = '恢复失败，请核对版本和网络后重试。');
    }
  }

  Future<void> _purge(Diary diary) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('永久删除日记？'),
        content: const Text('永久删除后无法恢复，请再次确认。'),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('取消')),
          FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('永久删除')),
        ],
      ),
    );
    if (confirmed != true) return;
    try {
      await widget.api.permanentlyDeleteDiary(diary);
      if (mounted) _reload();
    } catch (error, stack) {
      developer.log(
          '回收站删除失败 request_id=${DateTime.now().microsecondsSinceEpoch}',
          name: 'diary.trash',
          error: error,
          stackTrace: stack);
      if (mounted) setState(() => _error = '永久删除失败，请重试。');
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('回收站'), actions: [
          IconButton(
              tooltip: '刷新回收站',
              onPressed: _reload,
              icon: const Icon(Icons.refresh))
        ]),
        body: FutureBuilder<List<Diary>>(
          future: _trash,
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting) {
              return const Center(child: CircularProgressIndicator());
            }
            final items = snapshot.data ?? const <Diary>[];
            return Column(children: [
              if (_error != null)
                MaterialBanner(content: Text(_error!), actions: [
                  TextButton(onPressed: _reload, child: const Text('刷新'))
                ]),
              Expanded(
                child: snapshot.hasError
                    ? const Center(child: Text('服务器暂不可用，无法读取回收站。'))
                    : items.isEmpty
                        ? const Center(child: Text('回收站暂无日记'))
                        : ListView.builder(
                            itemCount: items.length,
                            itemBuilder: (context, index) {
                              final diary = items[index];
                              return Card(
                                  child: ListTile(
                                title: Text(diary.date),
                                subtitle: Text(diary.content,
                                    maxLines: 3,
                                    overflow: TextOverflow.ellipsis),
                                trailing: PopupMenuButton<String>(
                                  onSelected: (action) => action == 'restore'
                                      ? _restore(diary)
                                      : _purge(diary),
                                  itemBuilder: (context) => const [
                                    PopupMenuItem(
                                        value: 'restore', child: Text('恢复')),
                                    PopupMenuItem(
                                        value: 'purge', child: Text('永久删除')),
                                  ],
                                ),
                              ));
                            },
                          ),
              ),
            ]);
          },
        ),
      );
}
