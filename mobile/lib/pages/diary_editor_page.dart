import 'package:flutter/material.dart';

import '../models/diary.dart';
import '../services/sync_manager.dart';

class DiaryEditorPage extends StatefulWidget {
  const DiaryEditorPage({super.key, required this.sync, this.diary});

  final SyncManager sync;
  final Diary? diary;

  @override
  State<DiaryEditorPage> createState() => _DiaryEditorPageState();
}

class _DiaryEditorPageState extends State<DiaryEditorPage> {
  late final TextEditingController _content;
  late final TextEditingController _tags;
  late DateTime _selectedDate;
  bool _saving = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _content = TextEditingController(text: widget.diary?.content ?? '');
    _tags = TextEditingController(text: widget.diary?.tags.join(', ') ?? '');
    _selectedDate =
        DateTime.tryParse(widget.diary?.date ?? '') ?? DateTime.now();
  }

  @override
  void dispose() {
    _content.dispose();
    _tags.dispose();
    super.dispose();
  }

  List<String> get _tagNames => _tags.text
      .split(RegExp(r'[,，]'))
      .map((tag) => tag.trim())
      .where((tag) => tag.isNotEmpty)
      .toSet()
      .toList(growable: false);

  Future<void> _save() async {
    final content = _content.text.trim();
    if (content.isEmpty) {
      setState(() => _error = '正文不能为空');
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      if (widget.diary == null) {
        await widget.sync.createDiary(
          date: _selectedDate.toIso8601String().substring(0, 10),
          content: content,
          tags: _tagNames,
        );
      } else {
        await widget.sync
            .updateDiary(widget.diary!, content: content, tags: _tagNames);
      }
      if (mounted) Navigator.of(context).pop(true);
    } catch (_) {
      if (mounted) setState(() => _error = '保存失败，请检查网络；版本冲突时先刷新再编辑');
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _delete() async {
    final diary = widget.diary;
    if (diary == null) return;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('删除日记？'),
        content: const Text('这篇日记会被移到服务器回收状态；请确认没有未保存的更改。'),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('取消')),
          FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('删除')),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await widget.sync.deleteDiary(diary);
      if (mounted) Navigator.of(context).pop(true);
    } catch (_) {
      if (mounted) setState(() => _error = '删除失败，请检查网络；版本冲突时先刷新');
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: Text(widget.diary == null ? '新建日记' : '编辑日记')),
        body: Padding(
          padding: const EdgeInsets.all(16),
          child: ListView(children: [
            ListTile(
              title: Text(
                  '日期：${_selectedDate.toIso8601String().substring(0, 10)}'),
              subtitle: widget.diary == null
                  ? const Text('新日记可选择日期')
                  : const Text('已有日记的创建日期不修改'),
              onTap: widget.diary != null || _saving
                  ? null
                  : () async {
                      final value = await showDatePicker(
                        context: context,
                        initialDate: _selectedDate,
                        firstDate: DateTime(1900),
                        lastDate: DateTime(2100),
                      );
                      if (value != null && mounted) {
                        setState(() => _selectedDate = value);
                      }
                    },
            ),
            TextField(
              controller: _content,
              enabled: !_saving,
              maxLines: 12,
              minLines: 6,
              decoration: const InputDecoration(
                  labelText: '正文', border: OutlineInputBorder()),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _tags,
              enabled: !_saving,
              decoration: const InputDecoration(
                labelText: '标签',
                hintText: '用逗号分隔多个标签',
                border: OutlineInputBorder(),
              ),
            ),
            if (_error != null)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 12),
                child: Text(_error!,
                    style:
                        TextStyle(color: Theme.of(context).colorScheme.error)),
              ),
            const SizedBox(height: 12),
            FilledButton(
                onPressed: _saving ? null : _save, child: const Text('保存')),
            if (widget.diary != null)
              TextButton(
                  onPressed: _saving ? null : _delete,
                  child: const Text('删除日记')),
          ]),
        ),
      );
}
