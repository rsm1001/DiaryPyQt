import 'package:flutter/material.dart';

import '../services/diary_filter.dart';

Future<DiarySearchOptions?> showAdvancedSearchDialog(
  BuildContext context,
  DiarySearchOptions initial, {
  List<String> availableTags = const [],
}) =>
    showDialog<DiarySearchOptions>(
      context: context,
      builder: (_) => _AdvancedSearchDialog(
        initial: initial,
        availableTags: availableTags,
      ),
    );

class _AdvancedSearchDialog extends StatefulWidget {
  const _AdvancedSearchDialog(
      {required this.initial, required this.availableTags});

  final DiarySearchOptions initial;
  final List<String> availableTags;

  @override
  State<_AdvancedSearchDialog> createState() => _AdvancedSearchDialogState();
}

class _AdvancedSearchDialogState extends State<_AdvancedSearchDialog> {
  DateTime? _from;
  DateTime? _to;
  final Set<String> _tags = {};
  late final TextEditingController _minViews;
  late final TextEditingController _maxViews;

  @override
  void initState() {
    super.initState();
    _from = widget.initial.from;
    _to = widget.initial.to;
    _tags.addAll(widget.initial.tags);
    _minViews =
        TextEditingController(text: widget.initial.minViews?.toString());
    _maxViews =
        TextEditingController(text: widget.initial.maxViews?.toString());
  }

  @override
  void dispose() {
    _minViews.dispose();
    _maxViews.dispose();
    super.dispose();
  }

  Future<void> _pickDate(bool start) async {
    final selected = await showDatePicker(
      context: context,
      initialDate: (start ? _from : _to) ?? DateTime.now(),
      firstDate: DateTime(1900),
      lastDate: DateTime(2100),
    );
    if (selected != null && mounted) {
      setState(() {
        if (start) {
          _from = selected;
        } else {
          _to = selected;
        }
      });
    }
  }

  void _apply() {
    final min = _minViews.text.trim().isEmpty
        ? null
        : int.tryParse(_minViews.text.trim());
    final max = _maxViews.text.trim().isEmpty
        ? null
        : int.tryParse(_maxViews.text.trim());
    if ((min != null && min < 0) ||
        (max != null && max < 0) ||
        (_minViews.text.trim().isNotEmpty && min == null) ||
        (_maxViews.text.trim().isNotEmpty && max == null) ||
        (min != null && max != null && min > max) ||
        (_from != null && _to != null && _from!.isAfter(_to!))) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('请检查日期与次数范围')),
      );
      return;
    }
    Navigator.pop(
      context,
      DiarySearchOptions(
        from: _from,
        to: _to,
        minViews: min,
        maxViews: max,
        tags: List.unmodifiable(_tags.toList()..sort()),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final tags = {...widget.availableTags, ...widget.initial.tags}.toList()
      ..sort();
    return AlertDialog(
      title: const Text('高级搜索'),
      content: SingleChildScrollView(
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          ListTile(
            title: Text(_from == null
                ? '开始日期不限'
                : '开始：${_from!.toIso8601String().substring(0, 10)}'),
            trailing: const Icon(Icons.date_range),
            onTap: () => _pickDate(true),
          ),
          ListTile(
            title: Text(_to == null
                ? '结束日期不限'
                : '结束：${_to!.toIso8601String().substring(0, 10)}'),
            trailing: const Icon(Icons.date_range),
            onTap: () => _pickDate(false),
          ),
          TextField(
            controller: _minViews,
            keyboardType: TextInputType.number,
            decoration: const InputDecoration(labelText: '最少查看次数'),
          ),
          TextField(
            controller: _maxViews,
            keyboardType: TextInputType.number,
            decoration: const InputDecoration(labelText: '最多查看次数'),
          ),
          if (tags.isNotEmpty) ...[
            const Align(
              alignment: Alignment.centerLeft,
              child: Padding(
                padding: EdgeInsets.only(top: 12),
                child: Text('标签组合（须包含所有选中标签）'),
              ),
            ),
            Wrap(
              spacing: 8,
              children: [
                for (final tag in tags)
                  FilterChip(
                    label: Text(tag),
                    selected: _tags.contains(tag),
                    onSelected: (selected) => setState(() {
                      if (selected) {
                        _tags.add(tag);
                      } else {
                        _tags.remove(tag);
                      }
                    }),
                  ),
              ],
            ),
          ],
        ]),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context, const DiarySearchOptions()),
          child: const Text('清除高级条件'),
        ),
        FilledButton(onPressed: _apply, child: const Text('应用')),
      ],
    );
  }
}
