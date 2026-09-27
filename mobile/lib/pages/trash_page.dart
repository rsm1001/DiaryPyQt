import 'package:flutter/material.dart';

import '../models/diary.dart';
import '../services/diary_api.dart';

class TrashPage extends StatefulWidget {
  const TrashPage({super.key, required this.api});
  final DiaryApi api;

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
      await widget.api.restoreDiary(diary);
      _reload();
    } catch (_) {
      if (mounted) setState(() => _error = '???????????');
    }
  }

  Future<void> _purge(Diary diary) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('?????'),
        content: const Text('??????????????????????'),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('??')),
          FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('????')),
        ],
      ),
    );
    if (confirmed != true) return;
    try {
      await widget.api.permanentlyDeleteDiary(diary);
      _reload();
    } catch (_) {
      if (mounted) setState(() => _error = '??????');
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('???'), actions: [
          IconButton(onPressed: _reload, icon: const Icon(Icons.refresh))
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
                  TextButton(onPressed: _reload, child: const Text('??'))
                ]),
              Expanded(
                child: items.isEmpty
                    ? const Center(child: Text('?????'))
                    : ListView.builder(
                        itemCount: items.length,
                        itemBuilder: (context, index) {
                          final diary = items[index];
                          return Card(
                            child: ListTile(
                              title: Text(diary.date),
                              subtitle: Text(diary.content,
                                  maxLines: 3, overflow: TextOverflow.ellipsis),
                              trailing: PopupMenuButton<String>(
                                onSelected: (action) => action == 'restore'
                                    ? _restore(diary)
                                    : _purge(diary),
                                itemBuilder: (context) => const [
                                  PopupMenuItem(
                                      value: 'restore', child: Text('??')),
                                  PopupMenuItem(
                                      value: 'purge', child: Text('????')),
                                ],
                              ),
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
