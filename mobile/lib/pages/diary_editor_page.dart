import 'package:flutter/material.dart';

import '../localization/app_strings.dart';
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
      .split(RegExp(r'[,?]'))
      .map((tag) => tag.trim())
      .where((tag) => tag.isNotEmpty)
      .toSet()
      .toList(growable: false);

  Future<void> _save() async {
    final strings = AppStrings.of(context);
    final content = _content.text.trim();
    if (content.isEmpty) {
      setState(() => _error = strings.contentRequired);
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
        await widget.sync.updateDiary(
          widget.diary!,
          content: content,
          tags: _tagNames,
        );
      }
      if (mounted) Navigator.of(context).pop(true);
    } catch (_) {
      if (mounted) setState(() => _error = strings.diarySaveFailed);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _delete() async {
    final diary = widget.diary;
    if (diary == null) return;
    final strings = AppStrings.of(context);
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(strings.deleteDiaryTitle),
        content: Text(strings.deleteDiaryMessage),
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
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await widget.sync.deleteDiary(diary);
      if (mounted) Navigator.of(context).pop(true);
    } catch (_) {
      if (mounted) setState(() => _error = strings.diaryDeleteFailed);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final strings = AppStrings.of(context);
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.diary == null
            ? strings.newDiaryTitle
            : strings.editDiaryTitle),
      ),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: ListView(children: [
          ListTile(
            title: Text(strings
                .dateText(_selectedDate.toIso8601String().substring(0, 10))),
            subtitle: Text(widget.diary == null
                ? strings.newDiaryDateHint
                : strings.existingDiaryDateHint),
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
            decoration: InputDecoration(
              labelText: strings.content,
              border: const OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _tags,
            enabled: !_saving,
            decoration: InputDecoration(
              labelText: strings.tagsField,
              hintText: strings.tagsHint,
              border: const OutlineInputBorder(),
            ),
          ),
          if (_error != null)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 12),
              child: Text(_error!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error)),
            ),
          const SizedBox(height: 12),
          FilledButton(
            onPressed: _saving ? null : _save,
            child: Text(strings.saveDiary),
          ),
          if (widget.diary != null)
            TextButton(
              onPressed: _saving ? null : _delete,
              child: Text(strings.deleteDiary),
            ),
        ]),
      ),
    );
  }
}
