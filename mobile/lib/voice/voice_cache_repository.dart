import 'dart:convert';
import 'dart:io';

import 'package:crypto/crypto.dart';
import 'package:sqflite/sqflite.dart';

import '../models/audio_asset.dart';

class VoiceCacheRepository {
  const VoiceCacheRepository(this.db);
  final Database db;

  static Future<void> createSchema(DatabaseExecutor executor) async {
    await executor.execute('CREATE TABLE audio_cache ('
        'diary_id TEXT NOT NULL, voice_id TEXT NOT NULL, '
        'content_hash TEXT NOT NULL, file_hash TEXT NOT NULL, '
        'duration_ms INTEGER NOT NULL, file_path TEXT NOT NULL, '
        'json TEXT NOT NULL, PRIMARY KEY (diary_id, voice_id, content_hash))');
  }

  static Future<void> upgradeSchema(Database db) async {
    final existing = await db.query('sqlite_master',
        columns: ['name'],
        where: 'type = ? AND name = ?',
        whereArgs: ['table', 'audio_cache']);
    if (existing.isEmpty) {
      await createSchema(db);
      return;
    }
    await db.execute('ALTER TABLE audio_cache RENAME TO audio_cache_old');
    await createSchema(db);
    await db.execute('INSERT INTO audio_cache '
        '(diary_id, voice_id, content_hash, file_hash, duration_ms, file_path, json) '
        'SELECT diary_id, voice_id, content_hash, file_hash, duration_ms, file_path, json '
        'FROM audio_cache_old');
    await db.execute('DROP TABLE audio_cache_old');
  }

  Future<AudioAsset?> get(
      String diaryId, String voiceId, String contentHash) async {
    final rows = await db.query('audio_cache',
        where: voiceId.isEmpty
            ? 'diary_id = ? AND content_hash = ?'
            : 'diary_id = ? AND voice_id = ? AND content_hash = ?',
        whereArgs: voiceId.isEmpty
            ? [diaryId, contentHash]
            : [diaryId, voiceId, contentHash],
        orderBy: 'rowid DESC',
        limit: 1);
    if (rows.isEmpty) return null;
    final row = rows.first;
    final filePath = row['file_path']! as String;
    final file = File(filePath);
    if (!await _isValidFile(row, file)) {
      await _removeInvalidRow(row);
      return null;
    }
    return AudioAsset.fromJson(
            jsonDecode(row['json'] as String) as Map<String, dynamic>, '')
        .copyWith(localPath: filePath);
  }

  Future<bool> _isValidFile(Map<String, Object?> row, File file) async {
    if (!await file.exists() || await file.length() == 0) return false;
    final expected = (row['file_hash'] as String?) ?? '';
    if (!expected.startsWith('sha256:')) return true;
    final actual = sha256.convert(await file.readAsBytes()).toString();
    return actual == expected.substring('sha256:'.length);
  }

  Future<void> _removeInvalidRow(Map<String, Object?> row) async {
    await db.delete(
      'audio_cache',
      where: 'diary_id = ? AND voice_id = ? AND content_hash = ?',
      whereArgs: [row['diary_id'], row['voice_id'], row['content_hash']],
    );
    final file = File(row['file_path']! as String);
    try {
      if (await file.exists()) await file.delete();
    } on FileSystemException {
      // ??????????????????????
    }
  }

  Future<void> save(AudioAsset asset, String filePath) async {
    await db.insert(
        'audio_cache',
        {
          'diary_id': asset.diaryId,
          'voice_id': asset.voiceId,
          'content_hash': asset.contentHash,
          'file_hash': asset.fileHash,
          'duration_ms': asset.durationMs,
          'file_path': filePath,
          'json': jsonEncode({
            'id': asset.id,
            'diary_id': asset.diaryId,
            'voice_id': asset.voiceId,
            'content_hash': asset.contentHash,
            'file_hash': asset.fileHash,
            'duration_ms': asset.durationMs,
            'download_url': asset.downloadUrl,
          }),
        },
        conflictAlgorithm: ConflictAlgorithm.replace);
  }

  Future<String?> defaultVoice(String serverUrl) async {
    final rows = await db.query('sync_state',
        columns: ['value'],
        where: 'key = ?',
        whereArgs: ['default_voice_id:$serverUrl'],
        limit: 1);
    return rows.isEmpty ? null : rows.single['value'] as String;
  }

  Future<void> saveDefaultVoice(String serverUrl, String voiceId) async {
    await db.insert(
        'sync_state', {'key': 'default_voice_id:$serverUrl', 'value': voiceId},
        conflictAlgorithm: ConflictAlgorithm.replace);
  }

  Future<String?> selectedVoice(String serverUrl) async {
    final rows = await db.query('sync_state',
        columns: ['value'],
        where: 'key = ?',
        whereArgs: ['voice_id:$serverUrl'],
        limit: 1);
    return rows.isEmpty ? null : rows.single['value'] as String;
  }

  Future<void> saveSelectedVoice(String serverUrl, String voiceId) async {
    await db.insert(
        'sync_state', {'key': 'voice_id:$serverUrl', 'value': voiceId},
        conflictAlgorithm: ConflictAlgorithm.replace);
  }
}
