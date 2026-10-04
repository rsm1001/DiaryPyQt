import 'dart:convert';

import 'package:crypto/crypto.dart';
import 'package:sqflite/sqflite.dart';

class LocalBackup {
  const LocalBackup({required this.payload, required this.checksum});

  static const currentVersion = 2;
  final Map<String, dynamic> payload;
  final String checksum;

  String encode() => jsonEncode({
        'backup_type': 'diary_mobile_local',
        'backup_version': currentVersion,
        'created_at': payload['created_at'],
        'server_scope': payload['server_scope'],
        'data': payload['data'],
        'checksum': checksum,
      });

  static LocalBackup parse(String source) {
    if (utf8.encode(source).length > 5 * 1024 * 1024) {
      throw const FormatException('备份文件过大');
    }
    dynamic decoded;
    try {
      decoded = jsonDecode(source);
    } on FormatException {
      throw const FormatException('备份文件无效');
    }
    if (decoded is! Map<String, dynamic> ||
        decoded['backup_type'] != 'diary_mobile_local' ||
        decoded['backup_version'] != currentVersion ||
        decoded['data'] is! Map<String, dynamic> ||
        decoded['checksum'] is! String ||
        decoded['server_scope'] is! String ||
        !RegExp(r'^[0-9a-f]{64}$')
            .hasMatch(decoded['server_scope'] as String) ||
        decoded['created_at'] is! String) {
      throw const FormatException('本地备份格式或版本不受支持');
    }
    final payload = <String, dynamic>{
      'backup_version': decoded['backup_version'],
      'created_at': decoded['created_at'],
      'server_scope': decoded['server_scope'],
      'data': decoded['data'],
    };
    final expected = _checksum(payload);
    if (expected != decoded['checksum']) {
      throw const FormatException('本地备份校验失败，文件可能已损坏');
    }
    _validateData(decoded['data'] as Map<String, dynamic>);
    return LocalBackup(payload: payload, checksum: expected);
  }

  static String buildChecksum(Map<String, dynamic> payload) =>
      _checksum(payload);

  static void _validateData(Map<String, dynamic> data) {
    const tables = <String, Set<String>>{
      'diaries': {'id', 'json', 'version', 'content_hash'},
      'outbox': {'entity_id', 'action', 'base_version', 'json'},
      'conflicts': {'diary_id', 'action', 'remote_json'},
      'playback_records': {
        'id',
        'diary_id',
        'voice_id',
        'round_number',
        'position_ms',
        'status',
        'updated_at'
      },
      'device_view_events': {'event_id', 'viewed_at_ms', 'synced'},
      'settings': {'key', 'value'},
    };
    if (data.keys.toSet().difference(tables.keys.toSet()).isNotEmpty) {
      throw const FormatException('备份结构无效');
    }
    for (final entry in tables.entries) {
      final rows = data[entry.key];
      if (rows is! List) throw FormatException('备份缺少数据表：');
      for (final raw in rows) {
        if (raw is! Map ||
            !raw.keys.toSet().containsAll(entry.value) ||
            raw.keys.any((key) =>
                key is! String ||
                (!entry.value.contains(key) &&
                    !(entry.key == 'outbox' && key == 'id')))) {
          throw const FormatException('备份数据字段无效');
        }
        if (entry.key == 'diaries') {
          if (raw['id'] is! String ||
              raw['json'] is! String ||
              raw['version'] is! int ||
              raw['content_hash'] is! String) {
            throw const FormatException('备份日记字段无效');
          }
          try {
            final diary = jsonDecode(raw['json'] as String);
            if (diary is! Map || diary['id'] != raw['id']) {
              throw const FormatException('备份日记编号不一致');
            }
          } on FormatException {
            throw const FormatException('备份日记数据无效');
          }
        }
        if (entry.key == 'settings' &&
            (raw['key'] != 'random_usage' || raw['value'] is! String)) {
          throw const FormatException('备份包含不安全的设置');
        }
        if (entry.key == 'outbox') {
          if (raw['entity_id'] is! String ||
              raw['json'] is! String ||
              !{'create', 'update', 'delete', 'view', 'restore', 'playback'}
                  .contains(raw['action'])) {
            throw const FormatException('备份待同步任务无效');
          }
          try {
            if (jsonDecode(raw['json'] as String) is! Map) {
              throw const FormatException('备份待同步任务无效');
            }
          } on FormatException {
            throw const FormatException('备份待同步任务无效');
          }
        }
      }
    }
  }

  static String _checksum(Map<String, dynamic> payload) =>
      sha256.convert(utf8.encode(jsonEncode(_canonical(payload)))).toString();

  static dynamic _canonical(dynamic value) {
    if (value is Map) {
      final keys = value.keys.map((key) => key.toString()).toList()..sort();
      return {for (final key in keys) key: _canonical(value[key])};
    }
    if (value is List) return value.map(_canonical).toList(growable: false);
    return value;
  }
}

