import 'package:flutter/material.dart';

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

  String _randomStageLabel() {
    switch (snapshot.stage) {
      case PlaybackStage.waiting:
        return '\u4e24\u904d\u4e4b\u95f4\u7b49\u5f85\u4e2d';
      case PlaybackStage.buffering:
        return '\u97f3\u9891\u52a0\u8f7d\u4e2d';
      case PlaybackStage.playingFirst:
        return '\u7b2c 1 \u904d\u64ad\u653e\u4e2d';
      case PlaybackStage.playingSecond:
        return '\u7b2c 2 \u904d\u64ad\u653e\u4e2d';
      case PlaybackStage.paused:
        return '\u5df2\u6682\u505c';
      case PlaybackStage.completed:
        return '\u5df2\u5b8c\u6210';
      case PlaybackStage.idle:
        return '\u51c6\u5907\u64ad\u653e';
    }
  }

  @override
  Widget build(BuildContext context) => Column(children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(12, 8, 12, 4),
          child: SizedBox(
            width: double.infinity,
            child: active
                ? OutlinedButton.icon(
                    onPressed: onStop,
                    icon: const Icon(Icons.stop_circle_outlined),
                    label: const Text(
                        '\u505c\u6b62\u968f\u673a\u8fde\u7eed\u64ad\u653e'),
                  )
                : FilledButton.icon(
                    onPressed: onStart,
                    icon: const Icon(Icons.shuffle),
                    label: const Text(
                        '\u5f00\u59cb\u968f\u673a\u8fde\u7eed\u64ad\u653e'),
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
                  child: Column(
                    children: [
                      ListTile(
                        dense: true,
                        contentPadding: EdgeInsets.zero,
                        leading: const Icon(Icons.shuffle),
                        title: Text(current == null
                            ? '\u6b63\u5728\u9009\u62e9\u4e0b\u4e00\u7bc7\u968f\u673a\u65e5\u8bb0'
                            : '\u5f53\u524d\uff1a${current!.date} \u00b7 \u67e5\u770b ${current!.viewCount} \u6b21'),
                        subtitle: current == null
                            ? Text(preparing
                                ? '\u6b63\u5728\u51c6\u5907\u97f3\u9891\uff0c\u8bf7\u7a0d\u5019'
                                : '\u968f\u673a\u5019\u9009\u6c60\u51c6\u5907\u4e2d')
                            : Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    current!.content,
                                    maxLines: 2,
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                  Text(
                                    preparing
                                        ? '\u6b63\u5728\u51c6\u5907\u4e0b\u4e00\u7bc7\u97f3\u9891'
                                        : '${_randomStageLabel()} \u00b7 \u5019\u9009\u6c60 $candidateCount \u7bc7\uff0c\u5faa\u73af\u64ad\u653e',
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
                    ],
                  ),
                ),
              ),
            ),
          ),
      ]);
}
