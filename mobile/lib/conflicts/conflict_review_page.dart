import 'dart:developer' as developer;

import 'package:flutter/material.dart';

import '../services/sync_manager.dart';
import 'diary_conflict.dart';

class ConflictReviewPage extends StatefulWidget {
  const ConflictReviewPage(
      {super.key, required this.sync, required this.onResolved});
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

  void _reload() => setState(() {
        _conflicts = widget.sync.getConflicts();
      });

  Future<void> _refresh(DiaryConflict conflict) async {
    if (_busyId != null) return;
    setState(() => _busyId = conflict.diaryId);
    try {
      await widget.sync.refreshConflict(conflict);
      if (mounted) setState(() => _message = '服务器版本已更新，请重新核对。');
    } catch (error, stack) {
      developer.log(
          '刷新冲突失败 request_id=${DateTime.now().microsecondsSinceEpoch}',
          name: 'diary.conflict',
          error: error,
          stackTrace: stack);
      if (mounted) setState(() => _message = '暂时无法获取服务器版本，已保留本地内容。');
    } finally {
      if (mounted) {
        setState(() => _busyId = null);
        _reload();
      }
    }
  }

  Future<void> _resolve(DiaryConflict conflict, bool keepLocal) async {
    if (_busyId != null || conflict.remote == null) return;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(keepLocal ? '确认保留本地版本？' : '确认采用服务器版本？'),
        content: Text(keepLocal
            ? '将基于当前服务器版本重新提交本地正文与标签；请确认两端差异。'
            : '将丢弃当前待同步的正文或恢复操作；本设备查看事件和统计保持独立。'),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(dialogContext, false),
              child: const Text('取消')),
          FilledButton(
              onPressed: () => Navigator.pop(dialogContext, true),
              child: const Text('确认')),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    setState(() => _busyId = conflict.diaryId);
    try {
      await widget.sync.resolveConflict(conflict, keepLocal: keepLocal);
      if (mounted) setState(() => _message = '已处理冲突，请查看同步状态。');
      try {
        await widget.onResolved();
      } catch (error, stack) {
        developer.log(
            '冲突处理后的列表刷新失败 request_id=${DateTime.now().microsecondsSinceEpoch}',
            name: 'diary.conflict',
            error: error,
            stackTrace: stack);
        if (mounted) setState(() => _message = '冲突已处理，列表刷新失败，请手动刷新。');
      }
    } catch (error, stack) {
      developer.log(
          '处理冲突失败 request_id=${DateTime.now().microsecondsSinceEpoch}',
          name: 'diary.conflict',
          error: error,
          stackTrace: stack);
      if (mounted) setState(() => _message = '处理失败或版本已变化，请重新核对后重试。');
    } finally {
      if (mounted) {
        setState(() => _busyId = null);
        _reload();
      }
    }
  }

  String _summary(String content) =>
      content.length > 160 ? '${content.substring(0, 160)}…' : content;

  Widget _details(DiaryConflict conflict, bool local) {
    final diary = local ? conflict.local : conflict.remote;
    if (diary == null) {
      return const Text('服务器版本暂不可用；重新获取前不能处理冲突。');
    }
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(local ? '本地版本 ${diary.version}' : '服务器版本 ${diary.version}',
          style: const TextStyle(fontWeight: FontWeight.bold)),
      Text('更新：${diary.updatedAt.isEmpty ? '未知' : diary.updatedAt}'),
      Text('标签：${diary.tags.isEmpty ? '无' : diary.tags.join('、')}'),
      Text('正文摘要：${_summary(diary.content)}'),
      if (diary.deletedAt != null) const Text('已删除或等待恢复'),
    ]);
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('同步冲突审核'), actions: [
          IconButton(
              tooltip: '刷新冲突列表',
              onPressed: _reload,
              icon: const Icon(Icons.refresh))
        ]),
        body: FutureBuilder<List<DiaryConflict>>(
          future: _conflicts,
          builder: (context, snapshot) {
            if (!snapshot.hasData &&
                snapshot.connectionState == ConnectionState.waiting) {
              return const Center(child: CircularProgressIndicator());
            }
            if (snapshot.hasError) {
              return const Center(child: Text('读取冲突列表失败，请重试。'));
            }
            final conflicts = snapshot.data ?? const <DiaryConflict>[];
            return ListView(padding: const EdgeInsets.all(16), children: [
              if (_message != null)
                Padding(
                    padding: const EdgeInsets.all(8), child: Text(_message!)),
              if (conflicts.isEmpty)
                const Text('暂无待审核的同步冲突。')
              else
                for (final conflict in conflicts)
                  Card(
                      child: Padding(
                    padding: const EdgeInsets.all(12),
                    child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                              '${conflict.local.date} · ${conflict.action == 'restore' ? '恢复' : conflict.action == 'delete' ? '删除' : '编辑'}冲突',
                              style: Theme.of(context).textTheme.titleMedium),
                          const SizedBox(height: 8),
                          _details(conflict, true),
                          const Divider(height: 24),
                          _details(conflict, false),
                          if (conflict.remote?.deletedAt != null &&
                              conflict.action != 'restore')
                            const Text('服务器已删除该日记；只能采用服务器状态，不能自动恢复本地编辑。'),
                          if (conflict.remote?.deletedAt == null &&
                              conflict.action == 'restore')
                            const Text('服务器已恢复该日记；无需重复提交恢复操作。'),
                          const SizedBox(height: 8),
                          Wrap(spacing: 8, runSpacing: 8, children: [
                            OutlinedButton(
                                onPressed: _busyId == null
                                    ? () => _refresh(conflict)
                                    : null,
                                child: const Text('刷新服务器版本')),
                            OutlinedButton(
                                onPressed: _busyId == null
                                    ? () => setState(() =>
                                        _message = '已暂不处理，本地内容与待同步任务保持不变。')
                                    : null,
                                child: const Text('暂不处理')),
                            FilledButton(
                                onPressed: _busyId == null &&
                                        conflict.remote != null &&
                                        (conflict.action == 'restore'
                                            ? conflict.remote!.deletedAt != null
                                            : conflict.remote!.deletedAt ==
                                                null)
                                    ? () => _resolve(conflict, true)
                                    : null,
                                child: const Text('保留本地')),
                            FilledButton(
                                onPressed:
                                    _busyId == null && conflict.remote != null
                                        ? () => _resolve(conflict, false)
                                        : null,
                                child: const Text('采用服务器')),
                          ]),
                        ]),
                  )),
            ]);
          },
        ),
      );
}
