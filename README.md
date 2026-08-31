# RepoOps

RepoOps 是面向个人开发者和小团队的 GitHub 项目协作与发布质量平台，第一版聚焦 CI 失败处理、Pull Request 状态和版本发布质量。

## 当前状态

已完成 MVP 主链路：GitHub OAuth、账号和仓库绑定、Webhook HMAC 校验、delivery 幂等、PR/CI/Release 状态、可解释发布质量门禁、Celery 任务入口、AI 结构化分析和 Vue 质量工作台。

发布门禁根据真实 GitHub 数据给出“可发布、需要确认、阻塞发布”结论，并逐项展示主分支 CI、开放 PR 和 Release 说明的判断依据。

运行时只接收和同步真实 GitHub 数据，不提供本地演示数据写入接口。

Release Notes 草稿从最近一次 Release 之后合并到默认分支的 PR 生成；前端支持输入目标版本、编辑 Markdown、保存草稿并追溯来源 PR，草稿不会自动发布到 GitHub。

Release 质量页支持生成可审阅的 AI 润色建议：保留原始草稿、展示变更摘要和前后内容对比，用户确认后才载入编辑区，建议本身作为独立分析记录保存；不会自动覆盖草稿或发布版本。

发布前检查单汇总自动门禁与人工确认，按草稿版本保存变更范围、回滚方案和发布窗口的确认状态，并记录操作人和更新时间；人工确认不能覆盖失败 CI 等自动阻塞项。

前端总览提供当前状态和下一步操作引导，Release 质量页按“同步数据 → 生成草稿 → 审阅保存 → 发布前检查”组织流程；空数据和失败状态会说明原因及可执行动作。

当前边界：AI 只生成摘要、CI 失败解释、Release Notes 草稿和可审阅的润色建议，不自动改代码、合并 PR、覆盖草稿、发布版本或部署。

## 运行方式

复制 `.env.example` 为 `.env`，填入 GitHub OAuth 和加密密钥后启动基础服务：

```powershell
docker compose up -d --build
```

开发时也可以分别启动后端和前端：

```powershell
\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload
npm run dev --prefix frontend
```

默认前端地址是 `http://localhost:5174`，API 健康检查是 `/api/health`。生产环境应先执行 `alembic upgrade head`，再启用 `CELERY_ENABLED=true` 启动 Worker。

## 质量保证

- 后端：pytest、Ruff、Alembic 迁移验证。
- 前端：Vitest、Vite production build。
- CI：`.github/workflows/ci.yml` 同时检查后端、前端和 Compose 配置。

## 本地入口

后端测试：

```powershell
\.venv\Scripts\python.exe -m pytest backend\tests -q
```

前端命令：

```powershell
npm install --prefix frontend
npm run build --prefix frontend
```

基础服务：

```powershell
docker compose up -d postgres redis
```

真实 OAuth、Webhook Secret、LLM API Key 和数据库密码只放在本地 `.env` 或部署环境，不提交到 Git。
