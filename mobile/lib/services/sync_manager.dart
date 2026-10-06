import 'dart:convert';
import 'dart:developer' as developer;
import 'dart:io';
import 'dart:math';

import 'package:crypto/crypto.dart';
import 'package:connectivity_plus/connectivity_plus.dart';

import '../conflicts/diary_conflict.dart';
import '../models/audio_asset.dart';
import '../models/audio_preparation_stage.dart';
import '../playback/playback_record.dart';
import '../playback/local_store_playback.dart';
import '../models/diary.dart';
import '../tags/batch_tag_policy.dart';
import '../tags/batch_tag_repository.dart';
import 'diary_api.dart';
import '../transfer/diary_transfer.dart';
import 'local_store.dart';

class SyncManager {
  SyncManager({
    required this.api,
    required this.store,
    Future<List<ConnectivityResult>> Function()? checkConnectivity,
  }) : _checkConnectivity =
            checkConnectivity ?? Connectivity().checkConnectivity;
  final DiaryApi api;
  final LocalStore store;
  final Future<List<ConnectivityResult>> Function() _checkConnectivity;

  Future<List<Diary>> loadLocal() => store.getDiaries();

  String _contentHash(String content) =>
      'sha256:${sha256.convert(utf8.encode(content)).toString()}';

  bool _isNetworkFailure(Object error) =>
      error is DiaryApiException && error.network;

  bool _isConflict(Object error) =>
      error is DiaryApiException && error.conflict;

  Future<Diary> _fetchConflictDiary(String diaryId) async {
    try {
      return await api.fetchDiary(diaryId);
    } on DiaryApiException catch (error) {
      if (error.statusCode != 404) rethrow;
      final trash = await api.fetchTrash();
      return trash.firstWhere((diary) => diary.id == diaryId,
          orElse: () => throw const DiaryApiException('服务器日记不存在'));
    }
  }

  Future<void> _captureConflict(String diaryId, String action) async {
    Diary? remote;
    try {
      remote = await _fetchConflictDiary(diaryId);
    } catch (error, stack) {
      developer.log(
          jsonEncode({
            'request_id': DateTime.now().microsecondsSinceEpoch.toString(),
            'operation': 'fetch_conflict_snapshot_failed',
            'diary_id': diaryId,
          }),
          name: 'diary.sync',
          error: error,
          stackTrace: stack);
    }
    await store.recordConflict(diaryId, action, remote);
  }

  Future<List<DiaryConflict>> getConflicts() => store.getConflicts();
  Future<void> refreshConflict(DiaryConflict conflict) async {
    final remote = await _fetchConflictDiary(conflict.diaryId);
    await store.recordConflict(conflict.diaryId, conflict.action, remote);
  }

  Future<void> resolveConflict(DiaryConflict conflict,
      {required bool keepLocal}) async {
    final remote = await _fetchConflictDiary(conflict.diaryId);
    try {
      await store.resolveConflict(conflict, remote, keepLocal: keepLocal);
    } on StateError {
      await store.recordConflict(conflict.diaryId, conflict.action, remote);
      rethrow;
    }
    developer.log(
        jsonEncode({
          'request_id': DateTime.now().microsecondsSinceEpoch.toString(),
          'operation': 'resolve_diary_conflict',
          'diary_id': conflict.diaryId,
          'keep_local': keepLocal,
        }),
        name: 'diary.sync');
  }

  Future<int> importDiaries(List<DiaryImportEntry> entries) async {
    final now = DateTime.now().toUtc().toIso8601String();
    final diaries = entries
        .map((entry) => Diary(
              id: 'local-${_newViewEventId()}',
              date: entry.date,
              content: entry.content,
              contentHash: _contentHash(entry.content),
              version: 1,
              tags: entry.tags,
              updatedAt: now,
            ))
        .toList(growable: false);
    return store.importDiaries(diaries);
  }

  Future<int> batchTagDiaries(
    Set<String> diaryIds,
    List<String> tags,
    BatchTagMode mode,
  ) async {
    final count = await store.batchUpdateTags(diaryIds, tags, mode);
    developer.log(
        jsonEncode({
          'request_id': DateTime.now().microsecondsSinceEpoch.toString(),
          'operation': 'batch_tag_diaries',
          'mode': mode.name,
          'changed': count,
        }),
        name: 'diary.mobile');
    return count;
  }

