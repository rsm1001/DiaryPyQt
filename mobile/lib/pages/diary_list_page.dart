import 'dart:async';
import 'dart:developer' as developer;

import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../config/app_config.dart';
import '../models/audio_asset.dart';
import '../models/diary.dart';
import 'advanced_search_dialog.dart';
import 'batch_tag_dialog.dart';
import 'diary_editor_page.dart';
import 'diary_transfer_page.dart';
import 'diary_statistics_page.dart';
import 'tag_manager_page.dart';
import 'server_connection_dialog.dart';
import 'trash_page.dart';
import '../services/diary_api.dart';
import '../services/diary_filter.dart';
import '../services/double_playback_service.dart';
import '../services/local_store.dart';
import '../services/sync_manager.dart';
import '../services/sync_trigger.dart';
import '../services/random_playback_plan.dart';
import '../widgets/diary_list_body.dart';
import '../widgets/random_playback_panel.dart';
import '../widgets/sync_status_banner.dart';

class DiaryListPage extends StatefulWidget {
  const DiaryListPage({super.key});
  @override
  State<DiaryListPage> createState() => _DiaryListPageState();
}

class _DiaryListPageState extends State<DiaryListPage>
    with WidgetsBindingObserver {
  DiaryApi _api = DiaryApi();
  String _serverUrl = AppConfig.normalizedApiBaseUrl;
  final _store = LocalStore();
  final _secrets = const FlutterSecureStorage();
  String? _savedPassword;
  late SyncManager _sync = SyncManager(api: _api, store: _store);
  late final SyncTrigger _syncTrigger = SyncTrigger(
    changes: Connectivity().onConnectivityChanged,
    refresh: _performRefresh,
    onError: _onSyncError,
    onOfflineChanged: (offline) {
      if (mounted) setState(() => _offline = offline);
    },
  );
  bool _initialized = false;
  bool _offline = false;
  bool _syncing = false;
  int _pendingCount = 0;
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
  DiarySearchOptions _searchOptions = const DiarySearchOptions();
  String? _selectedTag;
  final _randomPlanner = RandomPlaybackPlanner();
  Diary? _randomCurrent;
  bool _randomMode = false;
  int _randomToken = 0;
  int _playRequest = 0;
  final Map<String, Future<AudioAsset>> _audioPrefetch = {};
  int _prefetchActive = 0;
  final Map<String, int> _randomFailures = {};
  final Set<String> _selectedDiaryIds = {};
  bool _selectionMode = false;
  bool _batchBusy = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
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
    final diaries = await _loadDiaries();
    await _updatePendingCount();
    if (mounted) {
      _initialized = true;
      _syncTrigger.start();
    }
    return diaries;
  }

  Future<void> _configureServer() async {
    final input = await showServerConnectionDialog(context, _serverUrl);
    if (input == null || !mounted) return;
    final url = input.url;
    final typedPassword = input.password;
    final password = typedPassword.isEmpty
        ? (url == _serverUrl ? _savedPassword : null)
        : typedPassword;
    final candidate = DiaryApi(baseUrl: url, password: password);
    try {
      await candidate.checkConnection();
      if (!mounted) {
        candidate.dispose();
        return;
      }
      if (url != _serverUrl && await _sync.pendingCount() > 0) {
        if (mounted) {
          setState(() => _errorMessage = '还有未同步的查看或编辑记录，请先同步或处理冲突，不可切换服务器。');
        }
        candidate.dispose();
        return;
      }
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
      });
      await _syncTrigger.request();
      previous.dispose();
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(const SnackBar(content: Text('日记服务器连接已验证')));
      }
    } catch (error, stack) {
      developer.log(
        '日记服务器连接失败 request_id=${DateTime.now().microsecondsSinceEpoch}',
        name: 'diary.sync',
        error: error,
        stackTrace: stack,
      );
      if (mounted) {
        setState(() => _errorMessage = '连接校验失败，请检查服务器地址与密码。');
      }
      if (!identical(candidate, _api)) candidate.dispose();
    }
  }

  Future<List<Diary>> _loadDiaries() async {
    final local = await _sync.loadLocal();
    try {
      final remote = await _sync.refresh();
      if (mounted) setState(() => _errorMessage = null);
      return remote;
    } catch (error, stack) {
      developer.log(
        '日记同步失败 request_id=${DateTime.now().microsecondsSinceEpoch}',
        name: 'diary.sync',
        error: error,
        stackTrace: stack,
      );
      final pending = await _sync.pendingCount();
      if (mounted) {
        setState(() {
          _pendingCount = pending;
          _errorMessage = describeSyncFailure(
              conflict: error is DiaryApiException && error.conflict,
              pending: pending);
        });
      }
      return local;
    }
  }

  Future<void> _updatePendingCount() async {
    final pending = await _sync.pendingCount();
    if (mounted && pending != _pendingCount) {
      setState(() => _pendingCount = pending);
    }
  }

  Future<void> _refreshLocalList() async {
    final local = await _store.getDiaries();
    if (mounted) setState(() => _diaries = Future.value(local));
  }

  Future<void> _recordPlaybackView(Diary diary) async {
    try {
      await _sync.recordView(diary);
      final local = await _store.getDiary(diary.id);
      if (mounted && local != null && _randomCurrent?.id == diary.id) {
        setState(() => _randomCurrent = local);
      }
      await _refreshLocalList();
    } catch (error, stack) {
      developer.log(
        'playback_view_record_failed request_id=${DateTime.now().microsecondsSinceEpoch} diary_id=${diary.id}',
        name: 'diary.playback',
        error: error,
        stackTrace: stack,
      );
    } finally {
      await _updatePendingCount();
    }
  }

  Future<AudioAsset> _ensureAudio(Diary diary) {
    final existing = _audioPrefetch[diary.id];
    if (existing != null) return existing;
    final future =
        _sync.ensureAudio(diary).catchError((Object error, StackTrace stack) {
      _audioPrefetch.remove(diary.id);
      Error.throwWithStackTrace(error, stack);
    });
    _audioPrefetch[diary.id] = future;
    return future;
  }

  Future<void> _prefetchRandomPlan() async {
    if (!_randomMode) return;
    for (final diary in _randomPlanner.peek(limit: 3)) {
      if (_prefetchActive >= 2 || _audioPrefetch.containsKey(diary.id)) {
        continue;
      }
      _prefetchActive++;
      unawaited(_prefetchAudio(diary));
    }
  }

  Future<void> _prefetchAudio(Diary diary) async {
    try {
      await _ensureAudio(diary);
    } catch (error, stack) {
      developer.log(
        'audio_prefetch_failed request_id=${DateTime.now().microsecondsSinceEpoch} diary_id=${diary.id}',
        name: 'diary.playback',
        error: error,
        stackTrace: stack,
      );
    } finally {
      _prefetchActive--;
      if (mounted && _randomMode) unawaited(_prefetchRandomPlan());
    }
  }

  void _onSyncError(Object error, StackTrace stack) {
    developer.log(
      '本地同步状态失败 request_id=${DateTime.now().microsecondsSinceEpoch}',
      name: 'diary.sync',
      error: error,
      stackTrace: stack,
    );
    if (mounted) {
      setState(() => _errorMessage = '本地同步状态无法更新，请稍后重试。');
    }
  }

  Future<void> _performRefresh() async {
    if (!mounted) return;
    setState(() => _syncing = true);
    try {
      final diaries = await _loadDiaries();
      if (mounted) setState(() => _diaries = Future.value(diaries));
    } finally {
      await _updatePendingCount();
      if (mounted) setState(() => _syncing = false);
    }
  }

  void _toggleSelection(String diaryId) {
    if (_batchBusy) return;
    setState(() {
      _selectionMode = true;
      if (!_selectedDiaryIds.add(diaryId)) {
        _selectedDiaryIds.remove(diaryId);
      }
      if (_selectedDiaryIds.isEmpty) _selectionMode = false;
    });
  }

  void _cancelSelection() {
    if (_batchBusy) return;
    setState(() {
      _selectionMode = false;
      _selectedDiaryIds.clear();
    });
  }

  Future<void> _batchDeleteSelected() async {
    if (_batchBusy || _selectedDiaryIds.isEmpty) return;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('\u6279\u91cf\u5220\u9664\u65e5\u8bb0'),
        content: Text(
            '\u5c06\u9009\u4e2d\u7684 ${_selectedDiaryIds.length} \u7bc7\u65e5\u8bb0\u79fb\u5165\u56de\u6536\u7ad9\uff0c\u662f\u5426\u7ee7\u7eed\uff1f'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: const Text('\u53d6\u6d88'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(dialogContext, true),
            child: const Text('\u5220\u9664'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    final selectedIds = Set<String>.from(_selectedDiaryIds);
    final diaries = await _store.getDiaries();
    final selected = diaries
        .where((diary) => selectedIds.contains(diary.id))
        .toList(growable: false);
    setState(() => _batchBusy = true);
    try {
      for (final diary in selected) {
        await _sync.deleteDiary(diary);
      }
      if (mounted) {
        setState(() {
          _selectionMode = false;
          _selectedDiaryIds.clear();
        });
      }
      await _syncTrigger.request();
    } catch (error, stack) {
      developer.log(
        'batch_delete_failed request_id=${DateTime.now().microsecondsSinceEpoch}',
        name: 'diary.mutation',
        error: error,
        stackTrace: stack,
      );
      if (mounted) {
        setState(() => _errorMessage =
            '\u6279\u91cf\u5220\u9664\u672a\u5b8c\u6210\uff0c\u5df2\u4fdd\u7559\u672a\u5904\u7406\u65e5\u8bb0');
      }
    } finally {
      if (mounted) setState(() => _batchBusy = false);
    }
  }

  Future<void> _batchTagSelected() async {
    if (_batchBusy || _selectedDiaryIds.isEmpty) return;
    final all = await _store.getDiaries();
    if (!mounted) return;
    final availableTags = all.expand((diary) => diary.tags).toSet().toList()
      ..sort();
    final selection = await showBatchTagDialog(context,
        diaryCount: _selectedDiaryIds.length, availableTags: availableTags);
    if (selection == null || !mounted) return;
    final selectedIds = Set<String>.from(_selectedDiaryIds);
    setState(() => _batchBusy = true);
    try {
      final changed = await _sync.batchTagDiaries(
          selectedIds, selection.tags, selection.mode);
      if (!mounted) return;
      setState(() {
        _selectionMode = false;
        _selectedDiaryIds.clear();
        _errorMessage =
            '\u5df2\u66f4\u65b0 $changed \u7bc7\u65e5\u8bb0\u7684\u6807\u7b7e';
      });
      await _refreshLocalList();
      await _updatePendingCount();
      if (mounted) unawaited(_syncTrigger.request());
    } catch (error, stack) {
      developer.log(
          'batch_tag_failed request_id=${DateTime.now().microsecondsSinceEpoch}',
          name: 'diary.mutation',
          error: error,
          stackTrace: stack);
      if (mounted) {
        setState(() => _errorMessage =
            '\u6807\u7b7e\u66f4\u65b0\u672a\u63d0\u4ea4\uff0c\u5df2\u4fdd\u7559\u9009\u62e9\u4f9b\u91cd\u8bd5');
      }
    } finally {
      if (mounted) setState(() => _batchBusy = false);
    }
  }

  Future<void> _toggleDiary(Diary diary) async {
    if (_randomMode) {
      _randomToken++;
      _randomMode = false;
      _randomPlanner.clear();
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

  Future<bool> _playDiary(
    Diary diary, {
    bool fromRandomQueue = false,
  }) async {
    final request = ++_playRequest;
    await _playback.stop();
    if (!mounted || request != _playRequest) return false;
    setState(() {
      _playingDiaryId = diary.id;
      _errorMessage = null;
    });
    var completed = false;
    try {
      final asset = await _ensureAudio(diary);
      if (!mounted ||
          request != _playRequest ||
          (fromRandomQueue && !_randomMode)) {
        return false;
      }
      // Record one view event for the whole two-pass playback session.
      unawaited(_recordPlaybackView(diary));
      if (fromRandomQueue) {
        await _store.recordRandomSelection(diary.id);
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
        if (!mounted || request != _playRequest) return false;
        setState(() => _errorMessage = error is StateError &&
                error.message == 'Audio playback stalled'
            ? '\u97f3\u9891\u64ad\u653e\u65e0\u8fdb\u5ea6\uff0c\u8bf7\u68c0\u67e5\u8bbe\u5907\u97f3\u9891\u89e3\u7801\u6216\u91cd\u65b0\u540c\u6b65\u97f3\u9891'
            : '\u97f3\u9891\u65e0\u6cd5\u64ad\u653e\uff0c\u5c06\u8df3\u8fc7\u5f53\u524d\u65e5\u8bb0\u5e76\u7ee7\u7eed\u64ad\u653e');
      }
    } finally {
      if (mounted && request == _playRequest && _playingDiaryId == diary.id) {
        setState(() => _playingDiaryId = null);
      }
    }
    return completed;
  }

  Future<void> _openAdvancedSearch() async {
    final selected = await showAdvancedSearchDialog(context, _searchOptions);
    if (selected != null && mounted) {
      setState(() => _searchOptions = selected);
    }
  }

  Future<void> _openTransfer() async {
    await Navigator.of(context).push(MaterialPageRoute<void>(
      builder: (_) => DiaryTransferPage(
        store: _store,
        sync: _sync,
        onImported: () async {
          await _refreshLocalList();
          await _updatePendingCount();
          if (mounted) unawaited(_syncTrigger.request());
        },
      ),
    ));
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
    _randomPlanner.clear();
    _randomFailures.clear();
    if (mounted) {
      setState(() {
        _randomMode = false;
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
    final usage = await _store.getRandomUsage();
    if (!mounted || token != _randomToken) return;
    _randomPlanner.reset(candidates, usage: usage);
    _randomFailures.clear();
    if (mounted) {
      setState(() {
        _randomMode = true;
        _randomCurrent = null;
        _errorMessage = null;
      });
    }
    await _playNextRandom();
  }

  Future<void> _playNextRandom() async {
    final token = _randomToken;
    while (mounted && _randomMode && token == _randomToken) {
      final diary = _randomPlanner.takeNext();
      if (diary == null) {
        await _stopRandomPlayback();
        return;
      }
      if (mounted) setState(() => _randomCurrent = diary);
      _randomPlanner.replenish();
      unawaited(_prefetchRandomPlan());
      final completed = await _playDiary(diary, fromRandomQueue: true);
      if (!mounted || !_randomMode || token != _randomToken) return;
      if (completed) {
        _randomFailures.remove(diary.id);
      } else {
        final failures = (_randomFailures[diary.id] ?? 0) + 1;
        if (failures < 3) {
          _randomFailures[diary.id] = failures;
          _randomPlanner.requeue(diary);
        } else {
          _randomFailures.remove(diary.id);
          developer.log(
            'random_item_deferred request_id=${DateTime.now().microsecondsSinceEpoch} diary_id=${diary.id}',
            name: 'diary.playback',
          );
        }
      }
      _randomPlanner.replenish();
      unawaited(_prefetchRandomPlan());
    }
  }

  Future<void> _openEditor([Diary? diary]) async {
    if (diary != null) {
      try {
        await _sync.recordView(diary);
      } catch (error, stack) {
        developer.log(
          '查看记录失败 request_id=${DateTime.now().microsecondsSinceEpoch} diary_id=${diary.id}',
          name: 'diary.sync',
          error: error,
          stackTrace: stack,
        );
      } finally {
        await _updatePendingCount();
        await _refreshLocalList();
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
    if (mounted) await _syncTrigger.request();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed && _initialized) {
      unawaited(_syncTrigger.request());
    }
  }

  @override
  void dispose() {
    _randomPlanner.clear();
    _audioPrefetch.clear();
    WidgetsBinding.instance.removeObserver(this);
    unawaited(_syncTrigger.dispose());
    _randomToken++;
    _playRequest++;
    _subscription?.cancel();
    _api.dispose();
    unawaited(_store.close());
    unawaited(_playback.dispose());
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(
          title: Text(_selectionMode
              ? '\u5df2\u9009\u62e9 ${_selectedDiaryIds.length} \u7bc7'
              : '\u65e5\u8bb0'),
          leading: _selectionMode
              ? IconButton(
                  tooltip: '\u53d6\u6d88\u9009\u62e9',
                  onPressed: _cancelSelection,
                  icon: const Icon(Icons.close),
                )
              : null,
          actions: _selectionMode
              ? [
                  IconButton(
                    tooltip: '\u6279\u91cf\u6807\u7b7e',
                    onPressed: _batchBusy || _selectedDiaryIds.isEmpty
                        ? null
                        : _batchTagSelected,
                    icon: const Icon(Icons.label_outline),
                  ),
                  IconButton(
                    tooltip: '\u6279\u91cf\u5220\u9664',
                    onPressed: _batchBusy || _selectedDiaryIds.isEmpty
                        ? null
                        : _batchDeleteSelected,
                    icon: const Icon(Icons.delete_outline),
                  ),
                ]
              : [
                  IconButton(
                    tooltip: '\u5237\u65b0',
                    onPressed: _syncTrigger.request,
                    icon: const Icon(Icons.refresh),
                  ),
                  IconButton(
                    tooltip: '\u968f\u673a\u8fde\u7eed\u64ad\u653e',
                    onPressed: _playRandomCached,
                    icon: const Icon(Icons.shuffle),
                  ),
                  PopupMenuButton<String>(
                    tooltip: '\u66f4\u591a\u5de5\u5177',
                    icon: const Icon(Icons.more_vert),
                    onSelected: (action) {
                      if (action == 'search') {
                        _openAdvancedSearch();
                      } else if (action == 'transfer') {
                        _openTransfer();
                      } else if (action == 'server') {
                        _configureServer();
                      } else if (action == 'tags') {
                        Navigator.of(context).push(MaterialPageRoute(
                          builder: (_) => TagManagerPage(api: _api),
                        ));
                      } else if (action == 'trash') {
                        Navigator.of(context).push(MaterialPageRoute(
                          builder: (_) => TrashPage(api: _api),
                        ));
                      } else if (action == 'statistics') {
                        _openStatistics();
                      }
                    },
                    itemBuilder: (_) => const [
                      PopupMenuItem(
                          value: 'search',
                          child: Text('\u9ad8\u7ea7\u641c\u7d22')),
                      PopupMenuItem(
                          value: 'transfer',
                          child: Text('\u5bfc\u5165 / \u5bfc\u51fa')),
                      PopupMenuItem(
                          value: 'tags',
                          child: Text('\u6807\u7b7e\u7ba1\u7406')),
                      PopupMenuItem(
                          value: 'trash', child: Text('\u56de\u6536\u7ad9')),
                      PopupMenuItem(
                          value: 'statistics', child: Text('\u7edf\u8ba1')),
                      PopupMenuItem(
                          value: 'server',
                          child: Text('\u670d\u52a1\u5668\u8bbe\u7f6e')),
                    ],
                  ),
                ],
        ),
        floatingActionButton: FloatingActionButton(
          tooltip: '新建日记',
          onPressed: () => _openEditor(),
          child: const Icon(Icons.add),
        ),
        body: Column(children: [
          if (_errorMessage != null)
            MaterialBanner(content: Text(_errorMessage!), actions: [
              TextButton(
                  onPressed: _syncTrigger.request, child: const Text('重试'))
            ]),
          if (_syncing || _offline || _pendingCount > 0)
            SyncStatusBanner(
              offline: _offline,
              syncing: _syncing,
              pendingCount: _pendingCount,
            ),
          RandomPlaybackPanel(
            active: _randomMode,
            current: _randomCurrent,
            candidateCount: _randomPlanner.candidateCount,
            preparing: _randomCurrent != null &&
                _snapshot.stage == PlaybackStage.buffering,
            snapshot: _snapshot,
            onStart: _playRandomCached,
            onStop: _stopRandomPlayback,
          ),
          Expanded(
            child: DiaryListBody(
              diaries: _diaries,
              searchQuery: _searchQuery,
              searchOptions: _searchOptions,
              selectedTag: _selectedTag,
              playingDiaryId: _playingDiaryId,
              snapshot: _snapshot,
              onSearch: (text) => setState(() => _searchQuery = text),
              onTag: (tag) => setState(() => _selectedTag = tag),
              onRefresh: _syncTrigger.request,
              selectionMode: _selectionMode,
              selectedIds: _selectedDiaryIds,
              onToggleSelection: _toggleSelection,
              onOpen: (diary) => _openEditor(diary),
              onPlay: _toggleDiary,
            ),
          ),
        ]),
      );
}
