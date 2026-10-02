import 'dart:io';

import 'package:crypto/crypto.dart';
import 'package:diary_mobile/models/audio_asset.dart';
import 'package:diary_mobile/models/diary.dart';
import 'package:diary_mobile/services/diary_api.dart';
import 'package:diary_mobile/services/local_store.dart';
import 'package:diary_mobile/services/sync_manager.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:path/path.dart' as path;
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

class _VoiceStore extends LocalStore {
  _VoiceStore(super.database, this.directory) : super.withDatabase();
  final String directory;
  @override
  Future<String> audioDirectory() async => directory;
}

class _VoiceApi extends DiaryApi {
  _VoiceApi() : super(baseUrl: '');
  final generated = <String>[];
  bool failDownload = false;
  bool wrongHash = false;
  bool wrongVoice = false;
  final bytes = <int>[1, 2, 3, 4];

  @override
  Future<AudioAsset> generateAudio(String diaryId, {String? voiceId}) async {
    generated.add(voiceId ?? 'default');
    return AudioAsset(
      id: 'asset-${generated.length}',
      diaryId: diaryId,
      voiceId: wrongVoice ? 'wrong-voice' : voiceId ?? 'default',
      contentHash: 'hash',
      fileHash: wrongHash ? 'sha256:wrong' : 'sha256:${sha256.convert(bytes)}',
      durationMs: 100,
      downloadUrl: '',
    );
  }

  @override
  Future<void> downloadAudioToFile(AudioAsset asset, File target) async {
    if (failDownload) throw const DiaryApiException('下载失败', network: true);
    await target.writeAsBytes(bytes);
  }
}

void main() {
  sqfliteFfiInit();
  late Directory directory;
  late _VoiceStore store;
  late _VoiceApi api;
  setUp(() async {
    directory = await Directory.systemTemp.createTemp('voice-sync-');
    final db = await databaseFactoryFfi
        .openDatabase(path.join(directory.path, 'db.sqlite'));
    await LocalStore.createSchema(db, 3);
    store = _VoiceStore(db, directory.path);
    api = _VoiceApi();
  });
  tearDown(() async {
    await store.close();
    api.dispose();
    await directory.delete(recursive: true);
  });
  const diary = Diary(
      id: 'diary',
      date: '2026-09-27',
      content: '正文',
      contentHash: 'hash',
      version: 1,
      tags: [],
      updatedAt: '');

  test('同篇切换语音分别生成，切回命中离线缓存且不改变查看统计', () async {
    await store.saveDiary(diary);
    final sync = SyncManager(api: api, store: store);
    final statuses = <String>[];
    final first =
        await sync.ensureAudio(diary, voiceId: 'one', onStatus: statuses.add);
    final second = await sync.ensureAudio(diary, voiceId: 'two');
    expect(first.localPath, isNot(second.localPath));
    expect(await File(first.localPath!).exists(), isTrue);
    expect(await File(second.localPath!).exists(), isTrue);
    expect((await sync.ensureAudio(diary, voiceId: 'one')).localPath,
        first.localPath);
    expect(api.generated, ['one', 'two']);
    expect(
        statuses, containsAllInOrder(['正在生成音频', '正在下载音频', '正在校验音频', '音频已缓存']));
    expect((await store.getDiary(diary.id))!.viewCount, 0);
    expect(await store.getOutbox(), isEmpty);
    expect(await store.getRandomUsage(), isEmpty);
  });

  test('服务器默认语音不会误命中其他语音包的离线缓存', () async {
    final sync = SyncManager(api: api, store: store);
    await sync.ensureAudio(diary, voiceId: 'other');
    final selected = await sync.ensureAudio(diary);
    expect(selected.voiceId, 'default');
    expect(await store.defaultVoice(api.cacheScope), 'default');
    expect((await sync.ensureAudio(diary)).localPath, selected.localPath);
    expect(api.generated, ['other', 'default']);
  });
  test('某篇音频生成失败后仍可处理随机队列的下一篇', () async {
    final sync = SyncManager(api: api, store: store);
    api.wrongHash = true;
    await expectLater(sync.ensureAudio(diary, voiceId: 'one'),
        throwsA(isA<DiaryApiException>()));
    api.wrongHash = false;
    final next = Diary(
        id: 'next',
        date: diary.date,
        content: '下一篇',
        contentHash: diary.contentHash,
        version: 1,
        tags: const [],
        updatedAt: '');
    final asset = await sync.ensureAudio(next, voiceId: 'one');
    expect(asset.diaryId, 'next');
    expect(await File(asset.localPath!).exists(), isTrue);
    expect(await store.getRandomUsage(), isEmpty);
    expect(await store.getOutbox(), isEmpty);
  });
  test('生成校验与下载失败不会缓存坏资源，下次可重试', () async {
    final sync = SyncManager(api: api, store: store);
    api.wrongVoice = true;
    await expectLater(sync.ensureAudio(diary, voiceId: 'one'),
        throwsA(isA<DiaryApiException>()));
    api.wrongVoice = false;
    api.failDownload = true;
    await expectLater(sync.ensureAudio(diary, voiceId: 'one'),
        throwsA(isA<DiaryApiException>()));
    api.failDownload = false;
    api.wrongHash = true;
    await expectLater(sync.ensureAudio(diary, voiceId: 'one'),
        throwsA(isA<DiaryApiException>()));
    expect(await store.getAudio(diary.id, 'one', diary.contentHash), isNull);
    api.wrongHash = false;
    expect((await sync.ensureAudio(diary, voiceId: 'one')).voiceId, 'one');
    expect(await store.getOutbox(), isEmpty);
  });
}