  Future<Diary> createDiary({
    required String date,
    required String content,
    required List<String> tags,
  }) async {
    try {
      final diary =
          await api.createDiary(date: date, content: content, tags: tags);
      await store.saveDiary(diary);
      return diary;
    } catch (error) {
      if (!_isNetworkFailure(error)) rethrow;
      final local = Diary(
        id: 'local-${DateTime.now().microsecondsSinceEpoch}',
        date: date,
        content: content,
        contentHash: _contentHash(content),
        version: 1,
        tags: List.unmodifiable(tags),
        updatedAt: DateTime.now().toUtc().toIso8601String(),
      );
      await store.saveDiary(local);
      await store.enqueueMutation(
        entityId: local.id,
        action: 'create',
        baseVersion: null,
        payload: {'date': date, 'content': content, 'tags': tags},
      );
      return local;
    }
  }

  Future<Diary> updateDiary(
    Diary diary, {
    required String content,
    required List<String> tags,
  }) async {
    try {
      final updated =
          await api.updateDiary(diary, content: content, tags: tags);
      await store.saveRemoteDiary(updated);
      return updated;
    } catch (error) {
      if (!_isNetworkFailure(error) && !_isConflict(error)) rethrow;
      final cached = await store.getDiary(diary.id);
      final local = Diary(
        id: diary.id,
        date: diary.date,
        content: content,
        contentHash: _contentHash(content),
        version: diary.version,
        tags: List.unmodifiable(tags),
        updatedAt: DateTime.now().toUtc().toIso8601String(),
        viewCount: cached?.viewCount ?? diary.viewCount,
        lastViewedAt: cached?.lastViewedAt ?? diary.lastViewedAt,
      );
      await store.saveDiary(local);
      await store.enqueueMutation(
        entityId: diary.id,
        action: 'update',
        baseVersion: diary.version,
        payload: {'content': content, 'tags': tags},
      );
      if (_isConflict(error)) await _captureConflict(diary.id, 'update');
      return local;
    }
  }

  String _newViewEventId() {
    final random = Random.secure();
    final bytes = List<int>.generate(16, (_) => random.nextInt(256));
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    final hex =
        bytes.map((byte) => byte.toRadixString(16).padLeft(2, '0')).join();
    return '${hex.substring(0, 8)}-${hex.substring(8, 12)}-'
        '${hex.substring(12, 16)}-${hex.substring(16, 20)}-'
        '${hex.substring(20)}';
  }

  Future<void> recordView(Diary diary) async {
    final eventId = _newViewEventId();
    final viewedAt = DateTime.now().toUtc().toIso8601String();
    final id = await store.recordViewLocally(diary.id, eventId, viewedAt);
    if (diary.id.startsWith('local-')) return;
    try {
      final result =
          await api.recordView(diary, eventId: eventId, viewedAt: viewedAt);
      await store.confirmView(id, diary.id, result);
    } catch (error) {
      if (!_isNetworkFailure(error)) rethrow;
    }
  }

  Future<void> restoreDiary(Diary diary) async {
    final pending = await store.getOutbox();
    if (pending.any((row) =>
        row['entity_id'] == diary.id &&
        row['action'] != 'view' &&
        row['action'] != 'restore')) {
      throw StateError('日记存在其他待同步操作，不能恢复');
    }
    try {
      final restored = await api.restoreDiary(diary);
      await store.saveRemoteDiary(restored);
      for (final row in pending.where((row) =>
          row['entity_id'] == diary.id && row['action'] == 'restore')) {
        await store.acknowledgeMutation(row['id'] as int);
      }
    } catch (error) {
      if (!_isNetworkFailure(error) && !_isConflict(error)) rethrow;
      final cached = await store.getDiary(diary.id);
      await store.saveDiary(
          cached == null ? diary : preserveLocalViews(cached, diary));
      await store.enqueueMutation(
          entityId: diary.id,
          action: 'restore',
          baseVersion: diary.version,
          payload: const {});
      if (_isConflict(error)) await _captureConflict(diary.id, 'restore');
    }
  }

