import 'dart:developer' as developer;

import 'package:flutter/material.dart';

import '../models/diary.dart';
import '../models/server_daily_statistics.dart';
import '../models/server_statistics.dart';
import '../services/diary_api.dart';
import '../services/diary_statistics.dart';
import '../services/local_store.dart';
import '../statistics/device_view_repository.dart';
import '../statistics/monthly_diary_heatmap.dart';

class DiaryStatisticsPage extends StatefulWidget {
  const DiaryStatisticsPage({
    super.key,
    required this.diaries,
    required this.api,
    required this.store,
  });

  final List<Diary> diaries;
  final DiaryApi api;
  final LocalStore store;

  @override
  State<DiaryStatisticsPage> createState() => _DiaryStatisticsPageState();
}

class _DiaryStatisticsPageState extends State<DiaryStatisticsPage> {
  ServerStatistics? _server;
  ServerDailyStatistics? _serverDaily;
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
          '服务器汇总读取失败 request_id=${DateTime.now().microsecondsSinceEpoch}',
          name: 'diary.statistics',
          error: error,
          stackTrace: stack);
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
      _serverDailyUnavailable = false;
      _history = null;
      _monthUnavailable = false;
    });
    try {
      final local = await widget.store.getDeviceViewHistory(month);
      if (mounted && request == _monthRequest) setState(() => _history = local);
    } catch (error, stack) {
      developer.log(
          '本设备查看记录读取失败 request_id=${DateTime.now().microsecondsSinceEpoch}',
          name: 'diary.statistics',
          error: error,
          stackTrace: stack);
      if (mounted && request == _monthRequest) {
        setState(() => _monthUnavailable = true);
      }
    }
    try {
      final daily =
          await widget.api.fetchDailyStatistics(start: start, end: end);
      if (mounted && request == _monthRequest) {
        setState(() => _serverDaily = daily);
      }
    } catch (error, stack) {
      developer.log(
          '服务器每日统计读取失败 request_id=${DateTime.now().microsecondsSinceEpoch}',
          name: 'diary.statistics',
          error: error,
          stackTrace: stack);
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
    List<Diary> remote = const [];
    var remoteUnavailable = false;
    try {
      remote = await widget.api.fetchDiariesByDate(date);
    } catch (error, stack) {
      remoteUnavailable = true;
      developer.log(
          '日期日记读取失败 request_id=${DateTime.now().microsecondsSinceEpoch}',
          name: 'diary.statistics',
          error: error,
          stackTrace: stack);
    }
    if (!mounted) return;
    await showDialog<void>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text('日期：$date'),
        content: SizedBox(
          width: double.maxFinite,
          child: ListView(shrinkWrap: true, children: [
            Text('本地缓存：${cached.length} 篇'),
            ...cached.map((diary) => ListTile(
                  dense: true,
                  title: Text(diary.content),
                  subtitle: Text('查看 ${diary.viewCount} 次'),
                )),
            if (cached.isEmpty) const Text('本地没有缓存该日期的日记。'),
            Text('服务器：${remote.length} 篇'),
            ...remote.map((diary) => ListTile(
                  dense: true,
                  title: Text(diary.content),
                  subtitle: const Text('服务器历史明细'),
                )),
            if (remoteUnavailable) const Text('服务器日期明细暂不可用。'),
          ]),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('关闭'),
          )
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
    final local = calculateDiaryStatistics(widget.diaries);
    final sortedTags = local.tagCounts.entries.toList()
      ..sort((a, b) => b.value.compareTo(a.value));
    final deviceDays = _history?.dailyCounts.entries.toList()
      ?..sort((a, b) => a.key.compareTo(b.key));
    return Scaffold(
      appBar: AppBar(title: const Text('统计与日期分布'), actions: [
        IconButton(
            tooltip: '刷新统计',
            onPressed: _refresh,
            icon: const Icon(Icons.refresh)),
      ]),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        if (_loadingServer || _loadingMonth) const LinearProgressIndicator(),
        const Text('服务器汇总',
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
        const SizedBox(height: 8),
        if (_serverUnavailable)
          Text(_server == null
              ? '服务器统计不可用；以下展示本设备可读取的缓存数据。'
              : '服务器暂不可用；以下汇总为上次成功获取的结果，并非实时数据。'),
        if (_server == null && !_serverUnavailable && _loadingServer)
          const Text('正在获取服务器汇总……'),
        if (_server != null) ...[
          _StatCard(label: '服务器日记', value: '${_server!.totalDiaries} 篇'),
          _StatCard(label: '服务器查看次数', value: '${_server!.totalViews} 次'),
          _StatCard(
              label: '服务器平均查看',
              value: _server!.averageViews.toStringAsFixed(1)),
          _StatCard(label: '最多查看', value: '${_server!.mostViewedCount} 次'),
          _StatCard(label: '最少查看', value: '${_server!.leastViewedCount} 次'),
        ],
        const Divider(height: 28),
        const Text('服务器历史日期明细',
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
        if (_serverDailyUnavailable)
          const Text('服务器每日明细暂不可用；不使用本设备事件替代。')
        else if (_serverDaily == null)
          const Text('正在读取服务器每日明细……')
        else ...[
          _StatCard(
              label: '本月服务器查看事件', value: '${_serverDaily!.totalEvents} 次'),
          _StatCard(label: '本月活跃日期', value: '${_serverDaily!.activeDays} 天'),
        ],
        const Divider(height: 28),
        const Text('当前设备缓存',
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
        const SizedBox(height: 8),
        const Text('以下统计只覆盖当前设备已缓存的日记，不代表服务器全部日记。'),
        _StatCard(label: '缓存日记', value: '${local.total} 篇'),
        _StatCard(label: '正文字符', value: '${local.totalCharacters} 个'),
        _StatCard(label: '缓存查看总数', value: '${local.totalViews} 次'),
        _StatCard(label: '活跃日期', value: '${local.activeDays} 天'),
        _StatCard(label: '最近日期', value: local.latestDate ?? '无'),
        const SizedBox(height: 16),
        const Text('标签使用次数',
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
        if (sortedTags.isEmpty)
          const Padding(
              padding: EdgeInsets.symmetric(vertical: 12), child: Text('暂无标签'))
        else
          ...sortedTags.map((entry) => ListTile(
                dense: true,
                leading: const Icon(Icons.label_outline),
                title: Text(entry.key),
                trailing: Text('${entry.value} 篇'),
              )),
        const SizedBox(height: 16),
        const Text('最长日记',
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
        ListTile(
            title: Text(local.longestContent?.date ?? '无'),
            subtitle: Text(local.longestContent?.content ?? '暂无缓存日记',
                maxLines: 4, overflow: TextOverflow.ellipsis)),
        const Divider(height: 28),
        const Text('日期热力图',
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
        Row(children: [
          IconButton(
              tooltip: '上个月',
              onPressed: () => _changeMonth(-1),
              icon: const Icon(Icons.chevron_left)),
          Expanded(
              child: Center(child: Text('${_month.year} 年 ${_month.month} 月'))),
          IconButton(
              tooltip: '下个月',
              onPressed: () => _changeMonth(1),
              icon: const Icon(Icons.chevron_right)),
        ]),
        if (_monthUnavailable)
          const Text('本设备逐日记录读取失败，请重试。')
        else if (_history == null)
          const Text('正在读取本设备逐日记录……')
        else ...[
          _StatCard(label: '本设备已记录事件', value: '${_history!.totalEvents} 次'),
          _StatCard(label: '其中待同步', value: '${_history!.pendingEvents} 次'),
          MonthlyDiaryHeatmap(
              month: _month,
              deviceViews: _history!.dailyCounts,
              serverViews: _serverDaily?.dailyCounts ?? const {},
              cachedDiaries: cachedDiaryDays(widget.diaries, _month),
              onDateTap: _showDate),
          if (deviceDays == null || deviceDays.isEmpty)
            const Text('本月没有本设备新增查看事件。')
          else
            ...deviceDays.map((entry) => ListTile(
                dense: true,
                title: Text(entry.key),
                trailing: Text('本设备新增查看 ${entry.value} 次'))),
        ],
        const Padding(
            padding: EdgeInsets.symmetric(vertical: 12),
            child: Text('服务器日期明细来自真实查看事件；本设备新增事件与服务器历史分开展示。')),
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
          trailing: Text(value,
              style: const TextStyle(fontWeight: FontWeight.bold))));
}
