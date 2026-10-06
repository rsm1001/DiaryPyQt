import 'dart:io';

import 'package:diary_mobile/models/audio_asset.dart';
import 'package:diary_mobile/services/diary_api.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

const _asset = AudioAsset(
  id: 'asset',
  diaryId: 'diary',
  voiceId: 'voice',
  contentHash: 'hash',
  fileHash: 'hash',
  durationMs: 1000,
  downloadUrl: 'https://example.invalid/api/v1/audio-assets/asset/download',
);

void main() {
  late Directory directory;
  setUp(() async => directory = await Directory.systemTemp.createTemp());
  tearDown(() async => directory.delete(recursive: true));

  test('partial download resumes from the existing byte offset', () async {
    final target = File('${directory.path}/audio.part');
    await target.writeAsBytes([1, 2]);
    final api = DiaryApi(
      baseUrl: 'https://example.invalid',
      client: MockClient((request) async {
        expect(request.headers['Range'], 'bytes=2-');
        return http.Response.bytes([3, 4], 206);
      }),
    );
    await api.downloadAudioToFile(_asset, target);
    expect(await target.readAsBytes(), [1, 2, 3, 4]);
    api.dispose();
  });

  test('full download replaces an obsolete partial file', () async {
    final target = File('${directory.path}/audio.part');
    await target.writeAsBytes([1, 2]);
    final api = DiaryApi(
      baseUrl: 'https://example.invalid',
      client: MockClient((request) async {
        expect(request.headers['Range'], 'bytes=2-');
        return http.Response.bytes([5, 6, 7], 200);
      }),
    );
    await api.downloadAudioToFile(_asset, target);
    expect(await target.readAsBytes(), [5, 6, 7]);
    api.dispose();
  });

  test('expired partial range retries without offset', () async {
    final target = File('${directory.path}/audio.part');
    await target.writeAsBytes([1, 2, 3]);
    var requests = 0;
    final api = DiaryApi(
      baseUrl: 'https://example.invalid',
      client: MockClient((request) async {
        requests++;
        if (requests == 1) {
          expect(request.headers['Range'], 'bytes=3-');
          return http.Response('', 416);
        }
        expect(request.headers.containsKey('Range'), isFalse);
        return http.Response.bytes([4, 5], 200);
      }),
    );
    await api.downloadAudioToFile(_asset, target);
    expect(requests, 2);
    expect(await target.readAsBytes(), [4, 5]);
    api.dispose();
  });

  test('failed download does not replace cached partial bytes', () async {
    final target = File('${directory.path}/audio.part');
    await target.writeAsBytes([1, 2]);
    final api = DiaryApi(
      baseUrl: 'https://example.invalid',
      client: MockClient((_) async => http.Response('', 503)),
    );
    await expectLater(api.downloadAudioToFile(_asset, target),
        throwsA(isA<DiaryApiException>()));
    expect(await target.readAsBytes(), [1, 2]);
    api.dispose();
  });
}
