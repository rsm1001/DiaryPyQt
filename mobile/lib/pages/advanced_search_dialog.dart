import 'package:flutter/material.dart';

import '../services/diary_filter.dart';

Future<DiarySearchOptions?> showAdvancedSearchDialog(
  BuildContext context,
  DiarySearchOptions initial,
) =>
    showDialog<DiarySearchOptions>(
      context: context,
      builder: (_) => _AdvancedSearchDialog(initial: initial),
    );

class _AdvancedSearchDialog extends StatefulWidget {
  const _AdvancedSearchDialog({required this.initial});

  final DiarySearchOptions initial;

  @override
  State<_AdvancedSearchDialog> createState() => _AdvancedSearchDialogState();
}

class _AdvancedSearchDialogState extends State<_AdvancedSearchDialog> {
  DateTime? _from;
  DateTime? _to;
  late final TextEditingController _minViews;
  late final TextEditingController _maxViews;

  @override
  void initState() {
    super.initState();
    _from = widget.initial.from;
    _to = widget.initial.to;
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
        const SnackBar(
            content: Text(
                '\u8bf7\u68c0\u67e5\u65e5\u671f\u4e0e\u6b21\u6570\u8303\u56f4')),
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
        ));
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
        title: const Text('\u9ad8\u7ea7\u641c\u7d22'),
        content: SingleChildScrollView(
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            ListTile(
              title: Text(_from == null
                  ? '\u5f00\u59cb\u65e5\u671f\u4e0d\u9650'
                  : '\u5f00\u59cb\uff1a${_from!.toIso8601String().substring(0, 10)}'),
              trailing: const Icon(Icons.date_range),
              onTap: () => _pickDate(true),
            ),
            ListTile(
              title: Text(_to == null
                  ? '\u7ed3\u675f\u65e5\u671f\u4e0d\u9650'
                  : '\u7ed3\u675f\uff1a${_to!.toIso8601String().substring(0, 10)}'),
              trailing: const Icon(Icons.date_range),
              onTap: () => _pickDate(false),
            ),
            TextField(
              controller: _minViews,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(
                  labelText: '\u6700\u5c11\u67e5\u770b\u6b21\u6570'),
            ),
            TextField(
              controller: _maxViews,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(
                  labelText: '\u6700\u591a\u67e5\u770b\u6b21\u6570'),
            ),
          ]),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, const DiarySearchOptions()),
            child: const Text('\u6e05\u9664\u6761\u4ef6'),
          ),
          FilledButton(onPressed: _apply, child: const Text('\u5e94\u7528')),
        ],
      );
}
