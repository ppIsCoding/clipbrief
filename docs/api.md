# API 契约

> 版本：v1（2026-11-12 冻结，按参考实现对齐）
> 规则：**改接口先改这份文档，再改代码，并在群里同步**。
> Base URL：`http://localhost:8000/api`
> 编码：UTF-8；请求/响应为 JSON（文件下载和 SSE 除外）

## 1. 通用约定

- 需要登录的接口带 `Authorization: Bearer <token>`（JWT，72 小时有效）
- 业务接口统一信封：

```json
{ "success": true, "data": { } }
```

- 错误由 FastAPI 抛出，结构为：

```json
{ "detail": "错误说明" }
```

解析/下载失败时 `detail` 是对象：

```json
{ "detail": { "success": false, "error": "解析失败: ..." } }
```

| 场景 | HTTP |
| --- | --- |
| 参数/解析/下载失败 | 400 |
| 未登录、token 无效或过期 | 401 |
| 缩略图代理失败 | 502 |
| 服务内部错误 | 500 |

## 2. 接口清单

| 方法 | 路径 | 说明 | 登录 |
| --- | --- | --- | --- |
| GET | `/health` | 健康检查 | 否 |
| POST | `/parse` | 解析视频信息与可用格式 | 否 |
| POST | `/download` | 服务端下载并返回文件 | 否 |
| POST | `/direct-url` | 获取带鉴权的直链 | 否 |
| GET | `/proxy/thumbnail` | 缩略图代理（绕过防盗链） | 否 |
| POST | `/summarize` | AI 总结（SSE） | **是** |
| POST | `/chat` | 基于字幕问答（SSE） | **是** |
| POST | `/auth/register` | 注册 | 否 |
| POST | `/auth/login` | 登录 | 否 |
| GET | `/auth/me` | 当前用户 | 是 |

字幕文本随 `summarize` 的 `subtitle` 事件返回，不单独提供字幕接口；字幕文件下载在前端用已拿到的 `segments` 生成（SRT/VTT/TXT）。

## 3. 视频解析与下载

### POST /parse

```json
{ "url": "https://www.bilibili.com/video/BV1xx411c7mD" }
```

响应：

```json
{
  "success": true,
  "data": {
    "title": "视频标题",
    "thumbnail": "https://i0.hdslb.com/...",
    "duration": 632,
    "uploader": "UP 主昵称",
    "platform": "bilibili",
    "video_id": "BV1xx411c7mD",
    "formats": [
      {
        "format_id": "137",
        "ext": "mp4",
        "resolution": "1080p",
        "filesize": 123456789,
        "filesize_text": "117.7MB",
        "has_video": true,
        "has_audio": false,
        "note": "1080P 视频流"
      }
    ]
  }
}
```

说明：

- `formats` 已过滤掉纯音频，最多返回 15 条。
- `thumbnail` 是源站地址，前端展示时拼 `/api/proxy/thumbnail?url=...`。
- 抖音链接走 `douyin.py`，返回结构保持一致。

### POST /download

```json
{ "url": "https://...", "format_id": "bestvideo+bestaudio/best" }
```

响应：二进制文件流

```
Content-Type: application/octet-stream
Content-Disposition: attachment; filename="视频标题.mp4"
```

### POST /direct-url

请求同 `/download`。响应：

```json
{
  "success": true,
  "data": {
    "direct_url": "https://.../video.mp4",
    "ext": "mp4",
    "filesize": 123456789,
    "title": "视频标题"
  }
}
```

### GET /proxy/thumbnail?url=<encoded>

- 只允许 http/https
- 后端补 `User-Agent` / `Referer` 后转发
- 响应图片字节，`Cache-Control: public, max-age=86400`

## 4. AI 总结（SSE）

### POST /summarize

```json
{ "url": "https://...", "language": "zh" }
```

响应：`Content-Type: text/event-stream`

| event | data | 说明 |
| --- | --- | --- |
| `subtitle` | JSON 对象，见下 | 字幕结果，一次 |
| `summary` | JSON 字符串，如 `"## 核心内容\n"` | 摘要增量，多次 |
| `mindmap` | `{"markdown":"# 主题\n## 分支"}` | 导图 Markdown，一次 |
| `quota` | `{"remaining":2,"limit":3}` | 成功后剩余次数 |
| `done` | `"[DONE]"` | 结束 |
| `error` | `{"message":"...","need_login":false}` | 失败 |

`subtitle` 事件的数据结构：

```json
{
  "has_subtitle": true,
  "language": "zh-CN",
  "subtitle_type": "manual",
  "segments": [
    { "start": 0.0, "end": 2.5, "text": "第一句" }
  ],
  "full_text": "完整字幕文本"
}
```

注意：

- `summary` 的 data 是 **JSON 编码后的字符串**，前端取出来直接拼接。
- 未登录时只发一个 `error` 事件（`need_login: true`），不发 `subtitle`。
- 没有字幕时先发 `subtitle`（`has_subtitle: false`），再发 `error`。
- 失败时 **不扣次数**，只有成功走到 `quota` 事件才扣。

### POST /chat

```json
{
  "url": "https://...",
  "question": "视频里提到的三个方法是什么？",
  "subtitle_text": "可选，传了就不再重新提取字幕"
}
```

事件：`answer`（JSON 字符串增量）、`done`、`error`。

## 5. 用户与配额

### POST /auth/register

```json
{ "email": "a@b.com", "password": "至少 6 位" }
```

```json
{
  "success": true,
  "data": {
    "token": "jwt...",
    "user": { "id": 1, "email": "a@b.com" }
  }
}
```

### POST /auth/login

请求同上，响应同注册。

### GET /auth/me

```json
{ "success": true, "data": { "id": 1, "email": "a@b.com" } }
```

配额规则：

- 免费用户每日 3 次（`FREE_DAILY_LIMIT` 可配），跨天按 UTC 日期重置
- **总结成功才扣**；无字幕、模型失败、中途断开都不扣
- 剩余次数通过 `summarize` 的 `quota` 事件返回

## 6. 前端约定

- 所有请求走 `/api`，开发环境由 Vite 代理到 `localhost:8000`
- 业务接口判断 `success`，错误读 `detail`（可能是字符串或对象）
- SSE 用 `fetch` + `ReadableStream` 解析，不用 `EventSource`（需要 POST 和 Authorization 头）
- 下载用 axios `responseType: 'blob'`，再创建 `<a download>` 触发保存

## 7. 冻结记录

| 日期 | 变更 | 负责人 |
| --- | --- | --- |
| 2026-11-12 | v1：10 个接口、SSE 事件、错误结构、配额规则 | 潘少杰 |
