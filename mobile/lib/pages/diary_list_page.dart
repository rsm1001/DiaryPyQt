import 'dart:async';
import 'dart:developer' as developer;
import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import '../config/app_config.dart';
import '../localization/app_strings.dart';
import '../deletion/random_deletion_page.dart';
import '../conflicts/conflict_review_page.dart';
import '../models/app_preferences.dart';
import '../models/audio_asset.dart';
import '../models/diary.dart';
import '../playback/audio_request_registry.dart';
import '../playback/playback_resume_dialog.dart';
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
import '../services/app_preferences_store.dart';
import '../settings/app_preferences_navigation.dart';
import '../services/sync_manager.dart';
import '../services/sync_trigger.dart';
import '../services/random_playback_plan.dart';
import '../widgets/diary_list_body.dart';
import '../widgets/random_playback_panel.dart';
import '../widgets/sync_status_banner.dart';
import '../voice/voice_selection_page.dart';

class DiaryListPage extends StatefulWidget {
  const DiaryListPage({
    super.key,
    this.preferences = AppPreferences.defaults,
    this.onPreferencesChanged,
  });

  final AppPreferences preferences;
  final ValueChanged<AppPreferences>? onPreferencesChanged;

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
    shouldRetry: (error) =>
        error is! DiaryApiException ||
        (!error.conflict &&
            (error.statusCode == null || error.statusCode! >= 500)),
    onOfflineChanged: (offline) {
      if (mounted) setState(() => _offline = offline);
    },
  );
  bool _initialized = false;
  bool _offline = false;
  bool _syncing = false;
  int _pendingCount = 0;
  bool _requiresServerCredentials = false;
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
  String _voiceId = '', _audioStatus = '';
  String _playingVoiceId = '';
  DateTime? _lastPlaybackPersistedAt;
  String _lastPlaybackPersistKey = '';
  String _searchQuery = '';
  DiarySearchOptions _searchOptions = const DiarySearchOptions();
  String? _selectedTag;
  final _randomPlanner = RandomPlaybackPlanner();
  Diary? _randomCurrent;
  bool _randomMode = false;
  int _randomToken = 0;
  bool _randomLoopRunning = false;
  int _playRequest = 0;
  final _audioRequests = AudioRequestRegistry();
  final Set<String> _selectedDiaryIds = {};
  bool _selectionMode = false;
  bool _batchBusy = false;
  late AppPreferences _preferences = widget.preferences;
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _diaries = _initialize();
    _subscription = _playback.stateStream.listen((snapshot) {
      if (mounted) setState(() => _snapshot = snapshot);
      unawaited(_persistPlayback(snapshot));
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
    _voiceId = await _store.selectedVoice(_serverUrl) ?? '';
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
          setState(
              () => _errorMessage = AppStrings.of(context).pendingServerChange);
        }
        candidate.dispose();
        return;
      }
      await _store.saveServerUrl(url);
      final selectedVoice = await _store.selectedVoice(url) ?? '';
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
        _voiceId = selectedVoice;
        _audioRequests.clear();
        _savedPassword = password;
        _api = candidate;
        _sync = SyncManager(api: _api, store: _store);
        _errorMessage = null;
        _requiresServerCredentials = false;
      });
      await _syncTrigger.request();
      previous.dispose();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(AppStrings.of(context).connectionVerified)));
      }
    } catch (error, stack) {
      developer.log(
        '日记服务器连接失败 request_id=${DateTime.now().microsecondsSinceEpoch}',
        name: 'diary.sync',
        error: error,
        stackTrace: stack,
      );
      if (mounted) {
        setState(() {
          _requiresServerCredentials =
              error is DiaryApiException && error.statusCode == 401;
          _errorMessage = _requiresServerCredentials
              ? AppStrings.of(context).syncFailure(
                  conflict: false, pending: _pendingCount, statusCode: 401)
              : AppStrings.of(context).connectionValidationFailed;
        });
      }
      if (!identical(candidate, _api)) candidate.dispose();
    }
  }

  Future<List<Diary>> _loadDiaries({bool rethrowOnFailure = false}) async {
    final local = await _sync.loadLocal();
    try {
      final remote = await _sync.refresh();
      if (mounted) {
        setState(() {
          _errorMessage = null;
          _requiresServerCredentials = false;
        });
      }
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
          final statusCode =
              error is DiaryApiException ? error.statusCode : null;
          _requiresServerCredentials = statusCode == 401 || statusCode == 403;
          _errorMessage = AppStrings.of(context).syncFailure(
              conflict: error is DiaryApiException && error.conflict,
              pending: pending,
              statusCode: statusCode);
        });
      }
      if (rethrowOnFailure) {
        if (mounted) setState(() => _diaries = Future.value(local));
        Error.throwWithStackTrace(error, stack);
      }
      _syncTrigger.scheduleRetry(error);
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

  String _playbackStatus(PlaybackStage stage) => switch (stage) {
        PlaybackStage.playingFirst || PlaybackStage.playingSecond => 'playing',
        PlaybackStage.paused => 'paused',
        PlaybackStage.waiting => 'waiting',
        PlaybackStage.completed => 'completed',
        PlaybackStage.buffering => 'playing',
        PlaybackStage.idle => 'skipped',
      };

  Future<void> _persistPlayback(PlaybackSnapshot snapshot) async {
    final diaryId = snapshot.diaryId;
    if (diaryId == null ||
        _playingVoiceId.isEmpty ||
        snapshot.stage == PlaybackStage.idle) {
      return;
    }
    final positionMs = snapshot.position.inMilliseconds;
    final status = _playbackStatus(snapshot.stage);
    final key =
        '$diaryId|$_playingVoiceId|${snapshot.roundNumber}|$status|${positionMs ~/ 1000}';
    final now = DateTime.now();
    if (key == _lastPlaybackPersistKey &&
        (now.difference(_lastPlaybackPersistedAt ?? DateTime(1970)))
                .inMilliseconds <
            800 &&
        status != 'paused' &&
        status != 'completed') {
      return;
    }
    _lastPlaybackPersistKey = key;
    _lastPlaybackPersistedAt = now;
    try {
      await _sync.savePlaybackRecord(
        diaryId: diaryId,
        voiceId: _playingVoiceId,
        roundNumber: snapshot.roundNumber,
        positionMs: positionMs,
        status: status,
      );
    } catch (error, stack) {
      developer.log(
        '播放记录本地保存失败 request_id=${DateTime.now().microsecondsSinceEpoch}',
        name: 'diary.playback',
        error: error,
        stackTrace: stack,
      );
    }
  }

  Future<(int, Duration)?> _askPlaybackResume(
      String diaryId, String voiceId, int durationMs) async {
    var record = await _sync.localPlayback(diaryId, voiceId);
    record ??= await _sync.remotePlayback(diaryId, voiceId);
    if (record == null ||
        record.status == 'completed' ||
        record.positionMs <= 0 ||
        record.positionMs >= durationMs) {
      return null;
    }
    if (!mounted) return null;
    final resume = await showPlaybackResumeDialog(context, record);
    return resume == true
        ? (record.roundNumber, Duration(milliseconds: record.positionMs))
        : null;
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

  String _audioKey(Diary diary) =>
      [diary.id, diary.contentHash, _voiceId].join('|');
  Future<AudioAsset> _ensureAudio(Diary diary, {bool foreground = false}) {
    final key = _audioKey(diary);
    return _audioRequests.ensure(
      key,
      (reportStatus) => _sync.ensureAudio(
        diary,
        voiceId: _voiceId,
        onStatus: reportStatus,
      ),
      onStatus: foreground
          ? (status) {
              if (mounted &&
                  _playingDiaryId == diary.id &&
                  _audioKey(diary) == key) {
                setState(() => _audioStatus =
                    AppStrings.of(context).audioCacheStatus(status));
              }
            }
          : null,
    );
  }

  void _onSyncError(Object error, StackTrace stack) {
    developer.log(
      '本地同步状态失败 request_id=${DateTime.now().microsecondsSinceEpoch}',
      name: 'diary.sync',
      error: error,
      stackTrace: stack,
    );
    if (mounted && _errorMessage == null) {
      setState(() => _errorMessage = AppStrings.of(context).syncStateFailed);
    }
  }

  Future<void> _performRefresh() async {
    if (!mounted) return;
    setState(() => _syncing = true);
    try {
      final diaries = await _loadDiaries(rethrowOnFailure: true);
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
    final strings = AppStrings.of(context);
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(strings.batchDeleteDiariesTitle),
        content:
            Text(strings.batchDeleteDiariesConfirm(_selectedDiaryIds.length)),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: Text(strings.cancel),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(dialogContext, true),
            child: Text(strings.deleteAction),
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
        setState(
            () => _errorMessage = AppStrings.of(context).batchDeleteFailed);
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
        _errorMessage = AppStrings.of(context).batchTagsUpdated(changed);
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
        setState(() => _errorMessage = AppStrings.of(context).batchTagsFailed);
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
      _audioStatus = AppStrings.of(context).preparingPlayback;
      _errorMessage = null;
    });
    var completed = false;
    try {
      final audioKey = _audioKey(diary);
      final asset = await _ensureAudio(diary, foreground: true);
      _audioRequests.clearStatusListener(audioKey);
      if (mounted && request == _playRequest) {
        setState(() => _audioStatus = '');
      }
      _playingVoiceId = asset.voiceId;
      if (fromRandomQueue && mounted && request == _playRequest) {
        setState(() => _randomCurrent = diary);
      }
      // 随机播放不弹出历史恢复提示，避免队列等待用户操作。
      final resume = fromRandomQueue
          ? null
          : await _askPlaybackResume(diary.id, asset.voiceId, asset.durationMs);
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
          asset: asset,
          initialRound: resume == null ? 1 : resume.$1,
          initialPosition: resume == null ? Duration.zero : resume.$2);
    } catch (error, stack) {
      developer.log(
          'audio_playback_failed request_id=${DateTime.now().microsecondsSinceEpoch} diary_id=${diary.id}',
          name: 'diary.playback',
          error: error,
          stackTrace: stack);
      if (mounted && request == _playRequest) {
        await _playback.stop();
        if (!mounted || request != _playRequest) return false;
        setState(() => _errorMessage =
            error is StateError && error.message == 'Audio playback stalled'
                ? AppStrings.of(context).playbackStalled
                : AppStrings.of(context).playbackFailed);
      }
    } finally {
      _audioRequests.clearStatusListener(_audioKey(diary));
      if (mounted && request == _playRequest && _playingDiaryId == diary.id) {
        setState(() => _audioStatus = '');
        setState(() => _playingDiaryId = null);
      }
    }
    return completed;
  }

  Future<void> _openAdvancedSearch() async {
    final tags = (await _store.getDiaries())
        .expand((diary) => diary.tags)
        .toSet()
        .toList()
      ..sort();
    if (!mounted) return;
    final selected = await showAdvancedSearchDialog(context, _searchOptions,
        availableTags: tags);
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

  Future<void> _openSettings() async {
    final updated = await openAppPreferences(
      context,
      initial: _preferences,
      save: _store.saveAppPreferences,
    );
    if (updated == null || !mounted) return;
    setState(() => _preferences = updated);
    widget.onPreferencesChanged?.call(updated);
  }

  Future<void> _openStatistics() async {
    final diaries = await _store.getDiaries();
    if (!mounted) return;
    await Navigator.of(context).push(MaterialPageRoute(
        builder: (_) =>
            DiaryStatisticsPage(diaries: diaries, api: _api, store: _store)));
  }

  Future<void> _stopRandomPlayback() async {
    _randomToken++;
    _playRequest++;
    _randomPlanner.clear();
    if (mounted) {
      setState(() {
        _randomMode = false;
        _randomCurrent = null;
        _playingDiaryId = null;
        _audioStatus = '';
      });
    }
    await _playback.stop();
  }

  Future<void> _playRandomCached() async {
    if (_randomLoopRunning) return;
    _randomLoopRunning = true;
    try {
      final token = ++_randomToken;
      _playRequest++;
      final diaries = await _store.getDiaries();
      if (!mounted || token != _randomToken) return;
      final candidates = filterDiaries(diaries, _searchQuery, _selectedTag,
          options: _searchOptions);
      if (candidates.isEmpty) {
        if (mounted) {
          setState(() =>
              _errorMessage = AppStrings.of(context).noRandomPlaybackCandidate);
        }
        return;
      }
      await _playback.stop();
      if (!mounted || token != _randomToken) return;
      final usage = await _store.getRandomUsage();
      if (!mounted || token != _randomToken) return;
      _randomPlanner.reset(candidates, usage: usage);
      if (mounted) {
        setState(() {
          _randomMode = true;
          _randomCurrent = null;
          _errorMessage = null;
        });
      }
      await _playNextRandom();
    } finally {
      _randomLoopRunning = false;
    }
  }

  Future<void> _playNextRandom() async {
    final token = _randomToken;
    while (mounted && _randomMode && token == _randomToken) {
      final diary = _randomPlanner.takeNext();
      if (diary == null) {
        await _stopRandomPlayback();
        return;
      }
      _randomPlanner.replenish();
      final completed = await _playDiary(diary, fromRandomQueue: true);
      if (!mounted || !_randomMode || token != _randomToken) return;
      if (!completed) {
        await _stopRandomPlayback();
        return;
      }
      _randomPlanner.replenish();
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
    _audioRequests.clear();
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
  Widget build(BuildContext context) {
    final strings = AppStrings.of(context);
    return Scaffold(
      appBar: AppBar(
        title: Text(_selectionMode
            ? strings.selectedCount(_selectedDiaryIds.length)
            : strings.diary),
        leading: _selectionMode
            ? IconButton(
                tooltip: strings.cancel,
                onPressed: _cancelSelection,
                icon: const Icon(Icons.close),
              )
            : null,
        actions: _selectionMode
            ? [
                IconButton(
                  tooltip: strings.batchTag,
                  onPressed: _batchBusy || _selectedDiaryIds.isEmpty
                      ? null
                      : _batchTagSelected,
                  icon: const Icon(Icons.label_outline),
                ),
                IconButton(
                  tooltip: strings.batchDelete,
                  onPressed: _batchBusy || _selectedDiaryIds.isEmpty
                      ? null
                      : _batchDeleteSelected,
                  icon: const Icon(Icons.delete_outline),
                ),
              ]
            : [
                IconButton(
                  tooltip: strings.refresh,
                  onPressed: _syncTrigger.request,
                  icon: const Icon(Icons.refresh),
                ),
                IconButton(
                  tooltip: strings.playRandom,
                  onPressed: _playRandomCached,
                  icon: const Icon(Icons.shuffle),
                ),
                PopupMenuButton<String>(
                  tooltip: strings.moreTools,
                  icon: const Icon(Icons.more_vert),
                  onSelected: (action) async {
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
                        builder: (_) => TrashPage(
                            api: _api,
                            sync: _sync,
                            onChanged: _refreshLocalList),
                      ));
                    } else if (action == 'voices') {
                      final selected = await Navigator.of(context).push<String>(
                          MaterialPageRoute(
                              builder: (_) => VoiceSelectionPage(
                                  api: _api,
                                  store: _store,
                                  serverUrl: _serverUrl,
                                  currentVoiceId: _voiceId)));
                      if (selected != null && mounted && selected != _voiceId) {
                        await _stopRandomPlayback();
                        if (mounted) {
                          setState(() {
                            _voiceId = selected;
                            _audioRequests.clear();
                          });
                        }
                      }
                    } else if (action == 'conflicts') {
                      Navigator.of(context).push(MaterialPageRoute(
                          builder: (_) => ConflictReviewPage(
                              sync: _sync,
                              onResolved: () async {
                                await _refreshLocalList();
                                await _updatePendingCount();
                                if (mounted) {
                                  unawaited(_syncTrigger.request());
                                }
                              })));
                    } else if (action == 'random_delete') {
                      await RandomDeletionPage.open(context,
                          store: _store, sync: _sync, onChanged: () async {
                        await _refreshLocalList();
                        await _updatePendingCount();
                      });
                    } else if (action == 'statistics') {
                      _openStatistics();
                    } else if (action == 'settings') {
                      _openSettings();
                    }
                  },
                  itemBuilder: (_) => [
                    PopupMenuItem(value: 'search', child: Text(strings.search)),
                    PopupMenuItem(
                        value: 'transfer', child: Text(strings.transfer)),
                    PopupMenuItem(value: 'tags', child: Text(strings.tags)),
                    PopupMenuItem(value: 'trash', child: Text(strings.trash)),
                    PopupMenuItem(value: 'voices', child: Text(strings.voices)),
                    PopupMenuItem(
                        value: 'conflicts', child: Text(strings.conflicts)),
                    PopupMenuItem(
                        value: 'random_delete',
                        child: Text(strings.randomDelete)),
                    PopupMenuItem(
                        value: 'statistics', child: Text(strings.statistics)),
                    PopupMenuItem(
                        value: 'settings', child: Text(strings.preferences)),
                    PopupMenuItem(
                        value: 'server', child: Text(strings.serverSettings)),
                  ],
                ),
              ],
      ),
      floatingActionButton: FloatingActionButton(
        tooltip: strings.newDiary,
        onPressed: () => _openEditor(),
        child: const Icon(Icons.add),
      ),
      body: Column(children: [
        if (_errorMessage != null)
          MaterialBanner(content: Text(_errorMessage!), actions: [
            TextButton(
                onPressed: _requiresServerCredentials
                    ? _configureServer
                    : _syncTrigger.request,
                child: Text(_requiresServerCredentials
                    ? strings.serverSettings
                    : strings.retry))
          ]),
        if (_syncing || _offline || _pendingCount > 0)
          SyncStatusBanner(
            offline: _offline,
            syncing: _syncing,
            pendingCount: _pendingCount,
          ),
        if (_audioStatus.isNotEmpty)
          Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Text(_audioStatus)),
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
            preferences: _preferences,
            onSearch: (text) => setState(() => _searchQuery = text),
            onTag: (tag) => setState(() => _selectedTag = tag),
            onClearFilters: () => setState(() {
              _searchQuery = '';
              _selectedTag = null;
              _searchOptions = const DiarySearchOptions();
            }),
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
}
