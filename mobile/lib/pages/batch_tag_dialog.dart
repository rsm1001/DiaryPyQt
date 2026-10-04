import 'package:flutter/material.dart';

import '../localization/app_strings.dart';
import '../tags/batch_tag_policy.dart';

class BatchTagSelection {
  const BatchTagSelection({required this.tags, required this.mode});

  final List<String> tags;
  final BatchTagMode mode;
}

Future<BatchTagSelection?> showBatchTagDialog(
  BuildContext context, {
  required int diaryCount,
  required List<String> availableTags,
}) =>
    showDialog<BatchTagSelection>(
      context: context,
      builder: (_) => _BatchTagDialog(
        diaryCount: diaryCount,
        availableTags: availableTags,
      ),
    );

class _BatchTagDialog extends StatefulWidget {
  const _BatchTagDialog(
      {required this.diaryCount, required this.availableTags});

  final int diaryCount;
  final List<String> availableTags;

  @override
  State<_BatchTagDialog> createState() => _BatchTagDialogState();
}

class _BatchTagDialogState extends State<_BatchTagDialog> {
  final _controller = TextEditingController();
  BatchTagMode _mode = BatchTagMode.add;
  String? _error;

  List<String> get _tags => _controller.text
      .split(RegExp(r'[,\uff0c]'))
      .map((tag) => tag.trim())
      .where((tag) => tag.isNotEmpty)
      .toSet()
      .toList(growable: false);

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _toggleTag(String tag) {
    final selected = _tags.toSet();
    if (!selected.add(tag)) selected.remove(tag);
    setState(() {
      _controller.text = selected.join(', ');
      _error = null;
    });
  }

  void _submit() {
    final tags = _tags;
    if (tags.isEmpty && _mode != BatchTagMode.replace) {
      setState(() => _error = AppStrings.of(context).tagsRequired);
      return;
    }
    Navigator.of(context).pop(BatchTagSelection(tags: tags, mode: _mode));
  }

  @override
  Widget build(BuildContext context) {
    final strings = AppStrings.of(context);
    return AlertDialog(
      title: Text(strings.batchTags(widget.diaryCount)),
      content: SingleChildScrollView(
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          SegmentedButton<BatchTagMode>(
            segments: [
              ButtonSegment(
                  value: BatchTagMode.add, label: Text(strings.addTags)),
              ButtonSegment(
                  value: BatchTagMode.remove, label: Text(strings.removeTags)),
              ButtonSegment(
                  value: BatchTagMode.replace,
                  label: Text(strings.replaceTags)),
            ],
            selected: {_mode},
            onSelectionChanged: (selected) => setState(() {
              _mode = selected.single;
              _error = null;
            }),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _controller,
            onChanged: (_) => setState(() => _error = null),
            decoration: InputDecoration(
              labelText: strings.tagsCommaHint,
              errorText: _error,
            ),
          ),
          if (widget.availableTags.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 12),
              child: Wrap(spacing: 8, children: [
                for (final tag in widget.availableTags)
                  FilterChip(
                    label: Text(tag),
                    selected: _tags.contains(tag),
                    onSelected: (_) => _toggleTag(tag),
                  ),
              ]),
            ),
          if (_mode == BatchTagMode.replace)
            Padding(
              padding: const EdgeInsets.only(top: 12),
              child: Text(strings.replaceTagsNote),
            ),
        ]),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: Text(strings.cancel),
        ),
        FilledButton(onPressed: _submit, child: Text(strings.apply)),
      ],
    );
  }
}
