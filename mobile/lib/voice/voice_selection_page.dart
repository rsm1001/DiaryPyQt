import 'dart:developer' as developer;

import 'package:flutter/material.dart';

import '../localization/app_strings.dart';
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
      final strings = AppStrings.of(context);
      setState(() {
        _voices = voices;
        _message = voices.isEmpty ? strings.noVoices : null;
      });
    } catch (error, stack) {
      developer.log(
        'voice_list_failed request_id=${DateTime.now().microsecondsSinceEpoch}',
        name: 'diary.voice',
        error: error,
        stackTrace: stack,
      );
      if (mounted) {
        setState(() => _message = AppStrings.of(context).voicesUnavailable);
      }
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
        'voice_selection_saved request_id=${DateTime.now().microsecondsSinceEpoch}',
        name: 'diary.voice',
      );
      if (mounted) Navigator.pop(context, voiceId);
    } catch (error, stack) {
      developer.log(
        'voice_selection_save_failed request_id=${DateTime.now().microsecondsSinceEpoch}',
        name: 'diary.voice',
        error: error,
        stackTrace: stack,
      );
      if (mounted) {
        setState(() => _message = AppStrings.of(context).saveVoiceFailed);
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final strings = AppStrings.of(context);
    return Scaffold(
      appBar: AppBar(
        title: Text(strings.voiceSelection),
        actions: [
          IconButton(
            tooltip: strings.refreshVoices,
            onPressed: _loading ? null : _load,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: ListView(children: [
        if (_loading) const LinearProgressIndicator(),
        if (_message != null)
          Padding(padding: const EdgeInsets.all(16), child: Text(_message!)),
        ListTile(
          title: Text(strings.currentSetting),
          subtitle: Text(widget.currentVoiceId.isEmpty
              ? strings.defaultVoice
              : strings.voiceId(widget.currentVoiceId)),
        ),
        if (_voices != null && _voices!.isNotEmpty) ...[
          ListTile(
            title: Text(strings.useDefaultVoice),
            leading: Icon(widget.currentVoiceId.isEmpty
                ? Icons.radio_button_checked
                : Icons.radio_button_unchecked),
            onTap: _saving ? null : () => _select(''),
          ),
          for (final voice in _voices!)
            ListTile(
              title: Text(voice.name),
              subtitle: Text(
                  '${voice.language} ? ${strings.voiceOffline(voice.offlineSupported)}'),
              leading: Icon(widget.currentVoiceId == voice.id
                  ? Icons.radio_button_checked
                  : Icons.radio_button_unchecked),
              onTap: _saving ? null : () => _select(voice.id),
            ),
        ],
        Padding(
          padding: const EdgeInsets.all(16),
          child: Text(strings.voiceNote),
        ),
      ]),
    );
  }
}