class LocalBackupRepository {
  const LocalBackupRepository(this.db);
  final Database db;

  Future<LocalBackup> exportBackup() async {
    return db.transaction((transaction) async {
      final scope = await _serverScope(transaction);
      final playbackRows = await transaction.query('playback_records');
      final outboxRows = await transaction.query('outbox');
      final data = <String, dynamic>{
        'diaries': await transaction.query('diaries'),
        'outbox': outboxRows.map((raw) {
          final row = Map<String, dynamic>.from(raw);
          if (row['action'] == 'playback') {
            final payload =
                Map<String, dynamic>.from(jsonDecode(row['json'] as String));
            payload.remove('device_id');
            row['json'] = jsonEncode(payload);
          }
          return row;
        }).toList(),
        'conflicts': await transaction.query('diary_conflicts'),
        'playback_records': playbackRows
            .map((raw) => Map<String, dynamic>.from(raw)..remove('device_id'))
            .toList(),
        'device_view_events': await transaction.query('device_view_events'),
        'settings': await transaction
            .query('sync_state', where: 'key = ?', whereArgs: ['random_usage']),
      };
      final payload = <String, dynamic>{
        'backup_version': LocalBackup.currentVersion,
        'created_at': DateTime.now().toUtc().toIso8601String(),
        'server_scope': scope,
        'data': data,
      };
      final result = LocalBackup(
          payload: payload, checksum: LocalBackup.buildChecksum(payload));
      if (utf8.encode(result.encode()).length > 5 * 1024 * 1024) {
        throw const FormatException('本地备份超过 5 MB，未保存文件');
      }
      return result;
    });
  }

  Future<String> _serverScope(DatabaseExecutor executor) async {
    final rows = await executor.query('sync_state',
        columns: ['value'],
        where: 'key = ?',
        whereArgs: ['server_url'],
        limit: 1);
    final url = rows.isEmpty ? '' : rows.single['value'] as String;
    return sha256.convert(utf8.encode(url)).toString();
  }

  Future<Map<String, int>> restore(LocalBackup backup) async {
    final verified = LocalBackup.parse(backup.encode());
    // 仅恢复到原服务器，避免待同步任务误提交。
    final data = verified.payload['data'] as Map<String, dynamic>;
    return db.transaction((transaction) async {
      if (verified.payload['server_scope'] != await _serverScope(transaction)) {
        throw const FormatException('备份与当前服务器不匹配，请先连接原服务器');
      }
      final deviceRows = await transaction.query('sync_state',
          columns: ['value'],
          where: 'key = ?',
          whereArgs: ['device_id'],
          limit: 1);
      final deviceId = deviceRows.isEmpty
          ? 'device-${DateTime.now().microsecondsSinceEpoch}'
          : deviceRows.single['value'] as String;
      if (deviceRows.isEmpty) {
        await transaction
            .insert('sync_state', {'key': 'device_id', 'value': deviceId});
      }
      await transaction.delete('diaries');
      await transaction.delete('outbox');
      await transaction.delete('diary_conflicts');
      await transaction.delete('playback_records');
      await transaction.delete('device_view_events');
      await transaction.delete('sync_state',
          where: 'key != ? AND key != ?',
          whereArgs: ['server_url', 'device_id']);
      for (final raw in data['diaries'] as List) {
        await transaction.insert(
            'diaries', Map<String, dynamic>.from(raw as Map));
      }
      for (final raw in data['outbox'] as List) {
        final row = Map<String, dynamic>.from(raw as Map)..remove('id');
        if (row['action'] == 'playback') {
          final payload =
              Map<String, dynamic>.from(jsonDecode(row['json'] as String));
          payload['device_id'] = deviceId;
          row['json'] = jsonEncode(payload);
        }
        await transaction.insert('outbox', row);
      }
      for (final raw in data['conflicts'] as List) {
        await transaction.insert(
            'diary_conflicts', Map<String, dynamic>.from(raw as Map));
      }
      for (final raw in data['playback_records'] as List) {
        final row = Map<String, dynamic>.from(raw as Map);
        row['device_id'] = deviceId;
        await transaction.insert('playback_records', row);
      }
      for (final raw in data['device_view_events'] as List) {
        await transaction.insert(
            'device_view_events', Map<String, dynamic>.from(raw as Map));
      }
      for (final raw in data['settings'] as List) {
        await transaction.insert(
            'sync_state', Map<String, dynamic>.from(raw as Map));
      }
      return {
        'diaries': (data['diaries'] as List).length,
        'outbox': (data['outbox'] as List).length,
        'conflicts': (data['conflicts'] as List).length,
        'playback_records': (data['playback_records'] as List).length,
      };
    });
  }
}
