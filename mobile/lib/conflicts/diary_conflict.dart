import '../models/diary.dart';

class DiaryConflict {
  const DiaryConflict({
    required this.diaryId,
    required this.local,
    required this.remote,
    required this.action,
  });

  final String diaryId;
  final Diary local;
  final Diary? remote;
  final String action;
}

Diary preserveLocalViews(Diary local, Diary remote) {
  final localTime = DateTime.tryParse(local.lastViewedAt ?? '');
  final remoteTime = DateTime.tryParse(remote.lastViewedAt ?? '');
  return remote.copyWith(
    viewCount:
        local.viewCount > remote.viewCount ? local.viewCount : remote.viewCount,
    lastViewedAt: localTime != null &&
            (remoteTime == null || localTime.isAfter(remoteTime))
        ? local.lastViewedAt
        : remote.lastViewedAt,
  );
}

Diary rebaseLocalDiary(Diary local, Diary remote) => Diary(
      id: local.id,
      date: remote.date,
      content: local.content,
      contentHash: local.contentHash,
      version: remote.version,
      tags: local.tags,
      updatedAt: local.updatedAt,
      viewCount: local.viewCount > remote.viewCount
          ? local.viewCount
          : remote.viewCount,
      lastViewedAt: preserveLocalViews(local, remote).lastViewedAt,
      deletedAt: local.deletedAt,
    );
