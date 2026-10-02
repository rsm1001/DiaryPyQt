import 'dart:developer' as developer;

import 'package:flutter/material.dart';

import '../services/diary_api.dart';
import '../services/local_store.dart';
import 'voice_profile.dart';

class VoiceSelectionPage extends StatefulWidget {
  const VoiceSelectionPage({
    super.key,
    required this.api,
    required this.store,
    required this.serverUrl,
    required this.currentVoiceId,
  });

  final DiaryApi api;
  final LocalStore store;
  final String serverUrl;
  final String currentVoiceId;

  @override
  State<VoiceSelectionPage> createState() => _VoiceSelectionPageState();
}

class _VoiceSelectionPageState extends State<VoiceSelectionPage> {
  List<VoiceProfile>? _voices;
  String? _message;
  bool _loading = false;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final voices = await widget.api.fetchVoices();
      if (!mounted) return;
      if (voices.isNotEmpty) {
        await widget.store.saveDefaultVoice(widget.serverUrl, voices.first.id);
      }
      if (!mounted) return;
      setState(() {
        _voices = voices;
        _message = voices.isEmpty ? '服务器暂无可选语音包，保留当前设置。' : null;
      });
    } catch (error, stack) {
      developer.log(
        '语音包列表读取失败 request_id=${DateTime.now().microsecondsSinceEpoch}',
        name: 'diary.voice',
        error: error,
        stackTrace: stack,
      );
      if (mounted) setState(() => _message = '语音包列表不可用，保留当前设置。');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _select(String voiceId) async {
    if (_saving) return;
    setState(() => _saving = true);
    try {
      await widget.store.saveSelectedVoice(widget.serverUrl, voiceId);
      developer.log(
        '语音包选择已保存 request_id=${DateTime.now().microsecondsSinceEpoch}',
        name: 'diary.voice',
      );
      if (mounted) Navigator.pop(context, voiceId);
    } catch (error, stack) {
      developer.log(
        '语音包选择保存失败 request_id=${DateTime.now().microsecondsSinceEpoch}',
        name: 'diary.voice',
        error: error,
        stackTrace: stack,
      );
      if (mounted) setState(() => _message = '保存语音包失败，请重试。');
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('选择语音包'), actions: [
          IconButton(
              tooltip: '刷新语音包',
              onPressed: _loading ? null : _load,
              icon: const Icon(Icons.refresh)),
        ]),
        body: ListView(children: [
          if (_loading) const LinearProgressIndicator(),
          if (_message != null)
            Padding(padding: const EdgeInsets.all(16), child: Text(_message!)),
          ListTile(
            title: const Text('当前设置'),
            subtitle: Text(widget.currentVoiceId.isEmpty
                ? '服务器默认语音包'
                : '语音包编号：${widget.currentVoiceId}'),
          ),
          if (_voices != null && _voices!.isNotEmpty) ...[
            ListTile(
              title: const Text('使用服务器默认语音包'),
              leading: Icon(widget.currentVoiceId.isEmpty
                  ? Icons.radio_button_checked
                  : Icons.radio_button_unchecked),
              onTap: _saving ? null : () => _select(''),
            ),
            for (final voice in _voices!)
              ListTile(
                title: Text(voice.name),
                subtitle: Text('${voice.language} · '
                    '${voice.offlineSupported ? '语音包支持离线，未缓存仍需联网生成' : '未缓存需联网生成'}'),
                leading: Icon(widget.currentVoiceId == voice.id
                    ? Icons.radio_button_checked
                    : Icons.radio_button_unchecked),
                onTap: _saving ? null : () => _select(voice.id),
              ),
          ],
          const Padding(
            padding: EdgeInsets.all(16),
            child: Text('切换语音包不删除已缓存音频，也不会产生查看次数。'),
          ),
        ]),
      );
}
