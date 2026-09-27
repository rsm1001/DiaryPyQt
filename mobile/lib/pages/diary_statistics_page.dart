import 'package:flutter/material.dart';

import '../models/diary.dart';
import '../models/server_statistics.dart';
import '../services/diary_api.dart';
import '../services/diary_statistics.dart';

class DiaryStatisticsPage extends StatefulWidget {
  const DiaryStatisticsPage({
    super.key,
    required this.diaries,
    required this.api,
  });

  final List<Diary> diaries;
  final DiaryApi api;

  @override
  State<DiaryStatisticsPage> createState() => _DiaryStatisticsPageState();
}

class _DiaryStatisticsPageState extends State<DiaryStatisticsPage> {
  ServerStatistics? _server;
  bool _loadingServer = true;

  @override
  void initState() {
    super.initState();
    _loadServerStatistics();
  }

  Future<void> _loadServerStatistics() async {
    try {
      final result = await widget.api.fetchStatistics();
      if (mounted) setState(() => _server = result);
    } catch (_) {
      // 断网时保留本地统计，不把服务器不可用显示成数据为零。
    } finally {
      if (mounted) setState(() => _loadingServer = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final local = calculateDiaryStatistics(widget.diaries);
    final sortedTags = local.tagCounts.entries.toList()
      ..sort((a, b) => b.value.compareTo(a.value));
    return Scaffold(
      appBar: AppBar(
        title: const Text('统计'),
        actions: [
          IconButton(
              tooltip: '刷新服务器统计',
              onPressed: _loadServerStatistics,
              icon: const Icon(Icons.refresh)),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          if (_loadingServer) const LinearProgressIndicator(),
          if (_server != null) ...[
            const Text('服务器统计',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            _StatCard(label: '服务器日记', value: '${_server!.totalDiaries} 篇'),
            _StatCard(label: '服务器查看次数', value: '${_server!.totalViews} 次'),
            _StatCard(
                label: '服务器平均查看',
                value: _server!.averageViews.toStringAsFixed(1)),
            _StatCard(label: '最多查看', value: '${_server!.mostViewedCount} 次'),
            _StatCard(label: '最少查看', value: '${_server!.leastViewedCount} 次'),
            const Divider(height: 28),
          ],
          Text(_server == null ? '本地缓存统计' : '本地缓存补充统计',
              style:
                  const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          Text(
              _server == null
                  ? '服务器统计不可用，以下数据来自当前设备缓存。'
                  : '字符数、活跃日期和标签使用情况来自当前设备缓存。',
              style: const TextStyle(color: Colors.grey)),
          _StatCard(label: '缓存日记', value: '${local.total} 篇'),
          _StatCard(label: '正文字符', value: '${local.totalCharacters} 个'),
          _StatCard(label: '本地查看次数', value: '${local.totalViews} 次'),
          _StatCard(label: '活跃日期', value: '${local.activeDays} 天'),
          _StatCard(label: '最近日期', value: local.latestDate ?? '无'),
          const SizedBox(height: 16),
          const Text('标签使用次数',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
          if (sortedTags.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 12),
              child: Text('暂无标签'),
            )
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
            subtitle: Text(
              local.longestContent?.content ?? '暂无缓存日记',
              maxLines: 4,
              overflow: TextOverflow.ellipsis,
            ),
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
