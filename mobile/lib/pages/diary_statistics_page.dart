import 'dart:developer' as developer;

import 'package:flutter/material.dart';

import '../localization/app_strings.dart';
import '../models/diary.dart';
import '../models/server_daily_statistics.dart';
import '../models/server_statistics.dart';
import '../services/diary_api.dart';
import '../services/diary_statistics.dart';
import '../services/local_store.dart';
import '../statistics/device_view_repository.dart';
import '../statistics/monthly_diary_heatmap.dart';
import '../statistics/server_daily_cache.dart';

class DiaryStatisticsPage extends StatefulWidget {
  const DiaryStatisticsPage({
    super.key,
    required this.diaries,
    required this.api,
    required this.store,
    this.dailyCache,
  });

  final List<Diary> diaries;
  final DiaryApi api;
  final LocalStore store;
  final ServerDailyCache? dailyCache;

  @override
  State<DiaryStatisticsPage> createState() => _DiaryStatisticsPageState();
}

class _DiaryStatisticsPageState extends State<DiaryStatisticsPage> {
  ServerStatistics? _server;
  ServerDailyStatistics? _serverDaily;
  DateTime? _dailyFetchedAt;
  bool _dailyFromCache = false;
  DeviceViewHistory? _history;
  late DateTime _month;
  bool _loadingServer = true;
  bool _loadingMonth = true;
  bool _serverUnavailable = false;
  bool _serverDailyUnavailable = false;
  bool _monthUnavailable = false;
  int _serverRequest = 0;
  int _monthRequest = 0;

  @override
  void initState() {
    super.initState();
    final now = DateTime.now();
    _month = DateTime(now.year, now.month);
    _loadServerStatistics();
    _loadMonth();
  }

  Future<void> _loadServerStatistics() async {
    final request = ++_serverRequest;
    setState(() => _loadingServer = true);
    try {
      final result = await widget.api.fetchStatistics();
      if (!mounted || request != _serverRequest) return;
      setState(() {
        _server = result;
        _serverUnavailable = false;
      });
    } catch (error, stack) {
      developer.log(
        'server_summary_failed request_id=${DateTime.now().microsecondsSinceEpoch}',
        name: 'diary.statistics',
        error: error,
        stackTrace: stack,
      );
      if (mounted && request == _serverRequest) {
        setState(() => _serverUnavailable = true);
      }
    } finally {
      if (mounted && request == _serverRequest) {
        setState(() => _loadingServer = false);
      }
    }
  }

  Future<void> _loadMonth() async {
    final request = ++_monthRequest;
    final month = _month;
    final start = DateTime(month.year, month.month);
    final end = DateTime(month.year, month.month + 1, 0);
    setState(() {
      _loadingMonth = true;
      _serverDaily = null;
      _dailyFetchedAt = null;
      _dailyFromCache = false;
      _serverDailyUnavailable = false;
      _history = null;
      _monthUnavailable = false;
    });
    try {
      final local = await widget.store.getDeviceViewHistory(month);
      if (mounted && request == _monthRequest) {
        setState(() => _history = local);
      }
    } catch (error, stack) {
      developer.log(
        'device_history_failed request_id=${DateTime.now().microsecondsSinceEpoch}',
        name: 'diary.statistics',
        error: error,
        stackTrace: stack,
      );
      if (mounted && request == _monthRequest) {
        setState(() => _monthUnavailable = true);
      }
    }
    final cache = widget.dailyCache ?? ServerDailyCache(widget.store);
    try {
      final stored = await cache.load(widget.api.cacheScope, start, end);
      if (stored != null && mounted && request == _monthRequest) {
        setState(() {
          _serverDaily = stored.statistics;
          _dailyFetchedAt = stored.fetchedAt;
          _dailyFromCache = true;
        });
      }
    } catch (error, stack) {
      developer.log(
        'server_daily_cache_read_failed request_id=${DateTime.now().microsecondsSinceEpoch}',
        name: 'diary.statistics',
        error: error,
        stackTrace: stack,
      );
    }
    try {
      final daily = await widget.api.fetchDailyStatistics(
        start: start,
        end: end,
      );
      final fetchedAt = DateTime.now().toUtc();
      if (mounted && request == _monthRequest) {
        setState(() {
          _serverDaily = daily;
          _dailyFetchedAt = fetchedAt;
          _dailyFromCache = false;
          _serverDailyUnavailable = false;
        });
        try {
          await cache.save(widget.api.cacheScope, start, end, daily,
              fetchedAt: fetchedAt);
        } catch (error, stack) {
          developer.log(
            'server_daily_cache_write_failed request_id=${DateTime.now().microsecondsSinceEpoch}',
            name: 'diary.statistics',
            error: error,
            stackTrace: stack,
          );
        }
      }
    } catch (error, stack) {
      developer.log(
        'server_daily_statistics_failed request_id=${DateTime.now().microsecondsSinceEpoch}',
        name: 'diary.statistics',
        error: error,
        stackTrace: stack,
      );
      if (mounted && request == _monthRequest) {
        setState(() => _serverDailyUnavailable = true);
      }
    } finally {
      if (mounted && request == _monthRequest) {
        setState(() => _loadingMonth = false);
      }
    }
  }

