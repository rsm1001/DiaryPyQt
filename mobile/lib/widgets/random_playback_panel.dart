import 'package:flutter/material.dart';

import '../localization/app_strings.dart';
import '../models/diary.dart';
import '../services/double_playback_service.dart';

class RandomPlaybackPanel extends StatelessWidget {
  const RandomPlaybackPanel({
    super.key,
    required this.active,
    required this.current,
    int? candidateCount,
    @Deprecated('Use candidateCount; this value is not a playback limit.')
    int? remaining,
    required this.snapshot,
    required this.onStart,
    required this.onStop,
    this.preparing = false,
  }) : candidateCount = candidateCount ?? remaining ?? 0;

  final bool active;
  final Diary? current;
  final int candidateCount;
  final PlaybackSnapshot snapshot;
  final Future<void> Function() onStart;
  final Future<void> Function() onStop;
  final bool preparing;

  String _randomStageLabel(AppStrings strings) {
    switch (snapshot.stage) {
      case PlaybackStage.waiting:
        return strings.waitingBetweenRounds;
      case PlaybackStage.buffering:
        return strings.audioLoading;
      case PlaybackStage.playingFirst:
        return strings.playingFirstRound;
      case PlaybackStage.playingSecond:
        return strings.playingSecondRound;
      case PlaybackStage.paused:
        return strings.playbackPaused;
      case PlaybackStage.completed:
        return strings.playbackCompleted;
      case PlaybackStage.idle:
        return strings.playbackReady;
    }
  }

  @override
  Widget build(BuildContext context) {
    final strings = AppStrings.of(context);
    return Column(children: [
      Padding(
        padding: const EdgeInsets.fromLTRB(12, 8, 12, 4),
        child: SizedBox(
          width: double.infinity,
          child: active
              ? OutlinedButton.icon(
                  onPressed: onStop,
                  icon: const Icon(Icons.stop_circle_outlined),
                  label: Text(strings.stopRandomPlayback),
                )
              : FilledButton.icon(
                  onPressed: onStart,
                  icon: const Icon(Icons.shuffle),
                  label: Text(strings.startRandomPlayback),
                ),
        ),
      ),
      if (active)
        Padding(
          padding: const EdgeInsets.fromLTRB(12, 4, 12, 4),
          child: Card(
            clipBehavior: Clip.hardEdge,
            color: Theme.of(context).colorScheme.primaryContainer,
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxHeight: 150),
              child: Padding(
                padding: const EdgeInsets.all(8),
                child: Column(children: [
                  ListTile(
                    dense: true,
                    contentPadding: EdgeInsets.zero,
                    leading: const Icon(Icons.shuffle),
                    title: Text(current == null
                        ? strings.selectingRandomDiary
                        : strings.currentDiary(
                            current!.date, current!.viewCount)),
                    subtitle: current == null
                        ? Text(preparing
                            ? strings.preparingAudio
                            : strings.preparingPool)
                        : Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(current!.content,
                                  maxLines: 2, overflow: TextOverflow.ellipsis),
                              Text(
                                preparing
                                    ? strings.preparingNextAudio
                                    : strings.playbackProgress(
                                        _randomStageLabel(strings),
                                        candidateCount),
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                              ),
                            ],
                          ),
                    isThreeLine: true,
                  ),
                  if (snapshot.stage == PlaybackStage.buffering)
                    const LinearProgressIndicator()
                  else if (snapshot.duration > Duration.zero)
                    LinearProgressIndicator(
                      value: (snapshot.position.inMilliseconds /
                              snapshot.duration.inMilliseconds)
                          .clamp(0.0, 1.0),
                    ),
                  if (snapshot.duration > Duration.zero)
                    Align(
                      alignment: Alignment.centerRight,
                      child: Text(
                        '${snapshot.position.inSeconds}s / ${snapshot.duration.inSeconds}s',
                        style: Theme.of(context).textTheme.labelSmall,
                      ),
                    ),
                ]),
              ),
            ),
          ),
        ),
    ]);
  }
}
