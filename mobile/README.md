# mobile

日记 Android App：在线同步服务器日记，已下载的日记与语音可以离线播放。

## 真机连接（不需要 Tailscale）

1. 在桌面打开 `DiaryPyQt-连接密码.txt`，取得连接密码。不要将它发送给别人。
2. 安装桌面上按日期时分命名的正式 APK，例如 `DiaryPyQt-release-20261001-1430.apk`；启动后点右上角齿轮。
3. 服务器地址填 `https://203.195.195.218`（**不要填 http**，也不要填 8010/8020 端口）。
4. 连接密码填桌面文件里的密码，点「测试并保存」；App 会验证身份并拉取日记。

地址保存到本地 SQLite，密码存入 Android 安全存储（Keystore）；App 不预置密码，切换服务器时不会向新服务器发送原密码。旧版 `http://100.125.111.63:8020` 和 `http://203.195.195.218` 保存地址会自动迁移到公网 HTTPS 地址。

## 构建与验证

```powershell
cd mobile
flutter pub get
flutter analyze
flutter test
flutter build apk --debug --dart-define=DIARY_API_BASE_URL=https://203.195.195.218
flutter build apk --release --dart-define=DIARY_API_BASE_URL=https://203.195.195.218

$buildStamp = Get-Date -Format 'yyyyMMdd-HHmm'
Copy-Item build/app/outputs/flutter-apk/app-debug.apk `
  "build/app/outputs/flutter-apk/DiaryPyQt-debug-$buildStamp.apk"
Copy-Item build/app/outputs/flutter-apk/app-release.apk `
  "build/app/outputs/flutter-apk/DiaryPyQt-release-$buildStamp.apk"
```

语音下载会附带鉴权，且只允许从当前服务器下载；离线音频按内容版本校验。电脑端后续日记修改仍需执行桌面同步后手机才能看到更新。

## 查看记录与离线管理自动恢复

- 随机播放/打开日记先写入 SQLite 查看事件与累计次数；响应丢失、断网重连后复用原事件 ID，服务器不重复计数。刷新时先提交本地待同步操作，再获取服务器日记。
- 网络由离线转为可用、App 从后台返回前台时会自动尝试同步；同时触发的请求按顺序合并，不会并行写入同一个 outbox。自动同步时已加载的日记列表仍可使用，队列数量及离线/同步状态显示在列表顶部。
- HTTP 409 版本冲突会停止提交，保留本地编辑、原版本与待同步任务并给出提示；不会静默覆盖服务端内容。若手机系统显示联网但服务端不可达，仍保留本地队列供恢复后重试。
- 断网新建后编辑只上传最终内容；未上传的新建即使已恢复网络，仍可本地直接撤销。删除已有日记前先提交该日记尚未同步的查看事件；网络再次中断时按“查看 → 删除”入队。在线编辑不会覆盖尚未上报的本地查看次数。
- 手机切换至另一服务器时若仍有待同步任务会拒绝切换，避免误发给不相关的服务；公网地址只接受 HTTPS，私网 HTTP 入口仅限已信任的本地和 Tailnet 配置。
- `sqflite_common_ffi` 仅用于桌面运行的 SQLite 回归测试，不增加正式 Android App 的运行时依赖；本机测试与 Debug 构建都不能替代真机断网、锁屏、蓝牙耳机验收。未经明确授权不发布新版 APK。

## 修改后强制验收流程（2026-09-28）

每次修改移动端代码后，必须在发布之前重新完成以下流程，不得只运行静态检查：

```powershell
cd mobile
flutter pub get
flutter analyze
flutter test
flutter build apk --debug --dart-define=DIARY_API_BASE_URL=https://203.195.195.218
flutter build apk --release --dart-define=DIARY_API_BASE_URL=https://203.195.195.218
```

- 交付文件必须命名为 `DiaryPyQt-debug-YYYYMMDD-HHmm.apk` 和 `DiaryPyQt-release-YYYYMMDD-HHmm.apk`，例如 `DiaryPyQt-release-20261001-1430.apk`。
- Debug 与 Release 必须使用同一批次时间戳；`app-debug.apk` 和 `app-release.apk` 只能作为 Flutter 的中间产物，不得直接发送或安装交付。
- 构建后应对按日期时分命名的交付 APK 计算并保留 SHA-1 校验值、文件大小和生成时间。
- 只有 `flutter analyze`、`flutter test`和两种 APK 构建全部成功后，才能将本次修改标记为可验收。
- 构建只在 Windows 本地完成；未经用户明确同意，不发布到生产服务器。

## 回收站批量操作与服务端兼容

回收站支持按日期或正文搜索、多选恢复与永久删除。清空回收站必须二次确认；操作结果分别展示成功、失败和未处理数量，失败项目可在当前列表重试。联网恢复沿用版本校验，断网恢复只保存待同步任务，不显示成已成功恢复。
新版手机端永久删除**只调用**服务端的版本校验入口 `DELETE /api/v1/trash/{diary_id}/versions/{version}`。服务端尚未更新时会拒绝新版删除操作，不会回退到旧无版本接口。需经用户另行授权先更新服务端，再安装该版本 App；本地构建与测试不等于已发布或已完成真机验收。