import 'dart:developer' as developer;

import 'package:flutter/material.dart';

import '../models/diary.dart';
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
  DeviceViewHistory? _history;
  late DateTime _month;
  bool _loadingServer = true;
  bool _loadingMonth = true;
  bool _serverUnavailable = false;
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
      developer.log(
        '服务器汇总读取成功 request_id=${DateTime.now().microsecondsSinceEpoch}',
        name: 'diary.statistics',
      );
      setState(() {
        _server = result;
        _serverUnavailable = false;
      });
    } catch (error, stack) {
      developer.log(
        '服务器汇总读取失败 request_id=${DateTime.now().microsecondsSinceEpoch}',
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
    setState(() {
      _loadingMonth = true;
      _history = null;
      _monthUnavailable = false;
    });
    try {
      final result = await widget.store.getDeviceViewHistory(month);
      if (mounted && request == _monthRequest) {
        setState(() => _history = result);
      }
    } catch (error, stack) {
      developer.log(
        '本设备查看记录读取失败 request_id=${DateTime.now().microsecondsSinceEpoch}',
        name: 'diary.statistics',
        error: error,
        stackTrace: stack,
      );
      if (mounted && request == _monthRequest) {
        setState(() => _monthUnavailable = true);
      }
    } finally {
      if (mounted && request == _monthRequest) {
        setState(() => _loadingMonth = false);
      }
    }
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
    final days = _history?.dailyCounts.entries.toList()
      ?..sort((a, b) => a.key.compareTo(b.key));
    return Scaffold(
      appBar: AppBar(
        title: const Text('统计与日期分布'),
        actions: [
          IconButton(
            tooltip: '刷新统计',
            onPressed: _refresh,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
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
                padding: EdgeInsets.symmetric(vertical: 12),
                child: Text('暂无标签'))
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
                maxLines: 4, overflow: TextOverflow.ellipsis),
          ),
          const Divider(height: 28),
          const Text('本设备查看事件与日期分布',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
          Row(children: [
            IconButton(
                tooltip: '上个月',
                onPressed: () => _changeMonth(-1),
                icon: const Icon(Icons.chevron_left)),
            Expanded(
                child:
                    Center(child: Text('${_month.year} 年 ${_month.month} 月'))),
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
              cachedDiaries: cachedDiaryDays(widget.diaries, _month),
            ),
            const SizedBox(height: 8),
            if (days == null || days.isEmpty)
              const Text('本月没有本设备新增查看事件。')
            else
              ...days.map((entry) => ListTile(
                    dense: true,
                    title: Text(entry.key),
                    trailing: Text('本设备新增查看 ${entry.value} 次'),
                  )),
          ],
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 12),
            child: Text('服务器历史逐日明细不可用；不根据服务器或缓存的查看总数推算历史日期。'),
          ),
        ],
      ),
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
