import 'dart:async';
import 'dart:developer' as developer;

import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../config/app_config.dart';
import '../models/diary.dart';
import 'diary_editor_page.dart';
import 'diary_statistics_page.dart';
import 'tag_manager_page.dart';
import 'trash_page.dart';
import '../services/diary_api.dart';
import '../services/diary_filter.dart';
import '../services/double_playback_service.dart';
import '../services/local_store.dart';
import '../services/sync_manager.dart';
import '../services/random_selector.dart';

class DiaryListPage extends StatefulWidget {
  const DiaryListPage({super.key});
  @override
  State<DiaryListPage> createState() => _DiaryListPageState();
}

class _DiaryListPageState extends State<DiaryListPage> {
  DiaryApi _api = DiaryApi();
  String _serverUrl = AppConfig.normalizedApiBaseUrl;
  final _store = LocalStore();
  final _secrets = const FlutterSecureStorage();
  String? _savedPassword;
  late SyncManager _sync = SyncManager(api: _api, store: _store);
  final _playback = DoublePlaybackService();
  late Future<List<Diary>> _diaries;
  StreamSubscription<PlaybackSnapshot>? _subscription;
  PlaybackSnapshot _snapshot = const PlaybackSnapshot(
      diaryId: null,
      stage: PlaybackStage.idle,
      roundNumber: 0,
      remainingGap: Duration.zero);
  String? _playingDiaryId;
  String? _errorMessage;
  String _searchQuery = '';
  String? _selectedTag;
  final _randomSelector = const WeightedRandomSelector();
  List<Diary> _randomQueue = const [];
  Diary? _randomCurrent;
  bool _randomMode = false;
  int _randomToken = 0;
  int _playRequest = 0;

  @override
  void initState() {
    super.initState();
    _diaries = _initialize();
    _subscription = _playback.stateStream.listen((snapshot) {
      if (mounted) setState(() => _snapshot = snapshot);
    });
  }

  Future<List<Diary>> _initialize() async {
    final storedUrl = await _store.getServerUrl();
    if (AppConfig.shouldMigrateLegacyUrl(storedUrl)) {
      _serverUrl = AppConfig.normalizedApiBaseUrl;
      await _store.saveServerUrl(_serverUrl);
    } else if (storedUrl != null && storedUrl.isNotEmpty) {
      _serverUrl = storedUrl;
    }
    final credentialOrigin =
        await _secrets.read(key: 'diary_server_password_origin');
    _savedPassword = credentialOrigin == _serverUrl
        ? await _secrets.read(key: 'diary_server_password')
        : null;
    _api.dispose();
    _api = DiaryApi(baseUrl: _serverUrl, password: _savedPassword);
    _sync = SyncManager(api: _api, store: _store);
    return _loadDiaries();
  }

