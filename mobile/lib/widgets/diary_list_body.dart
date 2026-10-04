import 'package:flutter/material.dart';

import '../localization/app_strings.dart';
import '../models/app_preferences.dart';
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
    this.preferences = AppPreferences.defaults,
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
  final AppPreferences preferences;
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

  String _stageLabel(Diary diary, AppStrings strings) {
    if (widget.playingDiaryId != diary.id) {
      return strings.version(diary.version);
    }
    switch (widget.snapshot.stage) {
      case PlaybackStage.buffering:
        return strings.buffering;
      case PlaybackStage.playingFirst:
        return strings.playingFirst;
      case PlaybackStage.waiting:
        return '等待 ${widget.snapshot.remainingGap.inSeconds} 秒';
      case PlaybackStage.playingSecond:
        return strings.playingSecond;
      case PlaybackStage.paused:
        return strings.paused;
      case PlaybackStage.completed:
        return strings.completed;
      case PlaybackStage.idle:
        return strings.ready;
    }
  }

  @override
  Widget build(BuildContext context) {
    final strings = AppStrings.of(context);
    return Column(children: [
      Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12),
        child: TextField(
          controller: _searchController,
          onChanged: widget.onSearch,
          decoration: InputDecoration(
            prefixIcon: Icon(Icons.search),
            hintText: strings.searchHint,
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
              return Center(child: Text(strings.noCachedDiaries));
            }
            if (!identical(_indexedItems, items)) {
              _indexedItems = items;
              _index = DiarySearchIndex(items);
            }
            final tags = items.expand((diary) => diary.tags).toSet().toList()
              ..sort();
            final tag =
                tags.contains(widget.selectedTag) ? widget.selectedTag : null;
            final filtered = [
              ..._index!.search(widget.searchQuery, tag,
                  options: widget.searchOptions)
            ]..sort(widget.preferences.compare);
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
                      label: Text(strings.clearFilters),
                    ),
                ]),
              ),
              Expanded(
                child: filtered.isEmpty
                    ? Center(child: Text(strings.noMatchingDiaries))
                    : RefreshIndicator(
                        onRefresh: widget.onRefresh,
                        child: ListView.separated(
                          padding: const EdgeInsets.all(12),
                          itemCount: filtered.length,
                          separatorBuilder: (_, __) =>
                              const SizedBox(height: 8),
                          itemBuilder: (context, index) {
                            final diary = filtered[index];
                            final playing = widget.playingDiaryId == diary.id &&
                                widget.snapshot.stage !=
                                    PlaybackStage.completed;
                            final selected =
                                widget.selectedIds.contains(diary.id);
                            final previewParts = <String>[];
                            if (widget.preferences.showViews) {
                              previewParts.add(
                                  '${_stageLabel(diary, strings)} ? ${strings.viewed(diary.viewCount)}');
                            }
                            if (widget.preferences.showTags &&
                                diary.tags.isNotEmpty) {
                              previewParts.add(
                                  diary.tags.map((tag) => '#$tag').join(' '));
                            }
                            if (widget.preferences.showPreview) {
                              previewParts.add(diary.content);
                            }
                            final preview = previewParts.isEmpty
                                ? strings.hiddenFields
                                : previewParts.join('\n');
                            return Card(
                              color:
                                  selected ? colors.secondaryContainer : null,
                              child: ListTile(
                                onTap: widget.selectionMode
                                    ? () =>
                                        widget.onToggleSelection?.call(diary.id)
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
                                        tooltip: playing
                                            ? strings.pausePlayback
                                            : strings.playPlayback,
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
}
