# 日记管理系统 - PyQt版本

这是一个使用PyQt6开发的现代化日记管理系统，从原有的Tkinter版本迁移而来，保留了所有原有功能并提供了更好的用户体验。

## 功能特性

- **现代化UI**: 使用PyQt6框架，提供流畅的用户界面
- **数据管理**: 完整的日记增删改查功能
- **智能排序**: 按查看次数和日期排序
- **随机查看**: 从最少查看的日记中随机选择
- **全文搜索**: 支持关键词搜索日记内容
- **统计功能**: 提供详细的统计信息
- **主题切换**: 支持亮色/暗色主题
- **独立数据**: 项目包含独立的数据库副本

## 安装依赖

```bash
pip install -r requirements.txt
```

## 运行应用

```bash
python main.py
```

应用程序将使用 `data/diary.db` 数据库文件。

## 文件结构

```
DiaryPyQt/
├── data/                           # 数据目录
│   └── diary.db                    # SQLite 数据库
├── main.py                         # 主程序入口
├── requirements.txt                # 依赖包列表
├── launch_diary_app.bat            # Windows 启动脚本
├── README.md                       # 说明文档
├── config/                         # 配置模块
│   └── config.py                   # 应用配置、数据库路径
├── controllers/                    # 控制器层
│   └── enhanced_diary_controller.py # 日记业务控制器
├── models/                         # 数据模型层
│   ├── enhanced_database.py        # 增强数据库管理器
│   ├── migration_backup_manager.py # 数据迁移备份
│   ├── calculations/               # 计算核心
│   │   └── weight_calculation_core.py
│   ├── config/                     # 配置管理
│   │   └── db_config.py
│   ├── entities/                   # 实体类
│   │   └── diary.py
│   ├── mixins/                     # 混入类
│   │   ├── database_query_mixin.py
│   │   └── tag_management_mixin.py
│   ├── repository/                 # 仓储层
│   │   ├── data_migration_mixin.py
│   │   ├── diary_operations.py
│   │   └── statistics_mixin.py
│   ├── table_models/               # PyQt 表格模型
│   │   └── diary_table_model.py
│   └── weight/                     # 权重计算模块
│       ├── calculation_service.py
│       ├── calculator.py
│       ├── diary_selection_service.py
│       └── normalization_strategies.py
├── services/                       # 业务服务层
│   ├── content_service.py
│   ├── statistics_service.py
│   └── view_count_service.py
├── utils/                          # 工具函数
│   ├── formatters.py
│   └── theme_utils.py
├── views/                          # 视图层
│   ├── main_window.py              # 主窗口
│   ├── search_dialog.py            # 搜索对话框
│   ├── components/                 # UI 组件
│   │   ├── menu_bar.py
│   │   └── toolbar.py
│   ├── delegates/                  # 自定义委托
│   │   └── tag_delegate.py
│   └── dialogs/                    # 对话框
│       ├── base_dialog.py
│       ├── diary_dialogs.py
│       └── tag_manager_dialog.py
└── widgets/                        # 自定义控件
    ├── TagSelectorWidget.py
    └── layouts/
        └── flow_layout.py
```

## 快捷键

- `Ctrl+N`: 新建日记
- `Ctrl+R`: 随机查看
- `Ctrl+F`: 搜索
- `Ctrl+Q`: 退出
- `F5`: 刷新