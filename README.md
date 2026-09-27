# DiaryPyQt 日记系统

此仓库包含现有 PyQt 桌面项目、独立的日记 API 和 Android App。桌面项目已整体迁入 `desktop/`，不是另起一套 PyQt 程序。

```text
DiaryPyQt/
├─ desktop/              # 原有 PyQt 源代码、测试、启动脚本、依赖及同步组件
│  ├─ main.py             # 实际桌面入口
│  ├─ config/ controllers/ i18n/ models/ services/ utils/ views/ widgets/
│  └─ tests/
├─ data/                 # 原有真实日记数据库及 WAL；为安全保留原路径
├─ server/               # 独立 FastAPI 服务及其独立数据库
├─ mobile/               # Flutter Android App
├─ shared/               # 跨端协议和功能对照
├─ main.py               # 兼容原有 python main.py 启动方式
├─ launch_diary_app.bat  # 兼容原有桌面快捷方式
└─ requirements.txt      # 兼容原有安装命令
```

## 桌面端

```powershell
python -m pip install -r requirements.txt
python main.py
# 或直接执行 python desktop/main.py
```

原有日记默认仍读取 `data/diary.db`；不移动、覆盖或复制正在使用的数据库及其 WAL 文件。需要改路径时可配置 `DIARY_DB_PATH`。旧启动脚本与 `main.py` 会转发到 `desktop/` 内的实际工程。PyQt 功能（随机查看、搜索、标签、统计、回收站、批量操作、主题、语言、导入导出）保持原有实现；桌面同步现阶段仍是受控手动流程，不是自动双向同步。

## 手机端

手机 App 已有日记浏览、双遍后台播放和音频缓存；正在扩展桌面管理功能，当前新增了**在线**创建/编辑/删除、日期与正文搜索、标签筛选。离线写入和桌面全部功能尚未完成，见 `shared/feature_parity.md`。具体连接、构建与测试见 `mobile/README.md`。未授权时不要发布服务器或覆盖生产 App。
