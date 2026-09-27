import 'dart:convert';
import 'dart:io';

import 'package:crypto/crypto.dart';
import 'package:connectivity_plus/connectivity_plus.dart';

import '../models/audio_asset.dart';
import '../models/diary.dart';
import 'diary_api.dart';
import 'local_store.dart';

class SyncManager {
  SyncManager({required this.api, required this.store});
  final DiaryApi api;
  final LocalStore store;

  Future<List<Diary>> loadLocal() => store.getDiaries();

  String _contentHash(String content) =>
      'sha256:${sha256.convert(utf8.encode(content)).toString()}';

  bool _isNetworkFailure(Object error) =>
      error is DiaryApiException && error.network;

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
      await store.saveDiary(updated);
      return updated;
    } catch (error) {
      if (!_isNetworkFailure(error)) rethrow;
      final local = Diary(
        id: diary.id,
        date: diary.date,
        content: content,
        contentHash: _contentHash(content),
        version: diary.version,
        tags: List.unmodifiable(tags),
        updatedAt: DateTime.now().toUtc().toIso8601String(),
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

  Future<void> recordView(Diary diary) async {
    try {
      final result = await api.recordView(diary);
      await store.saveDiary(diary.copyWith(
          viewCount: result.viewCount, lastViewedAt: result.viewedAt));
    } catch (error) {
      if (!_isNetworkFailure(error)) rethrow;
      final local = diary.copyWith(
          viewCount: diary.viewCount + 1,
          lastViewedAt: DateTime.now().toUtc().toIso8601String());
      await store.saveDiary(local);
      await store.enqueueView(diary.id, diary.version);
    }
  }

  Future<void> deleteDiary(Diary diary) async {
    try {
      await api.deleteDiary(diary);
      await store.removeDiary(diary.id);
    } catch (error) {
      if (!_isNetworkFailure(error)) rethrow;
      final local = Diary(
        id: diary.id,
        date: diary.date,
        content: diary.content,
        contentHash: diary.contentHash,
        version: diary.version,
        tags: diary.tags,
        updatedAt: diary.updatedAt,
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
    for (final item in await store.getOutbox()) {
      final id = item['id'] as int;
      final entityId = item['entity_id'] as String;
      final action = item['action'] as String;
      final payload =
          Map<String, dynamic>.from(jsonDecode(item['json'] as String) as Map);
      if (action == 'view') {
        final current = await store.getDiary(entityId);
        if (current != null) {
          final result = await api.recordView(current);
          await store.saveDiary(current.copyWith(
              viewCount: result.viewCount, lastViewedAt: result.viewedAt));
        }
      } else if (action == 'create') {
        final created = await api.createDiary(
          date: payload['date'] as String,
          content: payload['content'] as String,
          tags:
              List<String>.from(payload['tags'] as List<dynamic>? ?? const []),
        );
        await store.removeDiary(entityId);
        await store.saveDiary(created);
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
          await store.saveDiary(updated);
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

  Future<List<Diary>> refresh() async {
    final connectivity = await Connectivity().checkConnectivity();
    if (connectivity.contains(ConnectivityResult.none)) {
      return store.getDiaries();
    }
    await _flushOutbox();
    final diaries = await api.fetchDiaries();
    await store.replaceDiaries(diaries);
    final pull = await api.pull(await store.getCursor());
    await store
        .saveCursor((pull['next_cursor'] as int?) ?? await store.getCursor());
    return diaries;
  }

  Future<AudioAsset> ensureAudio(Diary diary, {String voiceId = ''}) async {
    final cached = await store.getAudio(diary.id, voiceId, diary.contentHash);
    if (cached != null) return cached;
    final asset = await api.generateAudio(diary.id,
        voiceId: voiceId.isEmpty ? null : voiceId);
    final bytes = await api.downloadAudio(asset);
    final actualHash = sha256.convert(bytes).toString();
    if (asset.fileHash.isNotEmpty && !asset.fileHash.contains(actualHash)) {
      throw const DiaryApiException('Audio hash validation failed');
    }
    final directory = await store.audioDirectory();
    final filePath =
        '$directory/${diary.id}_${asset.voiceId}_${diary.contentHash.replaceAll(RegExp(r'[^a-zA-Z0-9_-]'), '_')}.mp3';
    await File(filePath).writeAsBytes(bytes, flush: true);
    final saved = asset.copyWith(localPath: filePath);
    await store.saveAudio(saved, filePath);
    return saved;
  }
}
