# Git 提交约定

> 仓库只由一个人统一提交（`ppIsCoding`），不再区分三个人各自的 author。
> 分工体现在文档和完成记录里，提交历史保持单一作者，避免多人本地环境混用。

## 一、作者配置

仓库已经配置好本地身份，不用每次指定：

```powershell
git config user.name "ppIsCoding"
git config user.email "ppIsCoding@users.noreply.github.com"
```

检查：

```powershell
git config user.name
git config user.email
```

## 二、提交流程

只提交与本次任务相关的文件，不要 `git add -A`：

```powershell
git status --short
git add backend/main.py frontend/src/App.vue
git commit -m "fix(download): 下载失败提示改为页面内展示"
git push
```

- 一个提交只做一件事，方便回滚和对照文档。
- 提交前至少保证后端能启动、前端能编译。
- 不要提交 `.env`、`.venv`、`node_modules`、`backend/data`、`backend/downloads`，`.gitignore` 已配好。

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
fix(frontend): 游客解析后不再自动弹登录框
docs: 补充 11/15 完成记录
test(download): 补充无效链接与错误格式用例
```

## 四、分支与版本

- 日常开发直接在 `main` 上提交，保持历史线性。
- 每完成一个阶段打 tag，方便答辩时切到对应版本：

```powershell
git tag stage-02-download
git tag stage-03-summary
git push --tags
```

## 五、三条硬规则

1. **不要 `git add -A`**：只加自己改的文件。
2. **不要提交敏感文件**：`.env`、密钥、cookies、下载产物都不进仓库。
3. **提交前先跑一遍**：后端能启动、前端能编译，别把跑不起来的代码推上去。
