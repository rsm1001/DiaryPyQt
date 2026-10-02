import 'package:flutter/material.dart';

import '../models/diary.dart';
import '../search/diary_highlight.dart';
import '../search/diary_search_index.dart';
import '../services/diary_filter.dart';
import '../services/double_playback_service.dart';

class DiaryListBody extends StatefulWidget {
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
    this.onClearFilters,
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
  final VoidCallback? onClearFilters;
  final Future<void> Function() onRefresh;
  final Future<void> Function(Diary) onOpen;
  final Future<void> Function(Diary) onPlay;
  final DiarySearchOptions searchOptions;
  final bool selectionMode;
  final Set<String> selectedIds;
  final ValueChanged<String>? onToggleSelection;

  @override
  State<DiaryListBody> createState() => _DiaryListBodyState();
}

class _DiaryListBodyState extends State<DiaryListBody> {
  late final TextEditingController _searchController;
  List<Diary>? _indexedItems;
  DiarySearchIndex? _index;

  @override
  void initState() {
    super.initState();
    _searchController = TextEditingController(text: widget.searchQuery);
  }

  @override
  void didUpdateWidget(DiaryListBody oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.searchQuery != _searchController.text) {
      _searchController.text = widget.searchQuery;
    }
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  String _stageLabel(Diary diary) {
    if (widget.playingDiaryId != diary.id) return 'v${diary.version}';
    switch (widget.snapshot.stage) {
      case PlaybackStage.buffering:
        return '缓冲中';
      case PlaybackStage.playingFirst:
        return '播放 1/2';
      case PlaybackStage.waiting:
        return '等待 ${widget.snapshot.remainingGap.inSeconds} 秒';
      case PlaybackStage.playingSecond:
        return '播放 2/2';
      case PlaybackStage.paused:
        return '已暂停';
      case PlaybackStage.completed:
        return '已完成';
      case PlaybackStage.idle:
        return '就绪';
    }
  }

  @override
  Widget build(BuildContext context) => Column(children: [
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12),
          child: TextField(
            controller: _searchController,
            onChanged: widget.onSearch,
            decoration: const InputDecoration(
              prefixIcon: Icon(Icons.search),
              hintText: '搜索日期、正文或标签（空格分隔多个关键词）',
            ),
          ),
        ),
        Expanded(
          child: FutureBuilder<List<Diary>>(
            future: widget.diaries,
            builder: (context, result) {
              if (result.connectionState == ConnectionState.waiting) {
                return const Center(child: CircularProgressIndicator());
              }
              final items = result.data ?? const <Diary>[];
              if (items.isEmpty) {
                return const Center(child: Text('暂无已缓存的日记'));
              }
              if (!identical(_indexedItems, items)) {
                _indexedItems = items;
                _index = DiarySearchIndex(items);
              }
              final tags = items.expand((diary) => diary.tags).toSet().toList()
                ..sort();
              final tag =
                  tags.contains(widget.selectedTag) ? widget.selectedTag : null;
              final filtered = _index!.search(widget.searchQuery, tag,
                  options: widget.searchOptions);
              final terms = diarySearchTerms(widget.searchQuery);
              final colors = Theme.of(context).colorScheme;
              final highlight = TextStyle(
                color: colors.onTertiaryContainer,
                backgroundColor: colors.tertiaryContainer,
                fontWeight: FontWeight.bold,
              );
              final activeFilters = widget.searchQuery.trim().isNotEmpty ||
                  widget.selectedTag != null ||
                  widget.searchOptions.isActive;
              return Column(children: [
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  child: Row(children: [
                    DropdownButton<String?>(
                      value: tag,
                      items: [
                        const DropdownMenuItem<String?>(
                            value: null, child: Text('全部标签')),
                        ...tags.map((name) => DropdownMenuItem<String?>(
                              value: name,
                              child: Text(name),
                            )),
                      ],
                      onChanged: widget.onTag,
                    ),
                    if (activeFilters && widget.onClearFilters != null)
                      TextButton.icon(
                        onPressed: widget.onClearFilters,
                        icon: const Icon(Icons.clear_all),
                        label: const Text('清除全部筛选'),
                      ),
                  ]),
                ),
                Expanded(
                  child: filtered.isEmpty
                      ? const Center(child: Text('没有匹配的日记'))
                      : RefreshIndicator(
                          onRefresh: widget.onRefresh,
                          child: ListView.separated(
                            padding: const EdgeInsets.all(12),
                            itemCount: filtered.length,
                            separatorBuilder: (_, __) =>
                                const SizedBox(height: 8),
                            itemBuilder: (context, index) {
                              final diary = filtered[index];
                              final playing =
                                  widget.playingDiaryId == diary.id &&
                                      widget.snapshot.stage !=
                                          PlaybackStage.completed;
                              final selected =
                                  widget.selectedIds.contains(diary.id);
                              final labels = diary.tags.isEmpty
                                  ? ''
                                  : '${diary.tags.map((tag) => '#$tag').join(' ')}\n';
                              final preview =
                                  '${_stageLabel(diary)} · 查看 ${diary.viewCount} 次\n'
                                  '$labels${diary.content}';
                              return Card(
                                color:
                                    selected ? colors.secondaryContainer : null,
                                child: ListTile(
                                  onTap: widget.selectionMode
                                      ? () => widget.onToggleSelection
                                          ?.call(diary.id)
                                      : () => widget.onOpen(diary),
                                  onLongPress: widget.onToggleSelection == null
                                      ? null
                                      : () => widget.onToggleSelection!
                                          .call(diary.id),
                                  leading: widget.selectionMode
                                      ? Checkbox(
                                          value: selected,
                                          onChanged: (_) => widget
                                              .onToggleSelection
                                              ?.call(diary.id),
                                        )
                                      : null,
                                  title: Text.rich(TextSpan(
                                    children: diaryHighlightSpans(
                                        diary.date, terms, highlight),
                                  )),
                                  subtitle: Text.rich(
                                    TextSpan(
                                        children: diaryHighlightSpans(
                                            preview, terms, highlight)),
                                    maxLines: 4,
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                  trailing: widget.selectionMode
                                      ? null
                                      : IconButton(
                                          tooltip: playing ? '暂停朗读' : '播放朗读',
                                          onPressed: () => widget.onPlay(diary),
                                          icon: Icon(playing
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
