import 'dart:convert';
import 'dart:developer' as developer;
import 'dart:math';
import 'dart:typed_data';

import 'package:http/http.dart' as http;

import '../config/app_config.dart';
import '../models/audio_asset.dart';
import '../models/diary.dart';
import '../models/diary_view_result.dart';
import '../models/diary_tag.dart';
import '../models/server_statistics.dart';

class DiaryApiException implements Exception {
  const DiaryApiException(this.message, {this.network = false});
  final String message;
  final bool network;
  @override
  String toString() => message;
}

class DiaryApi {
  DiaryApi({http.Client? client, String? baseUrl, String? password})
      : _client = client ?? http.Client(),
        _password = password,
        _baseUrl = (baseUrl ?? AppConfig.normalizedApiBaseUrl)
            .replaceFirst(RegExp(r'/+$'), '');
  final http.Client _client;
  final String _baseUrl;
  final String? _password;
  Map<String, String> get _authHeaders =>
      _password == null || _password!.isEmpty
          ? const {}
          : {
              'Authorization':
                  'Basic ${base64Encode(utf8.encode('diary:$_password'))}'
            };
  static const _timeout = Duration(seconds: 12);

  Future<void> checkConnection() async {
    try {
      final response = await _client
          .get(Uri.parse('$_baseUrl/health'), headers: _authHeaders)
          .timeout(_timeout);
      _ensureSuccess(response);
      final body = jsonDecode(response.body) as Map<String, dynamic>;
      if (body['service'] != 'diary-server' || body['status'] != 'ok') {
        throw const DiaryApiException('This address is not the diary server');
      }
    } catch (error) {
      if (error is DiaryApiException) rethrow;
      throw DiaryApiException('无法连接 $_baseUrl', network: true);
    }
  }

  Future<List<Diary>> fetchDiaries() async {
    const pageSize = 500;
    final diaries = <Diary>[];
    while (true) {
      final response = await _client
          .get(
              Uri.parse(
                  '$_baseUrl/api/v1/diaries?limit=$pageSize&offset=${diaries.length}'),
              headers: _authHeaders)
          .timeout(_timeout);
      _ensureSuccess(response);
      final body = jsonDecode(response.body) as Map<String, dynamic>;
      final items = (body['items'] as List<dynamic>? ?? const []);
      diaries.addAll(
          items.map((item) => Diary.fromJson(item as Map<String, dynamic>)));
      if (items.length < pageSize) return diaries;
    }
  }

  Map<String, String> _mutationHeaders(String requestId) => {
        ..._authHeaders,
        'Content-Type': 'application/json',
        'X-Request-ID': requestId,
      };

  String _newRequestId() =>
      '${DateTime.now().microsecondsSinceEpoch}-${Random.secure().nextInt(1 << 32)}';

  void _logMutation(String action, String requestId, int status) {
    developer.log(
      jsonEncode(
          {'request_id': requestId, 'operation': action, 'status': status}),
      name: 'diary.mobile',
    );
  }

  Future<T> _networkSafe<T>(Future<T> Function() operation) async {
    try {
      return await operation();
    } on DiaryApiException {
      rethrow;
    } catch (_) {
      throw const DiaryApiException('无法连接日记服务器', network: true);
    }
  }

  Future<DiaryViewResult> recordView(Diary diary) async {
    return _networkSafe(() async {
      final requestId = _newRequestId();
      final response = await _client
          .post(
            Uri.parse(
                '$_baseUrl/api/v1/diaries/${Uri.encodeComponent(diary.id)}/view'),
            headers: _mutationHeaders(requestId),
          )
          .timeout(_timeout);
      _logMutation('record_view', requestId, response.statusCode);
      _ensureSuccess(response);
      final body = jsonDecode(response.body) as Map<String, dynamic>;
      return DiaryViewResult.fromJson(body);
    });
  }

