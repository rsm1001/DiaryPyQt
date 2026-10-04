import 'package:flutter/material.dart';

import '../localization/app_strings.dart';
import 'playback_record.dart';

Future<bool?> showPlaybackResumeDialog(
    BuildContext context, PlaybackRecord record) {
  final strings = AppStrings.of(context);
  return showDialog<bool>(
    context: context,
    builder: (dialogContext) => AlertDialog(
      title: Text(strings.resumePlaybackTitle),
      content: Text(strings.resumePlaybackMessage(
        record.roundNumber,
        record.positionMs ~/ 1000,
        record.status,
      )),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(dialogContext, false),
          child: Text(strings.playFromBeginning),
        ),
        FilledButton(
          onPressed: () => Navigator.pop(dialogContext, true),
          child: Text(strings.continuePlayback),
        ),
      ],
    ),
  );
}
