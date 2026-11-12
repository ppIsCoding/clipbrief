# Git 协作与作者约定

> 目的：三个人各自写的代码，提交记录里能看出是谁写的；老师看 `git log` 或 GitHub 提交历史时一目了然。
> 前提：已经在 `05-项目代码/` 执行过 `git init`（分支 `main`）。

## 一、作者信息（先补真实邮箱）

| 代号 | 姓名 | 建议邮箱 |
| --- | --- | --- |
| `chen` | 陈博涵 | `chenbohan@example.com`（换成自己的 GitHub 邮箱） |
| `pan` | 潘少杰 | `panshaojie@example.com` |
| `xu` | 徐子昂 | `xuziang@example.com` |

邮箱有两种选择：

- 用 GitHub 账号邮箱：提交会自动关联到 GitHub 头像和主页，最直观。
- 用 GitHub 的 noreply 邮箱（设置 → Emails 里能查到，形如 `12345678+用户名@users.noreply.github.com`）：不暴露真实邮箱。

确定后，把 `scripts/commit.ps1` 里的三个邮箱改掉，并同步改这份表。

## 二、两种工作方式

### 方式 A：每人一份自己的 clone（推荐）

每个人在自己电脑上配置一次：

```powershell
git config user.name "陈博涵"
git config user.email "chenbohan@你的邮箱"
```

之后正常 `git commit`，作者自动是本人。三个人通过 GitHub 协作，各自推自己的分支。

### 方式 B：三个人共用同一个目录（现在这种）

共用目录时 `git config` 只有一份，后设置的人会覆盖前一个人。所以用 `--author` 指定本次提交的作者：

```powershell
git commit --author="陈博涵 <chenbohan@example.com>" -m "feat(download): 解析接口"
```

或者直接用仓库里的脚本：

```powershell
# 只提交指定文件，作者记为潘少杰
.\scripts\commit.ps1 -Who pan -Paths backend/api_auth.py,backend/auth.py -Message "feat(auth): 注册登录接口"

# 已经手动 git add 过，只补作者
.\scripts\commit.ps1 -Who xu -Message "feat(frontend): 解析结果组件"
```

脚本会同时设置 author 和 committer，`git log` 里作者和提交者都是本人。

## 三、提交信息规范

格式：`类型(模块): 中文描述`

| 类型 | 用途 |
| --- | --- |
| `feat` | 新功能 |
| `fix` | 修复 Bug |
| `docs` | 文档 |
| `refactor` | 重构 |
| `test` | 测试 |
| `chore` | 构建/配置 |

示例：

```
feat(download): 完成 B站解析与清晰度列表
feat(summary): SSE 流式摘要
fix(sse): 修复换行符丢失
docs(api): 补充字幕下载接口
test(download): 补充抖音短链用例
```

## 四、分支与合并

| 分支 | 负责人 | 内容 |
| --- | --- | --- |
| `feat/download` | 陈博涵 | 解析、下载、缩略图代理 |
| `feat/summary` | 陈博涵 | 字幕、DeepSeek、SSE、导图/问答 |
| `feat/frontend` | 徐子昂 | 页面、组件、布局 |
| `feat/auth` | 潘少杰 | 抖音适配、用户、配额 |
| `feat/seo` | 徐子昂 | SEO/GEO |

- 每个人只在自己的分支上提交，合并到 `main` 前至少一人看一眼。
- 每完成一条链路打 tag：`stage-02-download`、`stage-03-summary`……
- 合并时用 `git merge --no-ff`，保留分支记录。

## 五、三条硬规则

1. **不要 `git add -A`**：只加自己改的文件，避免把别人的半成品带进去。
2. **不要提交 `.env`、`.venv`、`node_modules`、`backend/data`**：`.gitignore` 已经配好。
3. **提交前先跑一遍**：至少保证后端能启动、前端能编译，别把跑不起来的代码推上去。

## 六、首次提交建议

```powershell
cd E:\Desktop\大三上\python\05-项目代码

# 潘少杰提交脚手架与接口契约
.\scripts\commit.ps1 -Who pan -Paths docs/api.md,backend,frontend,README.md,.gitignore `
  -Message "chore: 初始化项目骨架与接口契约"
```

之后按各自模块提交。如果老师要求看每个人的贡献，`git shortlog -sne` 能按作者统计提交数。