  Future<void> _showDate(String date) async {
    final cached = widget.diaries
        .where((diary) => diary.date.startsWith(date))
        .toList(growable: false);
    final remoteFuture = widget.api.fetchDiariesByDate(date).catchError(
      (Object error, StackTrace stack) {
        developer.log(
          'calendar_diaries_failed request_id=${DateTime.now().microsecondsSinceEpoch}',
          name: 'diary.statistics',
          error: error,
          stackTrace: stack,
        );
        Error.throwWithStackTrace(error, stack);
      },
    );
    if (!mounted) return;
    final strings = AppStrings.of(context);
    await showDialog<void>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(strings.dateLabel(date)),
        content: SizedBox(
          width: double.maxFinite,
          child: ListView(shrinkWrap: true, children: [
            Text(strings.localCacheCount(cached.length)),
            ...cached.map((diary) => ListTile(
                  dense: true,
                  title: Text(diary.content),
                  subtitle: Text(strings.viewed(diary.viewCount)),
                )),
            if (cached.isEmpty) Text(strings.localNoDateDiaries),
            FutureBuilder<List<Diary>>(
              future: remoteFuture,
              builder: (context, snapshot) {
                if (snapshot.hasError) {
                  return Text(strings.serverDateUnavailable);
                }
                if (!snapshot.hasData) {
                  return Text(strings.loadingCalendarDate);
                }
                final remote = snapshot.data!;
                return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(strings.serverCount(remote.length)),
                    ...remote.map((diary) => ListTile(
                          dense: true,
                          title: Text(diary.content),
                          subtitle: Text(strings.serverHistoryDetails),
                        )),
                  ],
                );
              },
            ),
          ]),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: Text(strings.close),
          ),
        ],
      ),
    );
  }

  void _changeMonth(int offset) {
    setState(() => _month = DateTime(_month.year, _month.month + offset));
    _loadMonth();
  }

  void _refresh() {
    _loadServerStatistics();
    _loadMonth();
  }

  @override
  Widget build(BuildContext context) {
    final strings = AppStrings.of(context);
    final local = calculateDiaryStatistics(widget.diaries);
    final sortedTags = local.tagCounts.entries.toList()
      ..sort((a, b) => b.value.compareTo(a.value));
    final deviceDays = _history?.dailyCounts.entries.toList()
      ?..sort((a, b) => a.key.compareTo(b.key));
    return Scaffold(
      appBar: AppBar(
        title: Text(strings.statsTitle),
        actions: [
          IconButton(
            tooltip: strings.refresh,
            onPressed: _refresh,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        if (_loadingServer || _loadingMonth) const LinearProgressIndicator(),
        Text(strings.serverSummary,
            style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
        const SizedBox(height: 8),
        if (_serverUnavailable)
          Text(_server == null
              ? strings.serverCacheFallback
              : strings.serverPreviousFallback),
        if (_server == null && !_serverUnavailable && _loadingServer)
          Text(strings.loadingServerSummary),
        if (_server != null) ...[
          _StatCard(
            label: strings.serverDiaries,
            value: strings.count(_server!.totalDiaries, strings.diaryUnit),
          ),
          _StatCard(
            label: strings.serverViews,
            value: strings.count(_server!.totalViews, strings.timesUnit),
          ),
          _StatCard(
            label: strings.serverAverageViews,
            value: _server!.averageViews.toStringAsFixed(1),
          ),
          _StatCard(
            label: strings.mostViewed,
            value: strings.count(_server!.mostViewedCount, strings.timesUnit),
          ),
          _StatCard(
            label: strings.leastViewed,
            value: strings.count(_server!.leastViewedCount, strings.timesUnit),
          ),
        ],
        const Divider(height: 28),
        Text(strings.serverDailyDetails,
            style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
        if (_serverDailyUnavailable && _serverDaily == null)
          Text(strings.dailyUnavailable)
        else if (_serverDaily == null)
          Text(strings.loadingDaily)
        else ...[
          if (_serverDailyUnavailable) Text(strings.dailyCacheHint),
          if (_dailyFetchedAt != null)
            Text(_dailyFromCache
                ? strings.dailyCacheAt(_dailyFetchedAt!)
                : strings.dailyLiveAt(_dailyFetchedAt!)),
          _StatCard(
            label: strings.serverDailyEvents,
            value: strings.count(_serverDaily!.totalEvents, strings.timesUnit),
          ),
          _StatCard(
            label: strings.activeDays,
            value: strings.count(_serverDaily!.activeDays, strings.dayUnit),
          ),
          if (_serverDaily!.yesterdayDate == null ||
              _serverDaily!.yesterdayTotalViews == null ||
              _serverDaily!.bestDayViews == null)
            Text(strings.dailyHistoryUnavailable),
          if (_serverDaily!.yesterdayDate != null &&
              _serverDaily!.yesterdayTotalViews != null)
            _StatCard(
              label:
                  '${strings.yesterdayServerViews} · ${_serverDaily!.yesterdayDate}',
              value: strings.count(
                  _serverDaily!.yesterdayTotalViews!, strings.timesUnit),
            ),
          if (_serverDaily!.bestDayViews != null)
            _StatCard(
              label: strings.bestServerDay,
              value: strings.bestServerDayValue(
                  _serverDaily!.bestDayDate, _serverDaily!.bestDayViews!),
            ),
        ],
        const Divider(height: 28),
        Text(strings.deviceCache,
            style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
        const SizedBox(height: 8),
        Text(strings.deviceCacheNote),
        _StatCard(
          label: strings.cachedDiaries,
          value: strings.count(local.total, strings.diaryUnit),
        ),
        _StatCard(
          label: strings.contentCharacters,
          value: strings.count(local.totalCharacters, strings.characterUnit),
        ),
        _StatCard(
          label: strings.cachedViews,
          value: strings.count(local.totalViews, strings.timesUnit),
        ),
        _StatCard(
          label: strings.activeDays,
          value: strings.count(local.activeDays, strings.dayUnit),
        ),
        _StatCard(
            label: strings.latestDate,
            value: local.latestDate ?? strings.noData),
        const SizedBox(height: 16),
        Text(strings.tagUsage,
            style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
        if (sortedTags.isEmpty)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 12),
            child: Text(strings.noTags),
          )
        else
          ...sortedTags.map((entry) => ListTile(
                dense: true,
                leading: const Icon(Icons.label_outline),
                title: Text(entry.key),
                trailing: Text(strings.count(entry.value, strings.diaryUnit)),
              )),
        const SizedBox(height: 16),
        Text(strings.longestDiary,
            style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
        ListTile(
          title: Text(local.longestContent?.date ?? strings.noData),
          subtitle: Text(local.longestContent?.content ?? strings.noCachedDiary,
              maxLines: 4, overflow: TextOverflow.ellipsis),
        ),
        const Divider(height: 28),
        Text(strings.heatmap,
            style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
        Row(children: [
          IconButton(
            tooltip: strings.previousMonth,
            onPressed: () => _changeMonth(-1),
            icon: const Icon(Icons.chevron_left),
          ),
          Expanded(
            child: Center(
                child: Text(strings.monthLabel(_month.year, _month.month))),
          ),
          IconButton(
            tooltip: strings.nextMonth,
            onPressed: () => _changeMonth(1),
            icon: const Icon(Icons.chevron_right),
          ),
        ]),
        if (_monthUnavailable)
          Text(strings.deviceRecordsUnavailable)
        else if (_history == null)
          Text(strings.loadingDeviceRecords)
        else ...[
          _StatCard(
            label: strings.serverDailyDetails,
            value: strings.count(_history!.totalEvents, strings.timesUnit),
          ),
          _StatCard(
            label: strings.pendingSync,
            value: strings.count(_history!.pendingEvents, strings.timesUnit),
          ),
          MonthlyDiaryHeatmap(
            month: _month,
            deviceViews: _history!.dailyCounts,
            serverViews: _serverDaily?.dailyCounts ?? const {},
            cachedDiaries: cachedDiaryDays(widget.diaries, _month),
            onDateTap: _showDate,
          ),
          if (deviceDays == null || deviceDays.isEmpty)
            Text(strings.noDeviceEvents)
          else
            ...deviceDays.map((entry) => ListTile(
                  dense: true,
                  title: Text(entry.key),
                  trailing: Text(strings.deviceEventCount(entry.value)),
                )),
        ],
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 12),
          child: Text(strings.statisticsSourceNote),
        ),
      ]),
    );
  }
}

class _StatCard extends StatelessWidget {
  const _StatCard({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) => Card(
        child: ListTile(
          title: Text(label),
          trailing:
              Text(value, style: const TextStyle(fontWeight: FontWeight.bold)),
        ),
      );
}