  Future<void> _configureServer() async {
    final controller = TextEditingController(text: _serverUrl);
    final passwordController = TextEditingController();
    String? validationError;
    final url = await showDialog<String>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (context, updateDialog) => AlertDialog(
          title: const Text('Connect to diary server'),
          content: Column(mainAxisSize: MainAxisSize.min, children: [
            TextField(
              controller: controller,
              keyboardType: TextInputType.url,
              autocorrect: false,
              decoration: InputDecoration(
                labelText: 'Server URL',
                hintText: AppConfig.normalizedApiBaseUrl,
                errorText: validationError,
              ),
            ),
            const SizedBox(height: 8),
            TextField(
              controller: passwordController,
              obscureText: true,
              autocorrect: false,
              decoration: const InputDecoration(
                labelText: 'Connection password',
                hintText: 'From desktop connection file',
              ),
            ),
            const SizedBox(height: 8),
            const Text(
                'Use HTTPS for public access. Leave password blank to keep the saved one.'),
          ]),
          actions: [
            TextButton(
                onPressed: () => Navigator.pop(dialogContext),
                child: const Text('Cancel')),
            FilledButton(
              onPressed: () {
                final candidate =
                    controller.text.trim().replaceFirst(RegExp(r'/+$'), '');
                final parsed = Uri.tryParse(candidate);
                if (parsed == null ||
                    !parsed.hasAuthority ||
                    (parsed.scheme != 'https' &&
                        !(parsed.scheme == 'http' &&
                            (parsed.host == '10.0.2.2' ||
                                parsed.host == '127.0.0.1' ||
                                parsed.host == '100.125.111.63'))) ||
                    parsed.userInfo.isNotEmpty ||
                    parsed.path.isNotEmpty ||
                    parsed.hasQuery ||
                    parsed.hasFragment) {
                  updateDialog(() => validationError =
                      'Enter an HTTPS URL without a path; HTTP is private-network only');
                  return;
                }
                Navigator.pop(dialogContext, candidate);
              },
              child: const Text('Test & save'),
            ),
          ],
        ),
      ),
    );
    if (url == null || !mounted) return;
    final typedPassword = passwordController.text.trim();
    final password = typedPassword.isEmpty
        ? (url == _serverUrl ? _savedPassword : null)
        : typedPassword;
    final candidate = DiaryApi(baseUrl: url, password: password);
    try {
      await candidate.checkConnection();
      if (!mounted) return;
      await _store.saveServerUrl(url);
      if (typedPassword.isNotEmpty) {
        await _secrets.write(
            key: 'diary_server_password', value: typedPassword);
        await _secrets.write(key: 'diary_server_password_origin', value: url);
      }
      if (!mounted) {
        candidate.dispose();
        return;
      }
      final previous = _api;
      setState(() {
        _serverUrl = url;
        _savedPassword = password;
        _api = candidate;
        _sync = SyncManager(api: _api, store: _store);
        _errorMessage = null;
        _diaries = _loadDiaries();
      });
      previous.dispose();
      ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Diary server connected')));
    } catch (error) {
      if (mounted) setState(() => _errorMessage = '$error');
      candidate.dispose();
    }
  }

  Future<List<Diary>> _loadDiaries() async {
    final local = await _sync.loadLocal();
    if (local.isNotEmpty && mounted) setState(() => _errorMessage = null);
    try {
      final remote = await _sync.refresh();
      if (mounted) setState(() => _errorMessage = null);
      return remote;
    } catch (error) {
      if (mounted) {
        setState(() => _errorMessage =
            'Cannot connect to $_serverUrl: $error. For public access use HTTPS and enter the connection password from your desktop.');
      }
      return local;
    }
  }

  Future<void> _toggleDiary(Diary diary) async {
    if (_randomMode) {
      _randomToken++;
      _randomMode = false;
      _randomQueue = const [];
      _randomCurrent = null;
    }
    if (_playingDiaryId == diary.id &&
        _snapshot.stage != PlaybackStage.completed) {
      if (_snapshot.stage == PlaybackStage.paused) {
        await _playback.resume();
      } else {
        await _playback.pause();
      }
      return;
    }
    await _playDiary(diary);
  }

  Future<void> _playDiary(Diary diary, {bool fromRandomQueue = false}) async {
    final request = ++_playRequest;
    await _playback.stop();
    if (!mounted || request != _playRequest) return;
    setState(() {
      _playingDiaryId = diary.id;
      _errorMessage = null;
    });
    var completed = false;
    try {
      final asset = await _sync.ensureAudio(diary);
      if (!mounted ||
          request != _playRequest ||
          (fromRandomQueue && !_randomMode)) {
        return;
      }
      completed = await _playback.playDiary(
          diaryId: diary.id,
          source: asset.localPath ?? asset.downloadUrl,
          asset: asset);
    } catch (error, stack) {
      developer.log(
          'audio_playback_failed request_id=${DateTime.now().microsecondsSinceEpoch} diary_id=${diary.id}',
          name: 'diary.playback',
          error: error,
          stackTrace: stack);
      if (mounted && request == _playRequest) {
        await _playback.stop();
        if (!mounted || request != _playRequest) return;
        setState(() => _errorMessage = error is StateError &&
                error.message == 'Audio playback stalled'
            ? '\u97f3\u9891\u64ad\u653e\u65e0\u8fdb\u5ea6\uff0c\u8bf7\u68c0\u67e5\u8bbe\u5907\u97f3\u9891\u89e3\u7801\u6216\u91cd\u65b0\u540c\u6b65\u97f3\u9891'
            : '\u97f3\u9891\u65e0\u6cd5\u64ad\u653e\uff0c\u8bf7\u68c0\u67e5\u7f51\u7edc\u6216\u91cd\u65b0\u540c\u6b65\u97f3\u9891');
      }
    } finally {
      if (mounted && request == _playRequest && _playingDiaryId == diary.id) {
        setState(() => _playingDiaryId = null);
      }
    }
    if (fromRandomQueue && _randomMode && mounted && request == _playRequest) {
      if (!completed) await _playback.stop();
      await _playNextRandom();
    }
  }

  String _randomStageLabel() {
    switch (_snapshot.stage) {
      case PlaybackStage.waiting:
        return '\u4e24\u904d\u4e4b\u95f4\u7b49\u5f85\u4e2d';
      case PlaybackStage.buffering:
        return '\u97f3\u9891\u52a0\u8f7d\u4e2d';
      case PlaybackStage.playingFirst:
        return '\u7b2c 1 \u904d\u64ad\u653e\u4e2d';
      case PlaybackStage.playingSecond:
        return '\u7b2c 2 \u904d\u64ad\u653e\u4e2d';
      case PlaybackStage.paused:
        return '\u5df2\u6682\u505c';
      case PlaybackStage.completed:
        return '\u5df2\u5b8c\u6210';
      case PlaybackStage.idle:
        return '\u51c6\u5907\u64ad\u653e';
    }
  }

  Future<void> _openStatistics() async {
    final diaries = await _store.getDiaries();
    if (!mounted) return;
    await Navigator.of(context).push(
      MaterialPageRoute(
          builder: (_) => DiaryStatisticsPage(diaries: diaries, api: _api)),
    );
  }

  Future<void> _stopRandomPlayback() async {
    _randomToken++;
    _playRequest++;
    if (mounted) {
      setState(() {
        _randomMode = false;
        _randomQueue = const [];
        _randomCurrent = null;
        _playingDiaryId = null;
      });
    }
    await _playback.stop();
  }

  Future<void> _playRandomCached() async {
    final token = ++_randomToken;
    _playRequest++;
    final diaries = await _store.getDiaries();
    if (!mounted || token != _randomToken) return;
    final candidates = filterDiaries(diaries, _searchQuery, _selectedTag);
    if (candidates.isEmpty) {
      if (mounted) {
        setState(() => _errorMessage =
            '\u5f53\u524d\u7b5b\u9009\u6ca1\u6709\u53ef\u968f\u673a\u64ad\u653e\u7684\u65e5\u8bb0');
      }
      return;
    }
    await _playback.stop();
    if (!mounted || token != _randomToken) return;
    if (mounted) {
      setState(() {
        _randomMode = true;
        _randomQueue = candidates;
        _randomCurrent = null;
        _errorMessage = null;
      });
    }
    await _playNextRandom();
  }

  Future<void> _playNextRandom() async {
    final token = _randomToken;
    if (!_randomMode || _randomQueue.isEmpty) {
      if (mounted) {
        setState(() {
          _randomMode = false;
          _randomQueue = const [];
          _randomCurrent = null;
        });
      }
      return;
    }
    final usage = await _store.getRandomUsage();
    if (!mounted || !_randomMode || token != _randomToken) return;
    final diary = _randomSelector.select(_randomQueue, usage: usage);
    if (diary == null) {
      await _stopRandomPlayback();
      return;
    }
    if (mounted) {
      setState(() {
        _randomCurrent = diary;
        _randomQueue =
            _randomQueue.where((item) => item.id != diary.id).toList();
      });
    }
    unawaited(
        _sync.recordView(diary).catchError((Object error, StackTrace stack) {
      developer.log(
          'random_view_record_failed request_id=${DateTime.now().microsecondsSinceEpoch} diary_id=${diary.id}',
          name: 'diary.playback',
          error: error,
          stackTrace: stack);
    }));
    await _store.recordRandomSelection(diary.id);
    if (!mounted || !_randomMode || token != _randomToken) return;
    await _playDiary(diary, fromRandomQueue: true);
  }

  Future<void> _openEditor([Diary? diary]) async {
    if (diary != null) {
      try {
        await _sync.recordView(diary);
      } catch (_) {
        // ?????????????????
      }
    }
    if (!mounted) return;
    final changed = await Navigator.of(context).push<bool>(
      MaterialPageRoute(
          builder: (_) => DiaryEditorPage(sync: _sync, diary: diary)),
    );
    if (changed != true || !mounted) return;
    if (_playingDiaryId == diary?.id) {
      await _playback.stop();
      if (mounted) setState(() => _playingDiaryId = null);
    }
    if (mounted) await _refresh();
  }

  Future<void> _refresh() async {
    final refreshed = _loadDiaries();
    setState(() {
      _diaries = refreshed;
    });
    await refreshed;
  }

  @override
  void dispose() {
    _randomToken++;
    _playRequest++;
    _subscription?.cancel();
    _api.dispose();
    unawaited(_store.close());
    unawaited(_playback.dispose());
    super.dispose();
  }

  String _stageLabel(Diary diary) {
    if (_playingDiaryId != diary.id) return 'v${diary.version}';
    switch (_snapshot.stage) {
      case PlaybackStage.buffering:
        return 'Buffering';
      case PlaybackStage.playingFirst:
        return 'Playing 1/2';
      case PlaybackStage.waiting:
        return 'Repeat gap ${_snapshot.remainingGap.inSeconds}s';
      case PlaybackStage.playingSecond:
        return 'Playing 2/2';
      case PlaybackStage.paused:
        return 'Paused';
      case PlaybackStage.completed:
        return 'Completed';
      case PlaybackStage.idle:
        return 'Ready';
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('\u65e5\u8bb0'), actions: [
          IconButton(
              tooltip: '\u670d\u52a1\u5668\u8bbe\u7f6e',
              onPressed: _configureServer,
              icon: const Icon(Icons.settings)),
          IconButton(
              tooltip: '\u5237\u65b0',
              onPressed: _refresh,
              icon: const Icon(Icons.refresh)),
          IconButton(
              tooltip: '\u6807\u7b7e\u7ba1\u7406',
              onPressed: () => Navigator.of(context).push(
                    MaterialPageRoute(
                        builder: (_) => TagManagerPage(api: _api)),
                  ),
              icon: const Icon(Icons.label_outline)),
          IconButton(
              tooltip: '\u56de\u6536\u7ad9',
              onPressed: () => Navigator.of(context).push(
                    MaterialPageRoute(builder: (_) => TrashPage(api: _api)),
                  ),
              icon: const Icon(Icons.delete_outline)),
          IconButton(
              tooltip: '\u7edf\u8ba1',
              onPressed: _openStatistics,
              icon: const Icon(Icons.analytics_outlined)),
          IconButton(
              tooltip: '\u968f\u673a\u8fde\u7eed\u64ad\u653e',
              onPressed: _playRandomCached,
              icon: const Icon(Icons.shuffle)),
        ]),
        floatingActionButton: FloatingActionButton(
          tooltip: '新建日记',
          onPressed: () => _openEditor(),
          child: const Icon(Icons.add),
        ),
        body: Column(children: [
          if (_errorMessage != null)
            MaterialBanner(content: Text(_errorMessage!), actions: [
              TextButton(onPressed: _refresh, child: const Text('重试'))
            ]),
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 8, 12, 4),
            child: SizedBox(
              width: double.infinity,
              child: _randomMode
                  ? OutlinedButton.icon(
                      onPressed: _stopRandomPlayback,
                      icon: const Icon(Icons.stop_circle_outlined),
                      label: const Text(
                          '\u505c\u6b62\u968f\u673a\u8fde\u7eed\u64ad\u653e'),
                    )
                  : FilledButton.icon(
                      onPressed: _playRandomCached,
                      icon: const Icon(Icons.shuffle),
                      label: const Text(
                          '\u5f00\u59cb\u968f\u673a\u8fde\u7eed\u64ad\u653e'),
                    ),
            ),
          ),
          if (_randomMode)
            Padding(
              padding: const EdgeInsets.fromLTRB(12, 4, 12, 4),
              child: Card(
                color: Theme.of(context).colorScheme.primaryContainer,
                child: Padding(
                  padding: const EdgeInsets.all(8),
                  child: Column(
                    children: [
                      ListTile(
                        leading: const Icon(Icons.shuffle),
                        title: Text(_randomCurrent == null
                            ? '\u6b63\u5728\u9009\u62e9\u4e0b\u4e00\u6761\u968f\u673a\u65e5\u8bb0\u2026'
                            : '\u5f53\u524d\uff1a${_randomCurrent!.date}'),
                        subtitle: Text(_randomCurrent == null
                            ? '\u968f\u673a\u961f\u5217\u51c6\u5907\u4e2d'
                            : '${_randomCurrent!.content}\\n${_randomStageLabel()} \u00b7 \u5269\u4f59 ${_randomQueue.length} \u6761'),
                        isThreeLine: true,
                      ),
                      if (_snapshot.stage == PlaybackStage.buffering)
                        const LinearProgressIndicator()
                      else if (_snapshot.duration > Duration.zero)
                        LinearProgressIndicator(
                          value: (_snapshot.position.inMilliseconds /
                                  _snapshot.duration.inMilliseconds)
                              .clamp(0.0, 1.0),
                        ),
                      if (_snapshot.duration > Duration.zero)
                        Align(
                          alignment: Alignment.centerRight,
                          child: Text(
                            '${_snapshot.position.inSeconds}s / ${_snapshot.duration.inSeconds}s',
                            style: Theme.of(context).textTheme.labelSmall,
                          ),
                        ),
                    ],
                  ),
                ),
              ),
            ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12),
            child: TextField(
              onChanged: (value) => setState(() => _searchQuery = value),
              decoration: const InputDecoration(
                  prefixIcon: Icon(Icons.search), hintText: '搜索日期、正文或标签'),
            ),
          ),
          Expanded(
            child: FutureBuilder<List<Diary>>(
              future: _diaries,
              builder: (context, snapshot) {
                if (snapshot.connectionState == ConnectionState.waiting) {
                  return const Center(child: CircularProgressIndicator());
                }
                final diaries = snapshot.data ?? const <Diary>[];
                if (diaries.isEmpty) {
                  return const Center(child: Text('暂无已缓存的日记'));
                }
                final tags = diaries
                    .expand((diary) => diary.tags)
                    .toSet()
                    .toList()
                  ..sort();
                final selectedTag =
                    tags.contains(_selectedTag) ? _selectedTag : null;
                final filtered =
                    filterDiaries(diaries, _searchQuery, selectedTag);
                return Column(children: [
                  Align(
                    alignment: Alignment.centerLeft,
                    child: Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 16),
                      child: DropdownButton<String?>(
                        value: selectedTag,
                        items: [
                          const DropdownMenuItem<String?>(
                              value: null, child: Text('全部标签')),
                          ...tags.map((tag) => DropdownMenuItem<String?>(
                                value: tag,
                                child: Text(tag),
                              )),
                        ],
                        onChanged: (tag) => setState(() => _selectedTag = tag),
                      ),
                    ),
                  ),
                  Expanded(
                    child: filtered.isEmpty
                        ? const Center(child: Text('没有匹配的日记'))
                        : RefreshIndicator(
                            onRefresh: _refresh,
                            child: ListView.separated(
                              padding: const EdgeInsets.all(12),
                              itemCount: filtered.length,
                              separatorBuilder: (_, __) =>
                                  const SizedBox(height: 8),
                              itemBuilder: (context, index) {
                                final diary = filtered[index];
                                final active = _playingDiaryId == diary.id &&
                                    _snapshot.stage != PlaybackStage.completed;
                                return Card(
                                  child: ListTile(
                                    onTap: () => _openEditor(diary),
                                    title: Text(diary.date),
                                    subtitle: Text(
                                      '${_stageLabel(diary)}\n${diary.content}',
                                      maxLines: 4,
                                      overflow: TextOverflow.ellipsis,
                                    ),
                                    trailing: IconButton(
                                      tooltip: active ? '暂停' : '播放',
                                      onPressed: () => _toggleDiary(diary),
                                      icon: Icon(active
                                          ? Icons.pause
                                          : Icons.play_arrow),
                                    ),
                                  ),
                                );
                              },
                            ),
                          ),
                  ),
                ]);
              },
            ),
          ),
        ]),
      );
}
