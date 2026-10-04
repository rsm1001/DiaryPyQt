import '../models/diary.dart';

enum AppThemeMode { system, light, dark }

enum AppLanguage { chinese, english }

enum DiarySortField { date, views }

class AppPreferences {
  const AppPreferences({
    this.themeMode = AppThemeMode.system,
    this.language = AppLanguage.chinese,
    this.showDate = true,
    this.showViews = true,
    this.showTags = true,
    this.showPreview = true,
    this.sortField = DiarySortField.date,
    this.sortDescending = true,
  });

  final AppThemeMode themeMode;
  final AppLanguage language;
  final bool showDate;
  final bool showViews;
  final bool showTags;
  final bool showPreview;
  final DiarySortField sortField;
  final bool sortDescending;

  static const defaults = AppPreferences();

  AppPreferences copyWith({
    AppThemeMode? themeMode,
    AppLanguage? language,
    bool? showDate,
    bool? showViews,
    bool? showTags,
    bool? showPreview,
    DiarySortField? sortField,
    bool? sortDescending,
  }) =>
      AppPreferences(
        themeMode: themeMode ?? this.themeMode,
        language: language ?? this.language,
        showDate: showDate ?? this.showDate,
        showViews: showViews ?? this.showViews,
        showTags: showTags ?? this.showTags,
        showPreview: showPreview ?? this.showPreview,
        sortField: sortField ?? this.sortField,
        sortDescending: sortDescending ?? this.sortDescending,
      );

  Map<String, dynamic> toJson() => {
        'theme_mode': themeMode.name,
        'language': language.name,
        'show_date': showDate,
        'show_views': showViews,
        'show_tags': showTags,
        'show_preview': showPreview,
        'sort_field': sortField.name,
        'sort_descending': sortDescending,
      };

  factory AppPreferences.fromJson(Map<String, dynamic> json) {
    AppThemeMode parseTheme() => AppThemeMode.values.firstWhere(
          (item) => item.name == json['theme_mode'],
          orElse: () => AppThemeMode.system,
        );
    AppLanguage parseLanguage() => AppLanguage.values.firstWhere(
          (item) => item.name == json['language'],
          orElse: () => AppLanguage.chinese,
        );
    DiarySortField parseSort() => DiarySortField.values.firstWhere(
          (item) => item.name == json['sort_field'],
          orElse: () => DiarySortField.date,
        );
    bool readBool(String key, bool fallback) =>
        json[key] is bool ? json[key] as bool : fallback;

    return AppPreferences(
      themeMode: parseTheme(),
      language: parseLanguage(),
      showDate: readBool('show_date', true),
      showViews: readBool('show_views', true),
      showTags: readBool('show_tags', true),
      showPreview: readBool('show_preview', true),
      sortField: parseSort(),
      sortDescending: readBool('sort_descending', true),
    );
  }

  int compare(Diary left, Diary right) {
    final result = sortField == DiarySortField.views
        ? left.viewCount.compareTo(right.viewCount)
        : left.date.compareTo(right.date);
    return sortDescending ? -result : result;
  }
}