  Future<void> deleteDiary(Diary diary) async {
    final pending = await store.getOutbox();
    if (diary.id.startsWith('local-')) {
      final hasCreate = pending.any((item) =>
          item['entity_id'] == diary.id && item['action'] == 'create');
      if (!hasCreate) {
        throw const DiaryApiException('本地新建任务缺失，已停止删除');
      }
      await store.enqueueMutation(
        entityId: diary.id,
        action: 'delete',
        baseVersion: diary.version,
        payload: const {},
      );
      return;
    }
    var attemptedDelete = false;
    try {
      if (pending.any((item) =>
          item['entity_id'] == diary.id && item['action'] == 'view')) {
        await flushPending();
      }
      final current = await store.getDiary(diary.id) ?? diary;
      attemptedDelete = true;
      await api.deleteDiary(current);
      await store.removeDiary(diary.id);
    } catch (error) {
      if (!_isNetworkFailure(error) &&
          !(attemptedDelete && _isConflict(error))) {
        rethrow;
      }
      final cached = await store.getDiary(diary.id);
      final local = Diary(
        id: diary.id,
        date: diary.date,
        content: diary.content,
        contentHash: diary.contentHash,
        version: diary.version,
        tags: diary.tags,
        updatedAt: diary.updatedAt,
        viewCount: cached?.viewCount ?? diary.viewCount,
        lastViewedAt: cached?.lastViewedAt ?? diary.lastViewedAt,
        deletedAt: DateTime.now().toUtc().toIso8601String(),
      );
      await store.saveDiary(local);
      await store.enqueueMutation(
        entityId: diary.id,
        action: 'delete',
        baseVersion: diary.version,
        payload: const {},
      );
      if (_isConflict(error)) await _captureConflict(diary.id, 'delete');
    }
  }

  Future<PlaybackRecord> savePlaybackRecord({
    required String diaryId,
    required String voiceId,
    required int roundNumber,
    required int positionMs,
    required String status,
    String? deviceId,
  }) async {
    final record = PlaybackRecord(
      id: 'local-playback-${DateTime.now().microsecondsSinceEpoch}',
      deviceId: deviceId ?? await store.getDeviceId(),
      diaryId: diaryId,
      voiceId: voiceId,
      roundNumber: roundNumber.clamp(1, 2).toInt(),
      positionMs: positionMs < 0 ? 0 : positionMs,
      status: status,
      updatedAt: DateTime.now().toUtc().toIso8601String(),
    );
    await store.savePlayback(record);
    return record;
  }

  Future<PlaybackRecord?> localPlayback(String diaryId, String voiceId) =>
      store.getPlayback(diaryId, voiceId);
  Future<PlaybackRecord?> remotePlayback(String diaryId, String voiceId) async {
    final deviceId = await store.getDeviceId();
    final localDevice = await api.fetchPlaybackRecords(
        deviceId: deviceId, diaryId: diaryId, voiceId: voiceId);
    if (localDevice.isNotEmpty) return localDevice.first;
    final others =
        await api.fetchPlaybackRecords(diaryId: diaryId, voiceId: voiceId);
    return others.isEmpty ? null : others.first;
  }

  Future<void> _flushPlayback(Map<String, dynamic> payload, int id) async {
    final saved = await api.savePlayback(PlaybackRecord.fromJson(payload));
    await store.savePlayback(saved, queue: false);
    await store.acknowledgeMutation(id);
  }

  Future<void> _flushOutbox() async {
    while (true) {
      final pending = await store.getOutbox();
      if (pending.isEmpty) return;
      var item = pending.first;
      if (['update', 'delete', 'restore'].contains(item['action']) &&
          await store.hasConflict(item['entity_id'] as String)) {
        final views = pending.where((row) => row['action'] == 'view');
        if (views.isEmpty) {
          throw const DiaryApiException('版本冲突等待人工审核', conflict: true);
        }
        // 查看事件与正文冲突独立，先补交已入队的查看事件。
        item = views.first;
      }
      final id = item['id'] as int;
      final entityId = item['entity_id'] as String;
      final action = item['action'] as String;
      final payload =
          Map<String, dynamic>.from(jsonDecode(item['json'] as String) as Map);
      if (action == 'playback') {
        await _flushPlayback(payload, id);
        continue;
      }
      if (action == 'view') {
        final current = await store.getDiary(entityId);
        if (current == null) {
          throw const DiaryApiException('待同步查看的本地日记不存在，已停止同步');
        }
        if (payload['event_id'] == null || payload['viewed_at'] == null) {
          final eventId = _newViewEventId();
          final viewedAt = DateTime.now().toUtc().toIso8601String();
          await store.ensureViewPayload(id, eventId, viewedAt);
          payload['event_id'] = eventId;
          payload['viewed_at'] = viewedAt;
        }
        final result = await api.recordView(current,
            eventId: payload['event_id'] as String,
            viewedAt: payload['viewed_at'] as String);
        await store.confirmView(id, entityId, result);
        continue;
      } else if (action == 'create') {
        final created = await api.createDiary(
          date: payload['date'] as String,
          content: payload['content'] as String,
          tags:
              List<String>.from(payload['tags'] as List<dynamic>? ?? const []),
        );
        await store.replaceLocalId(entityId, created, id);
        continue;
      } else {
        final current = await store.getDiary(entityId);
        if (current == null) {
          throw const DiaryApiException('本地待同步日记不存在，已停止同步');
        }
        try {
          if (action == 'update') {
            final updated = await api.updateDiary(
              current,
              content: payload['content'] as String,
              tags: List<String>.from(
                  payload['tags'] as List<dynamic>? ?? const []),
            );
            await store.saveRemoteDiary(updated);
          } else if (action == 'restore') {
            final restored = await api.restoreDiary(current);
            await store.saveRemoteDiary(restored);
          } else if (action == 'delete') {
            await api.deleteDiary(current);
            await store.removeDiary(entityId);
          } else {
            throw DiaryApiException('未知的离线操作：$action');
          }
        } on DiaryApiException catch (error) {
          if (error.conflict) await _captureConflict(entityId, action);
          rethrow;
        }
      }
      await store.acknowledgeMutation(id);
    }
  }

