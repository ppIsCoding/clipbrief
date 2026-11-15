# API 契约

> 版本：v1（2026-11-12 冻结，按参考实现对齐）
> 规则：**改接口先改这份文档，再改代码，并在群里同步**。
> Base URL：`http://localhost:8000/api`
> 编码：UTF-8；请求/响应为 JSON（文件下载和 SSE 除外）

## 1. 通用约定

- 需要登录的接口带 `Authorization: Bearer <token>`（JWT，72 小时有效）
- 所有接收 URL 的接口（`parse`、`download`、`summarize`、`chat`、`proxy/thumbnail`）只接受 `http/https`，并拒绝内网、回环、链路本地地址（如 `localhost`、`127.0.0.1`、`169.254.169.254`），防止 SSRF。
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
| 参数/解析/下载失败、URL 安全校验不通过 | 400 |
| 未登录、token 无效或过期 | 401 |
| 缩略图代理失败 | 502 |
| 服务内部错误 | 500 |

## 2. 接口清单

| 方法 | 路径 | 说明 | 登录 |
| --- | --- | --- | --- |
| GET | `/health` | 健康检查 | 否 |
| POST | `/parse` | 解析视频信息与可用格式 | 否 |
| POST | `/download/start` | 创建下载任务，返回 `task_id` | 否 |
| GET | `/download/progress/{task_id}` | 下载进度（SSE） | 否 |
| GET | `/download/file/{task_id}` | 取已完成的下载文件 | 否 |
| POST | `/download` | 同步下载并返回文件（兼容保留） | 否 |
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
    "id": "BV1GJ411x7h7",
    "title": "视频标题",
    "thumbnail": "http://i1.hdslb.com/bfs/archive/xxx.jpg",
    "duration": 212.393,
    "duration_string": "3:32",
    "uploader": "UP 主昵称",
    "platform": "BiliBili",
    "view_count": 108426595,
    "upload_date": "20191231",
    "description": "简介前 200 字",
    "formats": [
      {
        "format_id": "bestvideo+bestaudio/best",
        "ext": "mp4",
        "resolution": "1920x1080",
        "height": 1080,
        "filesize": 69809437,
        "filesize_approx": 69809437,
        "vcodec": "avc1.640032",
        "acodec": "merged",
        "has_audio": true,
        "label": "1080p 最佳 (视频+音频合并)"
      },
      {
        "format_id": "30064",
        "ext": "mp4",
        "resolution": "1280x720",
        "height": 720,
        "filesize": 46531934,
        "filesize_approx": 46531934,
        "vcodec": "avc1.640028",
        "acodec": null,
        "has_audio": false,
        "label": "720p MP4 (仅视频, 44.4MB)"
      }
    ],
    "subtitles": [],
    "automatic_captions": []
  }
}
```

说明：

- `url` 可以是纯链接，也可以是平台分享文案（如 `【标题】https://...`），后端会提取第一个 `http(s)` 链接。
- B站 `/id/video/BV...` 会自动归一化为 `/video/BV...`，只保留分 P 参数 `p`，去掉 `vd_source` 等跟踪参数。
- `platform` 取 yt-dlp 的 extractor 名（B站是 `BiliBili`），抖音是 `douyin`。
- `formats` 已过滤纯音频，按清晰度从高到低，最多 15 条；没有带音频的格式时，会自动插入一条 `bestvideo+bestaudio/best` 合并项。
- 同清晰度优先保留 H.264（Windows 自带播放器可直接打开），`label` 里带编码名；合并项的大小按视频流 + 音频流估算。
- `thumbnail` 是源站地址，前端展示时拼 `/api/proxy/thumbnail?url=...`。
- `subtitles` / `automatic_captions` 只返回语言列表，不返回内容。

### POST /download/start

```json
{
  "url": "https://...",
  "format_id": "bestvideo+bestaudio/best",
  "expected_size": 75219776
}
```

`expected_size` 可选，来自解析结果的 `filesize`，只作为进度的兜底分母；后端会预解析实际流并校正。

响应：

```json
{ "success": true, "data": { "task_id": "9f2c..." } }
```

### GET /download/progress/{task_id}

`Content-Type: text/event-stream`，使用默认 `message` 事件，每条 `data` 是一个 JSON：

```
data: {"status":"pending","percent":null,"downloaded":0,"total":null,"speed":null,"eta":null}

data: {"status":"downloading","percent":42.1,"downloaded":31660000,"total":75219776,"speed":2100000,"eta":14}

data: {"status":"processing","percent":99.0,"downloaded":75167359,"total":75219776,"speed":null,"eta":null}

data: {"status":"done","percent":100.0,"downloaded":75234063,"total":75219776,"filename":"视频标题.mp4"}

data: {"status":"error","error":"当前网络无法访问该平台，请检查网络后重试"}
```

- `status=processing` 表示音视频正在合并。
- `status=done` / `error` 后服务端关闭连接。
- 任务 15 分钟未取文件会过期。

### GET /download/file/{task_id}

- 仅在任务 `done` 后可取，否则返回 400。
- 返回文件流，响应结束后删除临时文件和任务；重复请求返回 404。

### POST /download（兼容保留）

同步下载并直接返回文件流，旧客户端使用；前端已改为「创建任务 + SSE + 取文件」。

```
Content-Type: application/octet-stream
Content-Disposition: attachment; filename*=utf-8''...
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

- 免费用户每日 3 次（`FREE_DAILY_LIMIT` 可配），按北京时间零点重置
- 时区可用 `QUOTA_TIMEZONE` 覆盖；Windows 没装 tzdata 时自动用固定 +08:00
- **总结成功才扣**；无字幕、模型失败、中途断开都不扣
- 剩余次数通过 `summarize` 的 `quota` 事件返回
- 邮箱注册/登录统一 `strip().lower()`，大小写不会产生两个账号

## 6. 前端约定

- 所有请求走 `/api`，开发环境由 Vite 代理到 `localhost:8000`
- 业务接口判断 `success`，错误读 `detail`（可能是字符串或对象）
- SSE 用 `fetch` + `ReadableStream` 解析，不用 `EventSource`（需要 POST 和 Authorization 头）
- 下载走服务端直链 `/api/download/file/{task_id}`，由浏览器原生下载保存

## 7. 冻结记录

| 日期 | 变更 | 负责人 |
| --- | --- | --- |
| 2026-11-12 | v1：10 个接口、SSE 事件、错误结构、配额规则 | 潘少杰 |
| 2026-11-22 | 非 B站链接保留原 query；配额改北京时间；邮箱统一小写；补 17 个单元测试 | 潘少杰 |
