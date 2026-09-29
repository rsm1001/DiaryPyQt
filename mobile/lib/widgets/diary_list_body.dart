import 'package:flutter/material.dart';

import '../models/diary.dart';
import '../services/diary_filter.dart';
import '../services/double_playback_service.dart';

class DiaryListBody extends StatelessWidget {
  const DiaryListBody({
    super.key,
    required this.diaries,
    required this.searchQuery,
    required this.selectedTag,
    required this.playingDiaryId,
    required this.snapshot,
    required this.onSearch,
    required this.onTag,
    required this.onRefresh,
    required this.onOpen,
    required this.onPlay,
    this.searchOptions = const DiarySearchOptions(),
    this.selectionMode = false,
    this.selectedIds = const {},
    this.onToggleSelection,
  });

  final Future<List<Diary>> diaries;
  final String searchQuery;
  final String? selectedTag;
  final String? playingDiaryId;
  final PlaybackSnapshot snapshot;
  final ValueChanged<String> onSearch;
  final ValueChanged<String?> onTag;
  final Future<void> Function() onRefresh;
  final Future<void> Function(Diary) onOpen;
  final Future<void> Function(Diary) onPlay;
  final DiarySearchOptions searchOptions;
  final bool selectionMode;
  final Set<String> selectedIds;
  final ValueChanged<String>? onToggleSelection;

  String _stageLabel(Diary diary) {
    if (playingDiaryId != diary.id) return 'v${diary.version}';
    switch (snapshot.stage) {
      case PlaybackStage.buffering:
        return 'Buffering';
      case PlaybackStage.playingFirst:
        return 'Playing 1/2';
      case PlaybackStage.waiting:
        return 'Repeat gap ${snapshot.remainingGap.inSeconds}s';
      case PlaybackStage.playingSecond:
        return 'Playing 2/2';
      case PlaybackStage.paused:
        return 'Paused';
      case PlaybackStage.completed:
        return 'Completed';
      case PlaybackStage.idle:
        return 'Ready';
    }
  }

  @override
  Widget build(BuildContext context) => Column(children: [
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12),
          child: TextField(
            onChanged: onSearch,
            decoration: const InputDecoration(
                prefixIcon: Icon(Icons.search), hintText: '搜索日期、正文或标签'),
          ),
        ),
        Expanded(
          child: FutureBuilder<List<Diary>>(
            future: diaries,
            builder: (context, result) {
              if (result.connectionState == ConnectionState.waiting) {
                return const Center(child: CircularProgressIndicator());
              }
              final items = result.data ?? const <Diary>[];
              if (items.isEmpty) {
                return const Center(child: Text('暂无已缓存的日记'));
              }
              final tags = items.expand((diary) => diary.tags).toSet().toList()
                ..sort();
              final tag = tags.contains(selectedTag) ? selectedTag : null;
              final filtered = filterDiaries(items, searchQuery, tag,
                  options: searchOptions);
              return Column(children: [
                Align(
                  alignment: Alignment.centerLeft,
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 16),
                    child: DropdownButton<String?>(
                      value: tag,
                      items: [
                        const DropdownMenuItem<String?>(
                            value: null, child: Text('全部标签')),
                        ...tags.map((name) => DropdownMenuItem<String?>(
                              value: name,
                              child: Text(name),
                            )),
                      ],
                      onChanged: onTag,
                    ),
                  ),
                ),
                Expanded(
                  child: filtered.isEmpty
                      ? const Center(child: Text('没有匹配的日记'))
                      : RefreshIndicator(
                          onRefresh: onRefresh,
                          child: ListView.separated(
                            padding: const EdgeInsets.all(12),
                            itemCount: filtered.length,
                            separatorBuilder: (_, __) =>
                                const SizedBox(height: 8),
                            itemBuilder: (context, index) {
                              final diary = filtered[index];
                              final active = playingDiaryId == diary.id &&
                                  snapshot.stage != PlaybackStage.completed;
                              final selected = selectedIds.contains(diary.id);
                              return Card(
                                color: selected
                                    ? Theme.of(context)
                                        .colorScheme
                                        .secondaryContainer
                                    : null,
                                child: ListTile(
                                  onTap: selectionMode
                                      ? () => onToggleSelection?.call(diary.id)
                                      : () => onOpen(diary),
                                  onLongPress: onToggleSelection == null
                                      ? null
                                      : () => onToggleSelection!.call(diary.id),
                                  leading: selectionMode
                                      ? Checkbox(
                                          value: selected,
                                          onChanged: (_) =>
                                              onToggleSelection?.call(diary.id),
                                        )
                                      : null,
                                  title: Text(diary.date),
                                  subtitle: Text(
                                    '${_stageLabel(diary)} \u00b7 \u67e5\u770b ${diary.viewCount} \u6b21\n${diary.content}',
                                    maxLines: 4,
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                  trailing: selectionMode
                                      ? null
                                      : IconButton(
                                          tooltip: active ? '??' : '??',
                                          onPressed: () => onPlay(diary),
                                          icon: Icon(active
                                              ? Icons.pause
                                              : Icons.play_arrow),
                                        ),
                                ),
                              );
                            },
                          ),
                        ),
                ),
              ]);
            },
          ),
        ),
      ]);
}
