# shared

电脑端、后端和手机 App 共用的接口协议、数据结构和同步规则目录。

协议主文档：[`protocol.md`](protocol.md)

固定约定：

- API 前缀：`/api/v1`
- 资源使用复数名词，例如 `/diaries`、`/voices`、`/audio-assets`
- JSON 字段使用 `snake_case`
- 时间统一使用 UTC ISO 8601
- ID 使用 UUID 字符串
- 环境变量统一使用 `DIARY_` 前缀
- 客户端不得直接访问服务器数据库文件
