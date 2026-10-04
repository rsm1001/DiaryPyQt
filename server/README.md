# server

日记独立后端，基于 FastAPI。

## 本地运行

```powershell
pip install -r server/requirements.txt
python -m server.main
```

默认地址：

```text
http://127.0.0.1:8010
```

健康检查：

```text
GET /health
```

日记 API：

```text
/api/v1/diaries
/api/v1/playback-records
/api/v1/tags
/api/v1/voices
/api/v1/diaries/{id}/audio/generate
/api/v1/diaries/{id}/audio
/api/v1/audio-assets/{id}/download
/api/v1/statistics/daily?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
/api/v1/calendar/diaries?date=YYYY-MM-DD
```

每日查看统计按 UTC 日期归属真实查看事件，并返回所选日期范围的每日次数、昨日查看总数及历史最佳单日和日期。历史查看基线不计入逐日事件；服务端保留每日事件聚合，日记进入回收站或永久删除后历史统计仍可查询。旧数据库升级时会从现存真实查看事件幂等回填聚合；无事件时最佳单日次数为零、日期为空。手机端按服务器与日期范围缓存成功获取的结果，断网时标注缓存时间，不将缓存视为实时统计。

数据库默认保存到 `server/data/diary_server.db`，音频默认保存到 `server/data/audio/`，真实数据库、音频和 `.env` 不提交到 Git。

## 测试

```powershell
pip install -r server/requirements-dev.txt
pytest server/tests -q
```
