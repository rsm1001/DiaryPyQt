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
