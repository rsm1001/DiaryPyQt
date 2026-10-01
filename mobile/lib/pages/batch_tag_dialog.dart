import 'package:flutter/material.dart';

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
      setState(
          () => _error = '\u8bf7\u9009\u62e9\u6216\u8f93\u5165\u6807\u7b7e');
      return;
    }
    Navigator.of(context).pop(BatchTagSelection(tags: tags, mode: _mode));
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
        title: Text(
            '\u6279\u91cf\u6807\u7b7e\uff08${widget.diaryCount} \u7bc7\uff09'),
        content: SingleChildScrollView(
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            SegmentedButton<BatchTagMode>(
              segments: const [
                ButtonSegment(
                    value: BatchTagMode.add, label: Text('\u6dfb\u52a0')),
                ButtonSegment(
                    value: BatchTagMode.remove, label: Text('\u79fb\u9664')),
                ButtonSegment(
                    value: BatchTagMode.replace, label: Text('\u66ff\u6362')),
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
                labelText: '\u6807\u7b7e\uff08\u9017\u53f7\u5206\u9694\uff09',
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
              const Padding(
                padding: EdgeInsets.only(top: 12),
                child: Text(
                    '\u66ff\u6362\u4f1a\u79fb\u9664\u672a\u9009\u4e2d\u7684\u65e7\u6807\u7b7e\uff1b\u7559\u7a7a\u8868\u793a\u6e05\u7a7a\u3002'),
              ),
          ]),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('\u53d6\u6d88'),
          ),
          FilledButton(onPressed: _submit, child: const Text('\u5e94\u7528')),
        ],
      );
}
