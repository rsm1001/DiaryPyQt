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
├── data/                    # 数据目录
│   └── diary.db            # 本地数据库
├── main.py                  # 主程序入口
├── config.py                # 配置文件
├── requirements.txt         # 依赖包列表
├── README.md               # 说明文档
├── models/                 # 数据模型
│   ├── diary.py           # 日记实体
│   ├── database.py        # 原始数据库管理
│   ├── enhanced_database.py # 增强数据库管理
│   └── __init__.py
├── views/                  # 视图层
│   ├── main_window.py     # 主窗口
│   └── __init__.py
├── controllers/            # 控制器层
│   ├── diary_controller.py     # 原始控制器
│   ├── enhanced_diary_controller.py # 增强控制器
│   └── __init__.py
└── utils/                  # 工具函数
    ├── themes.py          # 主题管理
    └── __init__.py
```

## 快捷键

- `Ctrl+N`: 新建日记
- `Ctrl+R`: 随机查看
- `Ctrl+F`: 搜索
- `Ctrl+Q`: 退出
- `F5`: 刷新