  Future<List<Diary>> fetchTrash() async {
    final response = await _client
        .get(Uri.parse('$_baseUrl/api/v1/trash?limit=500&offset=0'),
            headers: _authHeaders)
        .timeout(_timeout);
    _ensureSuccess(response);
    final body = jsonDecode(response.body) as Map<String, dynamic>;
    return (body['items'] as List<dynamic>? ?? const [])
        .map((item) => Diary.fromJson(item as Map<String, dynamic>))
        .toList(growable: false);
  }

  Future<Diary> restoreDiary(Diary diary) async {
    final requestId = _newRequestId();
    final url = Uri.parse(
            '$_baseUrl/api/v1/trash/${Uri.encodeComponent(diary.id)}/restore')
        .replace(queryParameters: {'version': '${diary.version}'});
    final response = await _client
        .post(url, headers: _mutationHeaders(requestId))
        .timeout(_timeout);
    _logMutation('restore_diary', requestId, response.statusCode);
    _ensureSuccess(response);
    return Diary.fromJson(jsonDecode(response.body) as Map<String, dynamic>);
  }

  Future<void> permanentlyDeleteDiary(Diary diary) async {
    final requestId = _newRequestId();
    final response = await _client
        .delete(
            Uri.parse(
                '$_baseUrl/api/v1/trash/${Uri.encodeComponent(diary.id)}'),
            headers: _mutationHeaders(requestId))
        .timeout(_timeout);
    _logMutation('permanently_delete_diary', requestId, response.statusCode);
    _ensureSuccess(response);
  }

  Future<Diary> createDiary({
    required String date,
    required String content,
    required List<String> tags,
  }) async {
    return _networkSafe(() async {
      final requestId = _newRequestId();
      final response = await _client
          .post(Uri.parse('$_baseUrl/api/v1/diaries'),
              headers: _mutationHeaders(requestId),
              body:
                  jsonEncode({'date': date, 'content': content, 'tags': tags}))
          .timeout(_timeout);
      _logMutation('create_diary', requestId, response.statusCode);
      _ensureSuccess(response);
      return Diary.fromJson(jsonDecode(response.body) as Map<String, dynamic>);
    });
  }

  Future<Diary> updateDiary(
    Diary diary, {
    required String content,
    required List<String> tags,
  }) async {
    return _networkSafe(() async {
      final requestId = _newRequestId();
      final response = await _client
          .patch(
              Uri.parse(
                  '$_baseUrl/api/v1/diaries/${Uri.encodeComponent(diary.id)}'),
              headers: _mutationHeaders(requestId),
              body: jsonEncode({
                'content': content,
                'tags': tags,
                'version': diary.version,
              }))
          .timeout(_timeout);
      _logMutation('update_diary', requestId, response.statusCode);
      _ensureSuccess(response);
      return Diary.fromJson(jsonDecode(response.body) as Map<String, dynamic>);
    });
  }

  Future<void> deleteDiary(Diary diary) async {
    return _networkSafe(() async {
      final requestId = _newRequestId();
      final url =
          Uri.parse('$_baseUrl/api/v1/diaries/${Uri.encodeComponent(diary.id)}')
              .replace(queryParameters: {'version': '${diary.version}'});
      final response = await _client
          .delete(url, headers: _mutationHeaders(requestId))
          .timeout(_timeout);
      _logMutation('delete_diary', requestId, response.statusCode);
      _ensureSuccess(response);
    });
  }

  Future<ServerStatistics> fetchStatistics() async {
    final response = await _client
        .get(Uri.parse('$_baseUrl/api/v1/statistics'), headers: _authHeaders)
        .timeout(_timeout);
    _ensureSuccess(response);
    return ServerStatistics.fromJson(
        jsonDecode(response.body) as Map<String, dynamic>);
  }

