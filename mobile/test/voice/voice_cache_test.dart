import 'dart:io';

import 'package:diary_mobile/models/audio_asset.dart';
import 'package:diary_mobile/services/local_store.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:path/path.dart' as path;
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

void main() {
  sqfliteFfiInit();
  late Directory root;
  late Database db;
  late LocalStore store;
  setUp(() async {
    root = await Directory.systemTemp.createTemp('voice-cache-');
    db =
        await databaseFactoryFfi.openDatabase(path.join(root.path, 'diary.db'));
    await LocalStore.createSchema(db, 3);
    store = LocalStore.withDatabase(db);
  });
  tearDown(() async {
    await store.close();
    await root.delete(recursive: true);
  });

  AudioAsset asset(String voice, String content, String file) => AudioAsset(
        id: '$voice-$content',
        diaryId: 'diary',
        voiceId: voice,
        contentHash: content,
        fileHash: '',
        durationMs: 100,
        downloadUrl: 'https://example.invalid/audio/$file',
      );

  test('三维缓存隔离，切换语音和正文不覆盖原有文件与默认配置', () async {
    final first = File(path.join(root.path, 'first.mp3'))
      ..writeAsBytesSync([1]);
    final second = File(path.join(root.path, 'second.mp3'))
      ..writeAsBytesSync([2]);
    final third = File(path.join(root.path, 'third.mp3'))
      ..writeAsBytesSync([3]);
    await store.saveAudio(asset('voice-a', 'hash-old', 'first'), first.path);
    await store.saveAudio(asset('voice-b', 'hash-old', 'second'), second.path);
    await store.saveAudio(asset('voice-a', 'hash-new', 'third'), third.path);
    expect((await store.getAudio('diary', 'voice-a', 'hash-old'))!.localPath,
        first.path);
    expect((await store.getAudio('diary', 'voice-b', 'hash-old'))!.localPath,
        second.path);
    expect((await store.getAudio('diary', 'voice-a', 'hash-new'))!.localPath,
        third.path);
    expect(await store.getAudio('diary', 'voice-b', 'hash-new'), isNull);
    await store.saveSelectedVoice('https://one.invalid', 'voice-a');
    await store.saveSelectedVoice('https://two.invalid', 'voice-b');
    expect(await store.selectedVoice('https://one.invalid'), 'voice-a');
    expect(await store.selectedVoice('https://two.invalid'), 'voice-b');
    await store.saveDefaultVoice('https://one.invalid', 'voice-a');
    expect(await store.defaultVoice('https://one.invalid'), 'voice-a');
    expect(await store.defaultVoice('https://two.invalid'), isNull);
    expect(await first.exists(), isTrue);
    expect(await second.exists(), isTrue);
  });

  test('旧版缓存迁移保留音频路径，升级后支持多个正文版本', () async {
    final oldPath = path.join(root.path, 'old.db');
    final oldFile = File(path.join(root.path, 'old.mp3'))
      ..writeAsBytesSync([4]);
    final oldAsset = asset('voice-a', 'hash-old', 'old');
    final oldDb = await databaseFactoryFfi.openDatabase(oldPath,
        options: OpenDatabaseOptions(
            version: 2,
            onCreate: (db, version) async {
              await db.execute('CREATE TABLE audio_cache ('
                  'diary_id TEXT NOT NULL, voice_id TEXT NOT NULL, '
                  'content_hash TEXT NOT NULL, file_hash TEXT NOT NULL, '
                  'duration_ms INTEGER NOT NULL, file_path TEXT NOT NULL, '
                  'json TEXT NOT NULL, PRIMARY KEY (diary_id, voice_id))');
              await db.execute(
                  'CREATE TABLE sync_state (key TEXT PRIMARY KEY, value TEXT NOT NULL)');
            }));
    await LocalStore.withDatabase(oldDb).saveAudio(oldAsset, oldFile.path);
    await oldDb.close();
    final upgraded = await databaseFactoryFfi.openDatabase(oldPath,
        options: OpenDatabaseOptions(
            version: 3, onUpgrade: LocalStore.upgradeSchema));
    final upgradedStore = LocalStore.withDatabase(upgraded);
    expect(
        (await upgradedStore.getAudio('diary', 'voice-a', 'hash-old'))!
            .localPath,
        oldFile.path);
    final newFile = File(path.join(root.path, 'new.mp3'))
      ..writeAsBytesSync([5]);
    await upgradedStore.saveAudio(
        asset('voice-a', 'hash-new', 'new'), newFile.path);
    expect(
        (await upgradedStore.getAudio('diary', 'voice-a', 'hash-old'))!
            .localPath,
        oldFile.path);
    expect(await oldFile.exists(), isTrue);
    await upgradedStore.close();
  });
}