  Future<void> flushPending() => _flushOutbox();
  Future<int> pendingCount() async => (await store.getOutbox()).length;
  Future<List<Diary>> refresh() async {
    final connectivity = await _checkConnectivity();
    if (connectivity.contains(ConnectivityResult.none)) {
      return store.getDiaries();
    }
    await flushPending();
    final diaries = await api.fetchDiaries();
    await store.replaceDiaries(diaries);
    final pull = await api.pull(await store.getCursor());
    await store
        .saveCursor((pull['next_cursor'] as int?) ?? await store.getCursor());
    return diaries;
  }

  Future<AudioAsset> ensureAudio(
    Diary diary, {
    String voiceId = '',
    void Function(AudioPreparationStage stage)? onStatus,
  }) async {
    onStatus?.call(AudioPreparationStage.checkingCache);
    final defaultVoice =
        voiceId.isEmpty ? await store.defaultVoice(api.cacheScope) : null;
    final cached = voiceId.isEmpty && defaultVoice == null
        ? null
        : await store.getAudio(
            diary.id, defaultVoice ?? voiceId, diary.contentHash);
    if (cached != null) {
      onStatus?.call(AudioPreparationStage.loadedOfflineCache);
      return cached;
    }
    onStatus?.call(AudioPreparationStage.generating);
    final asset = await api.generateAudio(diary.id,
        voiceId: voiceId.isEmpty ? null : voiceId);
    if (asset.diaryId != diary.id ||
        (voiceId.isNotEmpty && asset.voiceId != voiceId) ||
        (diary.contentHash.isNotEmpty &&
            asset.contentHash != diary.contentHash)) {
      throw const DiaryApiException('音频资源与当前日记或语音包不匹配');
    }
    final directory = await store.audioDirectory();
    // 文件名使用内容寻址，旧语音和旧正文的文件均可保留。
    final key = sha256.convert(utf8.encode(
        jsonEncode([diary.id, asset.voiceId, diary.contentHash, asset.id])));
    final filePath = '$directory/$key.mp3';
    final partialFile = File('$filePath.part');
    onStatus?.call(AudioPreparationStage.downloading);
    await api.downloadAudioToFile(asset, partialFile);
    onStatus?.call(AudioPreparationStage.verifying);
    final actualHash =
        sha256.convert(await partialFile.readAsBytes()).toString();
    final expectedHash = asset.fileHash.replaceFirst('sha256:', '');
    if (expectedHash.isNotEmpty && actualHash != expectedHash) {
      try {
        await partialFile.delete();
      } on FileSystemException {
        // 校验失败的临时文件下次下载会重新覆盖。
      }
      throw const DiaryApiException('音频文件校验失败');
    }
    final file = File(filePath);
    if (await file.exists()) await file.delete();
    await partialFile.rename(filePath);
    final saved = asset.copyWith(localPath: filePath);
    await store.saveAudio(saved, filePath);
    if (voiceId.isEmpty) {
      await store.saveDefaultVoice(api.cacheScope, asset.voiceId);
    }
    onStatus?.call(AudioPreparationStage.cached);
    developer.log(
        jsonEncode({
          'request_id': DateTime.now().microsecondsSinceEpoch.toString(),
          'operation': 'audio_cached',
          'diary_id': diary.id,
          'voice_id': asset.voiceId,
        }),
        name: 'diary.mobile');
    return saved;
  }
}
