import 'package:flutter/material.dart';

import '../models/diary_tag.dart';
import '../services/diary_api.dart';

class TagManagerPage extends StatefulWidget {
  const TagManagerPage({super.key, required this.api});

  final DiaryApi api;

  @override
  State<TagManagerPage> createState() => _TagManagerPageState();
}

class _TagManagerPageState extends State<TagManagerPage> {
  late Future<List<DiaryTag>> _tags;
  String? _error;

  @override
  void initState() {
    super.initState();
    _tags = widget.api.fetchTags();
  }

  void _reload() {
    setState(() {
      _error = null;
      _tags = widget.api.fetchTags();
    });
  }

  Future<String?> _nameDialog({String? initial}) async {
    final controller = TextEditingController(text: initial ?? '');
    return showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(initial == null ? '新建标签' : '重命名标签'),
        content: TextField(
          controller: controller,
          autofocus: true,
          textInputAction: TextInputAction.done,
          decoration: const InputDecoration(labelText: '名称'),
          onSubmitted: (value) => Navigator.pop(context, value.trim()),
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(context), child: const Text('取消')),
          FilledButton(
              onPressed: () => Navigator.pop(context, controller.text.trim()),
              child: const Text('保存')),
        ],
      ),
    );
  }

  Future<void> _create() async {
    final name = await _nameDialog();
    if (!mounted || name == null || name.isEmpty) return;
    try {
      await widget.api.createTag(name);
      _reload();
    } catch (_) {
      if (mounted) setState(() => _error = '创建标签失败');
    }
  }

  Future<void> _rename(DiaryTag tag) async {
    final name = await _nameDialog(initial: tag.name);
    if (!mounted || name == null || name.isEmpty || name == tag.name) return;
    try {
      await widget.api.updateTag(tag, name);
      _reload();
    } catch (_) {
      if (mounted) setState(() => _error = '重命名失败；标签重复或仍有网络问题');
    }
  }

  Future<void> _delete(DiaryTag tag) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('删除标签？'),
        content: Text('确定删除“${tag.name}”？正在使用的标签不能删除。'),
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
    try {
      await widget.api.deleteTag(tag);
      _reload();
    } catch (_) {
      if (mounted) setState(() => _error = '删除失败；正在使用的标签不能删除');
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(
          title: const Text('标签管理'),
          actions: [
            IconButton(onPressed: _create, icon: const Icon(Icons.add))
          ],
        ),
        body: FutureBuilder<List<DiaryTag>>(
          future: _tags,
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting) {
              return const Center(child: CircularProgressIndicator());
            }
            final tags = snapshot.data ?? const <DiaryTag>[];
            return Column(children: [
              if (_error != null)
                MaterialBanner(content: Text(_error!), actions: [
                  TextButton(onPressed: _reload, child: const Text('重试'))
                ]),
              Expanded(
                child: tags.isEmpty
                    ? const Center(child: Text('暂无标签'))
                    : ListView.builder(
                        itemCount: tags.length,
                        itemBuilder: (context, index) {
                          final tag = tags[index];
                          return ListTile(
                            leading: const Icon(Icons.label_outline),
                            title: Text(tag.name),
                            trailing: PopupMenuButton<String>(
                              onSelected: (action) => action == 'rename'
                                  ? _rename(tag)
                                  : _delete(tag),
                              itemBuilder: (context) => const [
                                PopupMenuItem(
                                    value: 'rename', child: Text('重命名')),
                                PopupMenuItem(
                                    value: 'delete', child: Text('删除')),
                              ],
                            ),
                          );
                        },
                      ),
              ),
            ]);
          },
        ),
      );
}
