# DiaryPyQt 日记系统共享协议

> 本文件是 `desktop`、`server` 和 `mobile` 的共同数据约定。修改字段前，必须同步评估三端和同步逻辑。

## 1. 基本约定

```text
API 前缀：/api/v1
JSON 字段：snake_case
时间：UTC ISO 8601，例如 2026-09-25T12:00:00Z
ID：UUID 字符串
内容哈希：sha256:<64位十六进制字符串>
环境变量：DIARY_ 前缀
```

API 使用复数资源名：

```text
/api/v1/diaries
/api/v1/tags
/api/v1/voices
/api/v1/audio-assets
/api/v1/playback-records
/api/v1/sync/pull
/api/v1/sync/push
```

## 2. 数据模型

### Diary

```json
{
  "id": "uuid",
  "date": "2026-09-25",
  "content": "日记正文",
  "content_hash": "sha256:...",
  "version": 1,
  "tags": ["学习", "教训"],
  "created_at": "2026-09-25T12:00:00Z",
  "updated_at": "2026-09-25T12:00:00Z",
  "deleted_at": null
}
```

规则：

- `content` 不能为空。
- `version` 每次内容修改递增。
- `content_hash` 根据正文重新计算。
- 删除使用软删除，保留 `deleted_at` 供同步使用。

### Tag

```json
{
  "id": "uuid",
  "name": "学习",
  "created_at": "2026-09-25T12:00:00Z"
}
```

### VoiceProfile

```json
{
  "id": "uuid",
  "name": "普通话女声",
  "provider": "edge_tts",
  "language": "zh-CN",
  "voice_name": "voice-name",
  "speed": 1.0,
  "pitch": 1.0,
  "offline_supported": false,
  "config_hash": "sha256:..."
}
```

### AudioAsset

```json
{
  "id": "uuid",
  "diary_id": "uuid",
  "voice_id": "uuid",
  "content_hash": "sha256:...",
  "voice_config_hash": "sha256:...",
  "duration_ms": 60000,
  "format": "mp3",
  "file_hash": "sha256:...",
  "status": "ready",
  "download_url": "/api/v1/audio-assets/uuid/download",
  "created_at": "2026-09-25T12:00:00Z"
}
```

`status` 允许值：

```text
pending | generating | ready | failed | expired
```

### PlaybackRecord

```json
{
  "id": "uuid",
  "device_id": "uuid",
  "diary_id": "uuid",
  "voice_id": "uuid",
  "round_number": 1,
  "position_ms": 0,
  "status": "playing",
  "updated_at": "2026-09-25T12:00:00Z"
}
```

`round_number` 只能是 `1` 或 `2`；`status` 允许值：

```text
playing | paused | waiting | completed | skipped
```

### SyncChange

```json
{
  "cursor": 100,
  "entity_type": "diary",
  "entity_id": "uuid",
  "action": "upsert",
  "version": 2,
  "updated_at": "2026-09-25T12:00:00Z"
}
```

`action` 允许值：

```text
upsert | delete
```

## 3. API 返回格式

成功响应直接返回资源或资源列表；分页列表统一使用：

```json
{
  "items": [],
  "next_cursor": null
}
```

错误响应统一使用：

```json
{
  "code": "DIARY_VERSION_CONFLICT",
  "message": "日记版本冲突",
  "request_id": "uuid",
  "details": {}
}
```

不允许把 Python 异常文本直接返回给客户端。

## 4. 同步规则

### 拉取

```text
GET /api/v1/sync/pull?cursor=100
```

- 客户端第一次使用 `cursor=0`。
- 服务端返回变更和新的 `next_cursor`。
- 客户端成功保存变更后，才能提交新的游标。

### 推送

```text
POST /api/v1/sync/push
```

每个修改携带：

```json
{
  "entity_type": "diary",
  "entity_id": "uuid",
  "base_version": 1,
  "action": "upsert",
  "data": {}
}
```

- `base_version` 等于服务器当前版本时允许更新。
- 版本不一致返回 HTTP `409`。
- 冲突数据不得静默覆盖。
- 播放进度允许按 `updated_at` 取最新值；日记正文必须提示冲突。

## 5. 音频更新规则

音频唯一匹配条件：

```text
日记 content_hash
+ 语音 config_hash
```

只要其中一个变化：

```text
旧音频标记 expired
→ 生成新音频
→ 保存 duration_ms 和 file_hash
→ 客户端下载并校验
→ 替换本地音频
```

下载未完成或校验失败时，不得删除本地可用旧音频。

## 查看事件（离线幂等）

`POST /api/v1/diaries/{diary_id}/view` 接受 JSON 请求体：

```json
{"event_id":"设备生成的唯一事件 ID","viewed_at":"2026-09-27T12:00:00Z"}
```

- 每次查看先在客户端同一 SQLite 事务内写入本地查看次数与待同步事件，再向服务器提交；重试必须复用同一 `event_id` 与 `viewed_at`。
- 服务端在一个事务内按 `event_id` 去重并更新次数；同一事件重复提交只返回现有汇总，不重复计数。相同 ID 指向其他日记返回 409。
- `last_viewed_at` 取已接收事件时间的最大值；`viewed_at` 必须带时区。旧客户端无请求体时仍可提交，但其请求不具备重试幂等性。
- 客户端收到确认后，必须在同一 SQLite 事务内更新本地汇总并移除 outbox；确认丢失时再次提交，由服务端去重。首次生成的本地临时日记需先取得服务端 ID，再发送该日记的查看事件。
### 电脑历史查看次数上行与持续同步

- 服务器日记最初源于电脑，但创建 API 当时只传了日期、正文和标签，未传电脑已有 `view_count` 和 `last_viewed_at`。先确认一对一 ID 映射，再将电脑原有历史统计补到服务器；**不得先把服务器的小计加回电脑作为初始基线**。
- `GET /health` 的 `capabilities` 必须同时含 `desktop_view_baseline_v1` 与 `view_event_idempotent_v1`，否则客户端禁止向旧服务端上传初始统计和待发查看事件。
- `POST /api/v1/diaries/{diary_id}/view-baselines` 接受 `source_id`、`view_count`、`last_viewed_at`；`source_id` 固定为 `desktop-initial:{diary_id}`。服务端在 SQLite 事务中按来源幂等地将初始累计加到现有服务器次数上，最后查看时间取较晚值；重复相同请求只确认、不同内容返回 409。
- 客户端首次发出网络请求前，在本地 SQLite 事务中冻结电脑初始累计和最后查看时间、建立检查点与 outbox。以后新的本地查看写入该 outbox；初次上传部分成功或响应丢失后，重试仍发送冻结的相同基线，不重复计数。
- 基线确认后上传待发查看事件，再读取稳定的服务器总数。单个 SQLite 事务中按服务器增量扣除已在本地计算的事件数，更新桌面统计与检查点，并确认出队；异常时保留队列。服务器只有总数和最后查看时间，不凭空生成电脑 `view_log` 的逐日明细。