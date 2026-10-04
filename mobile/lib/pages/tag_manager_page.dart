import 'package:flutter/material.dart';

import '../localization/app_strings.dart';
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
    final strings = AppStrings.of(context);
    final controller = TextEditingController(text: initial ?? '');
    return showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(initial == null ? strings.createTag : strings.renameTag),
        content: TextField(
          controller: controller,
          autofocus: true,
          textInputAction: TextInputAction.done,
          decoration: InputDecoration(labelText: strings.name),
          onSubmitted: (value) => Navigator.pop(context, value.trim()),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: Text(strings.cancel),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, controller.text.trim()),
            child: Text(strings.save),
          ),
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
      if (mounted) {
        setState(() => _error = AppStrings.of(context).createTagFailed);
      }
    }
  }

  Future<void> _rename(DiaryTag tag) async {
    final name = await _nameDialog(initial: tag.name);
    if (!mounted || name == null || name.isEmpty || name == tag.name) return;
    try {
      await widget.api.updateTag(tag, name);
      _reload();
    } catch (_) {
      if (mounted) {
        setState(() => _error = AppStrings.of(context).renameTagFailed);
      }
    }
  }

  Future<void> _delete(DiaryTag tag) async {
    final strings = AppStrings.of(context);
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(strings.deleteTagTitle),
        content: Text(strings.deleteTagMessage(tag.name)),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: Text(strings.cancel),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: Text(strings.purge),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    try {
      await widget.api.deleteTag(tag);
      _reload();
    } catch (_) {
      if (mounted) setState(() => _error = strings.deleteTagFailed);
    }
  }

  @override
  Widget build(BuildContext context) {
    final strings = AppStrings.of(context);
    return Scaffold(
      appBar: AppBar(
        title: Text(strings.tagManagement),
        actions: [IconButton(onPressed: _create, icon: const Icon(Icons.add))],
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
                TextButton(onPressed: _reload, child: Text(strings.retry)),
              ]),
            Expanded(
              child: tags.isEmpty
                  ? Center(child: Text(strings.noTagsAvailable))
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
                            itemBuilder: (context) => [
                              PopupMenuItem(
                                  value: 'rename', child: Text(strings.rename)),
                              PopupMenuItem(
                                  value: 'delete', child: Text(strings.purge)),
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
}
