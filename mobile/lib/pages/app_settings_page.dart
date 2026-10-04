import 'package:flutter/material.dart';

import '../models/app_preferences.dart';

class AppSettingsPage extends StatefulWidget {
  const AppSettingsPage({super.key, required this.initial});

  final AppPreferences initial;

  @override
  State<AppSettingsPage> createState() => _AppSettingsPageState();
}

class _AppSettingsPageState extends State<AppSettingsPage> {
  late AppPreferences _preferences = widget.initial;

  void _update(AppPreferences next) => setState(() => _preferences = next);

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(
          title: const Text('主题、语言与列表显示'),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(context).pop(_preferences),
              child: const Text('保存'),
            ),
          ],
        ),
        body: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            const Text('主题',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            DropdownButtonFormField<AppThemeMode>(
              initialValue: _preferences.themeMode,
              decoration: const InputDecoration(labelText: '主题模式'),
              items: const [
                DropdownMenuItem(
                    value: AppThemeMode.system, child: Text('跟随系统')),
                DropdownMenuItem(value: AppThemeMode.light, child: Text('浅色')),
                DropdownMenuItem(value: AppThemeMode.dark, child: Text('深色')),
              ],
              onChanged: (value) {
                if (value != null) {
                  _update(_preferences.copyWith(themeMode: value));
                }
              },
            ),
            const SizedBox(height: 24),
            const Text('语言',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            DropdownButtonFormField<AppLanguage>(
              initialValue: _preferences.language,
              decoration: const InputDecoration(labelText: '界面语言'),
              items: const [
                DropdownMenuItem(
                    value: AppLanguage.chinese, child: Text('简体中文')),
                DropdownMenuItem(
                    value: AppLanguage.english, child: Text('English')),
              ],
              onChanged: (value) {
                if (value != null) {
                  _update(_preferences.copyWith(language: value));
                }
              },
            ),
            const SizedBox(height: 24),
            const Text('列表字段',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            _switch('显示日期', _preferences.showDate,
                (value) => _update(_preferences.copyWith(showDate: value))),
            _switch('显示查看次数', _preferences.showViews,
                (value) => _update(_preferences.copyWith(showViews: value))),
            _switch('显示标签', _preferences.showTags,
                (value) => _update(_preferences.copyWith(showTags: value))),
            _switch('显示正文摘要', _preferences.showPreview,
                (value) => _update(_preferences.copyWith(showPreview: value))),
            const SizedBox(height: 12),
            DropdownButtonFormField<DiarySortField>(
              initialValue: _preferences.sortField,
              decoration: const InputDecoration(labelText: '排序字段'),
              items: const [
                DropdownMenuItem(
                    value: DiarySortField.date, child: Text('日记日期')),
                DropdownMenuItem(
                    value: DiarySortField.views, child: Text('查看次数')),
              ],
              onChanged: (value) {
                if (value != null) {
                  _update(_preferences.copyWith(sortField: value));
                }
              },
            ),
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              title: const Text('降序排列'),
              value: _preferences.sortDescending,
              onChanged: (value) =>
                  _update(_preferences.copyWith(sortDescending: value)),
            ),
            const Padding(
              padding: EdgeInsets.only(top: 12),
              child: Text('这些设置只影响本机界面，不会修改日记、查看统计或同步任务。'),
            ),
          ],
        ),
      );

  Widget _switch(String label, bool value, ValueChanged<bool> onChanged) =>
      SwitchListTile(
        contentPadding: EdgeInsets.zero,
        title: Text(label),
        value: value,
        onChanged: onChanged,
      );
}
