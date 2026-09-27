# PyQt 桌面项目

原有根目录的 `main.py`、`config/`、`controllers/`、`models/`、`services/`、`utils/`、`views/`、`widgets/`、`i18n/`、`tests/`、Python 依赖和 Windows 启动脚本已经迁入 `desktop/`。根目录保留兼容入口与依赖转发，不存在第二套 PyQt 界面。

```powershell
python -m pip install -r desktop/requirements.txt
python desktop/main.py
# 老命令 python main.py / launch_diary_app.bat 也可继续使用
```

原有 SQLite 数据仍在根目录 `data/`，**不搬移活动 WAL 文件**；`desktop/models/config/db_config.py` 与原路径保持一致。同步组件在 `desktop/sync/`；查看次数与最后查看时间在首次人工核对后支持双向增量同步，正文及标签仍只允许受控手动下行；此目录的 `tests/` 是迁入后的原有测试和同步测试。PyQt 旧的绝对导入暂通过包初始化与 pytest 路径兼容，后续可以逐模块改为显式的 `desktop.*` 导入。
# 桌面端服务器连接与查看同步

桌面程序优先读取显式 `DIARY_API_BASE_URL`、`DIARY_API_PASSWORD` 环境变量。未设置地址时，自动读取用户桌面**已存在**的 `DiaryPyQt-连接密码.txt` 中的 HTTPS 地址与独立日记连接密码；不会将密码复制进仓库、日志或同步状态文件。没有凭据文件时保持纯本地模式。`desktop/.env.example` 仅提供配置键，程序不会自动读取 `.env`。

服务器最初由电脑的日记内容建库，当时未导入电脑的历史查看次数。首次通过「工具 → 服务器日记同步审核」核对全部日记的日期、正文、标签均唯一匹配并保存 ID 映射，再点击「上传电脑历史并同步查看记录」。程序先在电脑 SQLite 中冻结历史次数与最后查看时间，通过 HTTPS 幂等补入服务器；已有服务器查看记录保留。导入和重试不会重复计数，随后服务器新增的查看次数及最后查看时间会合并回电脑。

首次核对成功且本地检查点已建立后，桌面程序启动时会尝试后台同步，并每五分钟检查一次：电脑本机新查看记录经 SQLite outbox 上传，手机等设备的新增查看增量下行；断网和服务端旧版本时保留 outbox，出错暂停自动同步，需人工审核并重试。下行只同步总查看数和最后查看时间，不会伪造旧查看明细 `view_log` 或热力图的逐日事件。

正文与标签的 `pull_once` 仍为**手动、已映射且严格校验基线**的受控下行。服务器新建/删除、日期变化、正文冲突仍需人工审核；旧 `sync_once` 对已映射数据的手动上传保持禁用。查看记录同步成功**不等于**日记内容已经开放自动双向同步。请勿删除本地映射文件或查看检查点来跳过冲突。