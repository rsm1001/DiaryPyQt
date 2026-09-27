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
/api/v1/tags
/api/v1/voices
/api/v1/diaries/{id}/audio/generate
/api/v1/diaries/{id}/audio
/api/v1/audio-assets/{id}/download
```

数据库默认保存到 `server/data/diary_server.db`，音频默认保存到 `server/data/audio/`，真实数据库、音频和 `.env` 不提交到 Git。

## 测试

```powershell
pip install -r server/requirements-dev.txt
pytest server/tests -q
```