  Future<List<DiaryTag>> fetchTags() async {
    final response = await _client
        .get(Uri.parse('$_baseUrl/api/v1/tags'), headers: _authHeaders)
        .timeout(_timeout);
    _ensureSuccess(response);
    final body = jsonDecode(response.body) as Map<String, dynamic>;
    return (body['items'] as List<dynamic>? ?? const [])
        .map((item) => DiaryTag.fromJson(item as Map<String, dynamic>))
        .toList(growable: false);
  }

  Future<DiaryTag> createTag(String name) async {
    final requestId = _newRequestId();
    final response = await _client
        .post(Uri.parse('$_baseUrl/api/v1/tags'),
            headers: _mutationHeaders(requestId),
            body: jsonEncode({'name': name}))
        .timeout(_timeout);
    _logMutation('create_tag', requestId, response.statusCode);
    _ensureSuccess(response);
    return DiaryTag.fromJson(jsonDecode(response.body) as Map<String, dynamic>);
  }

  Future<DiaryTag> updateTag(DiaryTag tag, String name) async {
    final requestId = _newRequestId();
    final response = await _client
        .patch(
            Uri.parse('$_baseUrl/api/v1/tags/${Uri.encodeComponent(tag.id)}'),
            headers: _mutationHeaders(requestId),
            body: jsonEncode({'name': name}))
        .timeout(_timeout);
    _logMutation('update_tag', requestId, response.statusCode);
    _ensureSuccess(response);
    return DiaryTag.fromJson(jsonDecode(response.body) as Map<String, dynamic>);
  }

  Future<void> deleteTag(DiaryTag tag) async {
    final requestId = _newRequestId();
    final response = await _client
        .delete(
            Uri.parse('$_baseUrl/api/v1/tags/${Uri.encodeComponent(tag.id)}'),
            headers: _mutationHeaders(requestId))
        .timeout(_timeout);
    _logMutation('delete_tag', requestId, response.statusCode);
    _ensureSuccess(response);
  }

  Future<AudioAsset> generateAudio(String diaryId, {String? voiceId}) async {
    final response = await _client.post(
        Uri.parse('$_baseUrl/api/v1/diaries/$diaryId/audio/generate'),
        headers: {..._authHeaders, 'Content-Type': 'application/json'},
        body: jsonEncode({'voice_id': voiceId}));
    _ensureSuccess(response);
    return AudioAsset.fromJson(
        jsonDecode(response.body) as Map<String, dynamic>, _baseUrl);
  }

  Future<Uint8List> downloadAudio(AudioAsset asset) async {
    if (Uri.parse(asset.downloadUrl).origin != Uri.parse(_baseUrl).origin) {
      throw const DiaryApiException(
          'Audio download host does not match the diary server');
    }
    final response = await _client
        .get(Uri.parse(asset.downloadUrl), headers: _authHeaders)
        .timeout(const Duration(minutes: 3));
    _ensureSuccess(response);
    return response.bodyBytes;
  }

  Future<Map<String, dynamic>> pull(int cursor) async {
    final response = await _client
        .get(Uri.parse('$_baseUrl/api/v1/sync/pull?cursor=$cursor'),
            headers: _authHeaders)
        .timeout(_timeout);
    _ensureSuccess(response);
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future<void> push(List<Map<String, dynamic>> operations) async {
    if (operations.isEmpty) return;
    final response = await _client.post(Uri.parse('$_baseUrl/api/v1/sync/push'),
        headers: {..._authHeaders, 'Content-Type': 'application/json'},
        body: jsonEncode({'operations': operations}));
    _ensureSuccess(response);
  }

  void dispose() => _client.close();

  static void _ensureSuccess(http.Response response) {
    if (response.statusCode == 401) {
      throw const DiaryApiException(
          'Authentication failed: update the connection password in server settings');
    }
    if (response.statusCode == 409) {
      throw const DiaryApiException('日记版本冲突，请刷新后再操作');
    }
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw DiaryApiException(
          'Server request failed: HTTP ${response.statusCode}');
    }
  }
}
