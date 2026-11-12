# ClipBrief

> AI 万能视频下载总结器 —— 一个链接搞定视频下载 + AI 总结。

粘贴视频链接，解析标题、封面和清晰度，服务端下载视频；同时提取字幕，调用 DeepSeek 生成摘要、思维导图，并支持基于字幕的问答。

## 功能

- 多平台解析下载：B站、YouTube、抖音等，基于 yt-dlp
- 抖音专用解析：短链还原，无水印直链
- 缩略图代理：解决 Referer 防盗链
- AI 总结：SSE 流式摘要，Markdown 排版
- 思维导图：markmap 渲染，支持全屏与导出
- AI 问答：基于视频字幕回答
- 字幕下载：SRT / VTT / TXT
- 用户体系：邮箱注册登录（bcrypt + JWT），免费用户每日 3 次 AI 总结
- SEO / GEO：TDK、结构化数据、robots.txt、sitemap.xml、FAQ 内容

## 技术栈

| 层 | 技术 |
| --- | --- |
| 前端 | Vue 3 + Vite + Tailwind CSS |
| 后端 | FastAPI + yt-dlp |
| AI | DeepSeek（OpenAI 兼容接口） |
| 存储 | SQLite |
| 流式 | SSE |

## 快速开始

后端：

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env    # 填 DEEPSEEK_API_KEY
python main.py
```

前端：

```powershell
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173。

没有 DeepSeek Key、只想联调界面时，用 Mock 顶替后端（同样占 8000 端口）：

```powershell
python .\mock\server.py
```

## 目录

```
backend/     FastAPI 服务：解析、下载、总结、用户
frontend/    Vue 3 前端
mock/        无依赖 Mock 服务
docs/        接口契约、组件树、测试用例、Git 约定
scripts/     提交脚本
```

## 文档

- 接口契约：[`docs/api.md`](docs/api.md)
- 组件树：[`docs/组件树.md`](docs/组件树.md)
- 测试用例模板：[`docs/测试用例模板.md`](docs/测试用例模板.md)
- Git 协作与作者约定：[`docs/git-协作与作者约定.md`](docs/git-协作与作者约定.md)
- 开发记录：[`docs/11-12-完成记录.md`](docs/11-12-完成记录.md)

## 团队

| 成员 | 负责 |
| --- | --- |
| 陈博涵 | 下载链路、AI 总结后端、导图导出与字幕下载组件 |
| 潘少杰 | 接口契约、抖音适配、用户与配额、测试统筹 |
| 徐子昂 | 前端页面、布局、SEO/GEO、演示 |

## 声明

本项目仅用于课程学习与技术研究，请下载自己拥有版权或已获授权的内容，遵守各平台服务条款。
