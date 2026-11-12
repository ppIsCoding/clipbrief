# 项目代码

自己写的代码放这里，**不要直接改 `04-参考代码/free-video-downloader`**。

## 目录

```
05-项目代码/
├─ backend/             FastAPI 后端
│  ├─ main.py           入口、解析/下载/缩略图代理、路由挂载
│  ├─ downloader.py     yt-dlp 封装
│  ├─ douyin.py         抖音专用解析
│  ├─ summarizer.py     字幕提取 + DeepSeek + SSE
│  ├─ api_summarize.py  总结/问答接口
│  ├─ database.py       SQLite 用户表与每日配额
│  ├─ auth.py           bcrypt + JWT
│  ├─ api_auth.py       注册/登录/me
│  ├─ requirements.txt
│  └─ .env.example
├─ frontend/            Vue 3 + Vite + Tailwind
│  ├─ src/App.vue       页面入口
│  ├─ src/components/   组件（见 docs/组件树.md）
│  ├─ src/api/          接口封装（video / summarize / auth）
│  ├─ index.html        TDK、结构化数据、FAQ（SEO/GEO）
│  └─ public/           robots.txt、sitemap.xml、favicon
├─ mock/server.py       无依赖 Mock 服务，前端不等后端
├─ scripts/commit.ps1   按作者提交（三人共用目录时用）
└─ docs/
   ├─ api.md            接口契约（唯一来源）
   ├─ 组件树.md
   ├─ git-协作与作者约定.md
   └─ notes/            每人一页模块笔记
```

## 启动

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

只想联调界面、没有 DeepSeek Key 时，用 Mock 顶替后端：

```powershell
python ..\mock\server.py
```

## 约定

- 接口先写进 `docs/api.md`，改接口先改文档。
- 分支：`feat/download`、`feat/summary`、`feat/frontend`、`feat/auth`、`feat/seo`。
- 每完成一条链路打 tag，和参考仓库的 `stage-0X` 对应。
- 提交信息 `feat(模块): 中文描述`；作者规则见 `docs/git-协作与作者约定.md`。
- `.env`、`node_modules/`、`.venv/`、`backend/data/`、`backend/downloads/` 不提交。
- 代码自己写，参考仓库只作对照；每个模块配一页笔记放在 `docs/notes/`。

## 当前进度（11/12）

- [x] 接口契约 `docs/api.md`
- [x] 后端骨架 + 解析/下载/总结/用户接口（已裁剪支付）
- [x] 前端骨架 + 组件（已裁剪定价/支付）
- [x] Mock 服务
- [x] Git 初始化与作者约定
- [ ] `backend/.env` 填 `DEEPSEEK_API_KEY`
- [ ] 安装 ffmpeg
- [ ] 前端 `npm install` 并跑通
