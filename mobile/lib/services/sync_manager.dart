import 'dart:convert';
import 'dart:developer' as developer;
import 'dart:io';
import 'dart:math';

import 'package:crypto/crypto.dart';
import 'package:connectivity_plus/connectivity_plus.dart';

import '../models/audio_asset.dart';
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
      if (!_isNetworkFailure(error)) rethrow;
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
    try {
      if (pending.any((item) =>
          item['entity_id'] == diary.id && item['action'] == 'view')) {
        await flushPending();
      }
      final current = await store.getDiary(diary.id) ?? diary;
      await api.deleteDiary(current);
      await store.removeDiary(diary.id);
    } catch (error) {
      if (!_isNetworkFailure(error)) rethrow;
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
    }
  }

  Future<void> _flushOutbox() async {
    while (true) {
      final pending = await store.getOutbox();
      if (pending.isEmpty) return;
      final item = pending.first;
      final id = item['id'] as int;
      final entityId = item['entity_id'] as String;
      final action = item['action'] as String;
      final payload =
          Map<String, dynamic>.from(jsonDecode(item['json'] as String) as Map);
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
        if (action == 'update') {
          final updated = await api.updateDiary(
            current,
            content: payload['content'] as String,
            tags: List<String>.from(
                payload['tags'] as List<dynamic>? ?? const []),
          );
          await store.saveRemoteDiary(updated);
        } else if (action == 'delete') {
          await api.deleteDiary(current);
          await store.removeDiary(entityId);
        } else {
          throw DiaryApiException('未知的离线操作：$action');
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
    void Function(String status)? onStatus,
  }) async {
    final defaultVoice =
        voiceId.isEmpty ? await store.defaultVoice(api.cacheScope) : null;
    final cached = voiceId.isEmpty && defaultVoice == null
        ? null
        : await store.getAudio(
            diary.id, defaultVoice ?? voiceId, diary.contentHash);
    if (cached != null) {
      onStatus?.call('已从离线缓存读取音频');
      return cached;
    }
    onStatus?.call('正在生成音频');
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
    onStatus?.call('正在下载音频');
    await api.downloadAudioToFile(asset, partialFile);
    onStatus?.call('正在校验音频');
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
    onStatus?.call('音频已缓存');
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
