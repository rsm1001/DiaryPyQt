import 'package:flutter/material.dart';

class MonthlyDiaryHeatmap extends StatelessWidget {
  const MonthlyDiaryHeatmap({
    super.key,
    required this.month,
    required this.deviceViews,
    required this.cachedDiaries,
    this.serverViews = const {},
    this.onDateTap,
  });

  final DateTime month;
  final Map<String, int> deviceViews;
  final Map<String, int> cachedDiaries;
  final Map<String, int> serverViews;
  final ValueChanged<String>? onDateTap;

  @override
  Widget build(BuildContext context) {
    final first = DateTime(month.year, month.month);
    final days = DateTime(month.year, month.month + 1, 0).day;
    final offset = first.weekday - 1;
    final sourceViews = serverViews.isEmpty ? deviceViews : serverViews;
    final peak = sourceViews.values
        .fold<int>(0, (max, count) => count > max ? count : max);
    final colors = Theme.of(context).colorScheme;
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(serverViews.isEmpty
          ? '颜色表示本设备新增查看，圆点表示本地缓存日记的创建日期。'
          : '颜色表示服务器历史查看，粗体数字表示本设备新增查看，圆点表示本地缓存日记。'),
      const SizedBox(height: 8),
      Row(children: [
        for (final day in ['一', '二', '三', '四', '五', '六', '日'])
          Expanded(child: Center(child: Text(day))),
      ]),
      GridView.builder(
        shrinkWrap: true,
        physics: const NeverScrollableScrollPhysics(),
        gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
          crossAxisCount: 7,
          mainAxisSpacing: 3,
          crossAxisSpacing: 3,
        ),
        itemCount: offset + days,
        itemBuilder: (context, index) {
          if (index < offset) return const SizedBox.shrink();
          final day = index - offset + 1;
          final key = '${first.year.toString().padLeft(4, '0')}-'
              '${first.month.toString().padLeft(2, '0')}-'
              '${day.toString().padLeft(2, '0')}';
          final views = deviceViews[key] ?? 0;
          final serverCount = serverViews[key] ?? 0;
          final diaries = cachedDiaries[key] ?? 0;
          final intensity = peak == 0
              ? 0.0
              : (serverViews.isEmpty ? views : serverCount) / peak;
          final background = Color.lerp(colors.surfaceContainerHighest,
              colors.primaryContainer, intensity)!;
          final description = '$key：服务器查看 $serverCount 次，本设备新增查看 '
              '$views 次，缓存日记 $diaries 篇';
          return Tooltip(
            message: description,
            child: Semantics(
              label: description,
              child: InkWell(
                onTap: onDateTap == null ? null : () => onDateTap!(key),
                child: Container(
                  decoration: BoxDecoration(
                    color: background,
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Text('$day',
                          style: TextStyle(
                            color: colors.onSurface,
                            fontWeight: views > 0 ? FontWeight.bold : null,
                          )),
                      if (diaries > 0)
                        Icon(Icons.circle, size: 6, color: colors.primary),
                    ],
                  ),
                ),
              ),
            ),
          );
        },
      ),
    ]);
  }
}
