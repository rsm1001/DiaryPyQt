# PyQt 桌面项目

原有根目录的 `main.py`、`config/`、`controllers/`、`models/`、`services/`、`utils/`、`views/`、`widgets/`、`i18n/`、`tests/`、Python 依赖和 Windows 启动脚本已经迁入 `desktop/`。根目录保留兼容入口与依赖转发，不存在第二套 PyQt 界面。

```powershell
python -m pip install -r desktop/requirements.txt
python desktop/main.py
# 老命令 python main.py / launch_diary_app.bat 也可继续使用
```

原有 SQLite 数据仍在根目录 `data/`，**不搬移活动 WAL 文件**；`desktop/models/config/db_config.py` 与原路径保持一致。同步组件在 `desktop/sync/`，尚未接入自动双向同步；此目录的 `tests/` 是迁入后的原有测试和同步测试。PyQt 旧的绝对导入暂通过包初始化与 pytest 路径兼容，后续可以逐模块改为显式的 `desktop.*` 导入。
# 桌面端服务器连接

PyQt 默认只使用本地数据库。要在「工具 → 检查服务器日记（只读）」查看服务器数据，先在启动桌面程序的环境中配置：

```powershell
$env:DIARY_API_BASE_URL = '你的日记服务 HTTPS 地址'
$env:DIARY_API_TIMEOUT = '15'
$env:DIARY_API_PASSWORD = '独立日记连接密码'
python main.py
```

连接密码会作为 `diary` 用户的 HTTP Basic 鉴权值发送，配置了密码时必须使用 HTTPS；未设置密码时不发送鉴权头。密码仅放本地环境，不要写入仓库或日志。`desktop/.env.example` 只列出配置键，应用不会自动读取 `.env` 文件。

检查在后台线程运行，读取增量记录及完整的服务器日记列表，报告日期/正文相同的数量，并单独计算日期、正文、标签名称均一致且**双方各只有一条**的候选 ID 映射数。若有未匹配或重复项，会显示需要人工核对的数量；**界面检查不上传、下载、修改日记或保存映射**。

`desktop/sync/service.py` 提供 `plan_initial_mapping` 和 `initialize_mapping` 供后续受控流程使用。首次映射仅在双方所有活跃日记一对一匹配、服务器两次快照不变、状态文件不存在时，写入 `DIARY_SYNC_STATE_PATH` 指定的**本地同步状态文件**。旧状态损坏或有重复/缺失日记必须人工核对，禁止清空状态强行重试。

新增 `pull_once(LocalDiaryRepository(db_path))`：仅通过手动调用处理**已映射的既有日记**。它逐页校验服务端版本、正文哈希、ID 和日期；对每页先在本地数据库事务内确认所有日记仍是映射时的内容，才更新正文、标签与搜索索引。每页还会在同一 SQLite 事务内写入包含前后状态与目标摘要的恢复收据，提交后才保存 JSON 游标。若数据库提交成功但状态文件写入失败，**下次手动下行**会核验收据与本地数据，核验通过则恢复游标，不重复覆盖日记；数据或状态不匹配则停止，需人工审核。服务器新日记、删除、日期变更、重复映射、离线编辑或双端冲突仍一律停止，不可删除状态文件绕过检查。

当前**没有自动双向同步**：PyQt 菜单仍只提供只读检查；首次映射和下行更新都未接入 UI，也不会在应用启动时运行。旧 `sync_once` 是手动上传适配器：对于已建立映射的日记，目前**完全禁止上传**；未经验证的服务器现存日记或未落地的变更同样阻止上传。正式开放同步前仍需新日记与删除的安全落地、冲突审核界面，以及在多进程并发场景下验证跨文件恢复方案。不要对已有生产日记直接运行手动上传。真机安装和耳机按键仍需现场验证。
