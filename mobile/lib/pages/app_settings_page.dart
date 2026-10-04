import 'package:flutter/material.dart';

import '../localization/app_strings.dart';
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
  Widget build(BuildContext context) {
    final strings = AppStrings.of(context);
    return Scaffold(
      appBar: AppBar(
        title: Text(strings.settingsTitle),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(_preferences),
            child: Text(strings.save),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(strings.theme,
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
          DropdownButtonFormField<AppThemeMode>(
            initialValue: _preferences.themeMode,
            decoration: InputDecoration(labelText: strings.themeMode),
            items: [
              DropdownMenuItem(
                  value: AppThemeMode.system, child: Text(strings.systemTheme)),
              DropdownMenuItem(
                  value: AppThemeMode.light, child: Text(strings.lightTheme)),
              DropdownMenuItem(
                  value: AppThemeMode.dark, child: Text(strings.darkTheme)),
            ],
            onChanged: (value) {
              if (value != null) {
                _update(_preferences.copyWith(themeMode: value));
              }
            },
          ),
          const SizedBox(height: 24),
          Text(strings.language,
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
          DropdownButtonFormField<AppLanguage>(
            initialValue: _preferences.language,
            decoration: InputDecoration(labelText: strings.interfaceLanguage),
            items: [
              DropdownMenuItem(
                  value: AppLanguage.chinese, child: Text(strings.chinese)),
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
          Text(strings.listFields,
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
          _switch(strings.showDate, _preferences.showDate,
              (value) => _update(_preferences.copyWith(showDate: value))),
          _switch(strings.showViews, _preferences.showViews,
              (value) => _update(_preferences.copyWith(showViews: value))),
          _switch(strings.showTags, _preferences.showTags,
              (value) => _update(_preferences.copyWith(showTags: value))),
          _switch(strings.showPreview, _preferences.showPreview,
              (value) => _update(_preferences.copyWith(showPreview: value))),
          const SizedBox(height: 12),
          DropdownButtonFormField<DiarySortField>(
            initialValue: _preferences.sortField,
            decoration: InputDecoration(labelText: strings.sortField),
            items: [
              DropdownMenuItem(
                  value: DiarySortField.date, child: Text(strings.diaryDate)),
              DropdownMenuItem(
                  value: DiarySortField.views, child: Text(strings.viewCount)),
            ],
            onChanged: (value) {
              if (value != null) {
                _update(_preferences.copyWith(sortField: value));
              }
            },
          ),
          SwitchListTile(
            contentPadding: EdgeInsets.zero,
            title: Text(strings.descending),
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
  }

  Widget _switch(String label, bool value, ValueChanged<bool> onChanged) =>
      SwitchListTile(
        contentPadding: EdgeInsets.zero,
        title: Text(label),
        value: value,
        onChanged: onChanged,
      );
}
