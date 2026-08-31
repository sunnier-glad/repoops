# RepoOps 上下文记忆

## 当前目标

- 将 RepoOps 完成到适合求职展示的 GitHub 项目协作与发布质量平台。
- 仅使用真实 GitHub PR、CI 和 Release 数据，不在产品界面加载演示数据。
- 当前优先完成真实数据驱动的发布准备闭环。

## 已确认方案与关键决策

- GitHub OAuth 负责用户登录与仓库访问。
- 本地环境 `GITHUB_WEBHOOK_ENABLED=false`，通过“同步仓库数据”主动拉取真实数据；公网部署后再启用 Webhook。
- AI 只提供摘要、失败解释和 Release Notes 草稿，不自动修改代码、合并或发布。
- Docker 无法启动时，允许使用项目已有 `.venv`、SQLite 和 Vite 开发服务器继续本地联调。

## 已完成内容

- `5600bb2 feat: use real GitHub data in workspace`
- `2c379cb feat: add quality detail views`
- 当前 Git 工作区在本轮开始时干净，无远程仓库配置。
- Docker Desktop 4.84.0 因 Windows AF_UNIX 残留 socket 连续崩溃：
  - 已将 `C:\Users\曹毅\AppData\Local\Docker\run` 可恢复地改名为 `run-stale-20260830`。
  - 仍有 `C:\Users\曹毅\AppData\Local\docker-secrets-engine\engine.sock` 无法由 Windows 删除或改名；Docker Engine 当前不可用，建议重启 Windows 后再处理。
- 已绕过 Docker 启动本地开发环境：
  - API：`http://127.0.0.1:8000/api/health` 返回 `status=ok`。
  - Web：`http://127.0.0.1:5174` 返回 HTTP 200。
  - 后端使用 `sqlite+pysqlite:///./repoops-local.db`，`CELERY_ENABLED=false`。
  - API 启动 PID 42468，Web 启动 PID 39900；实际子进程 PID 需重新查询端口确认。
  - 日志位于 `%LOCALAPPDATA%\Temp\repoops-api.*.log` 和 `repoops-web.*.log`。
- 已实现发布质量门禁后端：`GET /api/repositories/{id}/quality-gate`。
  - 主分支最新 CI 失败为 `blocked`。
  - CI 缺失/运行中、存在开放 PR、无 Release 或发布说明为空为 `warning`。
  - 全部检查通过为 `ready`；每项返回可解释证据和可选原始链接。
  - 门禁不依赖 AI，不自动发布。
- 已实现 Vue 发布门禁面板：
  - 仓库同步后同时读取真实门禁 API。
  - 展示 `阻塞发布 / 需要确认 / 可以发布`、三项证据和 GitHub 原始链接。
  - 支持 900px/680px 响应式布局；客户端已移除演示数据 API 导出和旧测试。
- 已实现 Release Notes 草稿后端：
  - PR 同步/Webhook 新增 `base_branch` 和 `merged_at`。
  - `ReleaseNoteDraft` 保存版本、Markdown、来源 PR 快照和基准 Release。
  - `GET/POST/PUT /api/repositories/{id}/release-notes/draft` 支持读取、生成与保存编辑。
  - 门禁“发布说明”检查改为读取待发布草稿，而不是已发布 Release。
  - `0007_release_note_drafts` 迁移已验证；本地 SQLite 已安全迁移到 0007，迁移前备份保存在系统临时目录。
- 已实现 Release Notes 前端编辑器：
  - 仅进入“Release 质量”页时按需读取草稿，避免总览页增加无关请求。
  - 支持目标版本输入、生成/重新生成、Markdown 编辑与保存。
  - 展示基准 Release、来源 PR 数量及 GitHub 原始链接，并明确标注“不自动发布”。
  - 生成或保存后重新读取发布门禁，使发布说明检查状态保持一致。
- 已实现持久化发布前检查单：
  - `GET/PUT /api/repositories/{id}/release-readiness` 汇总自动门禁和三项人工确认。
  - `ReleaseChecklist` 按仓库保存草稿版本、变更范围/回滚方案/发布窗口确认、操作人和更新时间。
  - 草稿版本变化后旧确认自动失效；自动门禁为 `blocked` 或 `warning` 时，人工勾选不能改变该结论。
  - Release 质量页展示完成进度、自动证据、人工勾选与审计信息，不提供自动发布入口。
  - 本地 SQLite 已从 0007 升级至 `0008_release_checklists`；升级前备份位于系统临时目录。
- 已实现可审阅的 AI Release Notes 润色建议：
  - `POST/GET /api/repositories/{id}/release-notes/ai-polish` 与 `/latest` 复用 DeepSeek 客户端和既有 `AiAnalysis` 表。
  - 结构化保存当前草稿原文、建议 Markdown、摘要、变更列表、模型和状态；失败也会独立记录，不改草稿、不调用 GitHub 写接口。
  - 草稿内容变化后旧建议自动失效；前端展示前后内容对比，用户只能手动载入编辑区，仍需再次保存。
- 已完成前端引导式工作台优化：
  - 总览页新增当前状态、下一步操作和四步工作流；按钮会根据登录、绑定、同步和草稿状态给出上下文动作。
  - Release 质量页增加专用流程条和使用提示；专业术语、空数据、错误和按钮文案更明确，保留真实数据和 AI 不自动发布边界。
  - 补充卡片说明、状态色、悬停/聚焦反馈和 900px/680px 响应式布局；通用引导只在总览显示，避免详情页重复。
- 已完成 Apple iOS 风格浅蓝主题改造：
  - `frontend/src/App.vue` 改用系统字体栈，移除 Google Fonts 外部依赖，使用浅蓝渐变背景、白色半透明卡片和系统蓝主操作色。
  - 统一仓库接入、下一步操作、质量门禁、指标卡片、事件流、Release 检查单和 AI 审阅区的圆角、边框、阴影、状态色与焦点反馈。
  - 保留真实 GitHub 数据、所有现有 `data-testid`、API 调用和移动端布局；没有新增演示数据或后端变更。
- 已完成前端排版舒适度调整：
  - 提升正文、辅助说明、状态、按钮和编辑器文字的字号与行高，保留标题、指标数字和移动端的层级回调。
  - 未改变业务逻辑；前端 Vitest 16/16、Vite production build 和 `git diff --check` 均通过。
- 已完成流程步骤跳转：
  - 总览页和 Release 质量页的步骤卡片均支持鼠标点击、Enter 和空格键操作。
  - 点击连接/同步定位到仓库区，点击生成草稿定位到 Release 草稿编辑器，点击检查确认定位到发布前检查单；跨页步骤会自动切换到 Release 质量页。
  - 新增前端回归测试，当前前端 Vitest 为 17/17。
- 已完成桌面端固定侧栏布局：
  - 左侧导航固定在视口并独立处理溢出，右侧主内容区域正常滚动。
  - 在 720px 以下恢复顶部导航和上下布局，避免移动端固定侧栏遮挡内容。
  - 前端 Vitest 17/17、Vite production build 和 `git diff --check` 均通过。

## 用户原有改动

- 未发现未提交改动；不要回滚用户提交。
- `.env` 已配置 GitHub OAuth、加密密钥等本地设置；不得输出或提交其中的 Secret。

## 验证结果与遗留问题

- 已验证 API 健康检查和前端首页均可访问；重启本地 SQLite 模式 API 后，OpenAPI 已加载 AI 润色两个接口。
- 用户已在本地 `.env` 配置 LLM Key；未读取、输出或提交 Key。API 已在 SQLite 本地模式重启，健康检查通过，前端 5174 可访问；尚未主动触发真实模型请求。
- 前端引导式 UI 已验证 Vitest 16/16、Vite production build 通过；本轮仅修改前端展示和测试，不改变后端 API。
- 真实 GitHub OAuth 已到达回调并成功创建会话，但原实现回调到 API 根路径 `/`，导致 `GET /` 404。
- 已新增受控 `FRONTEND_URL` 配置，OAuth state 记录该地址，回调后返回 `http://localhost:5174/`；涉及 `config.py`、OAuth 路由、环境模板、Compose 和测试。
- OAuth 回归测试 5/5 通过，Ruff 通过；API 已重启并再次通过健康检查。
- 门禁及仓库 API 回归测试 10/10 通过，相关 Ruff 检查通过。
- 前端 Vitest 16/16 通过，Vite production build 通过；API 健康检查和前端 HTTP 200 通过。
- Apple 浅蓝主题改造后，前端 Vitest 16/16 通过，Vite production build 通过，`git diff --check` 通过；API `/api/health` 返回 `status=ok`，前端 `5174` 返回 HTTP 200。
- 后端完整测试 42/42 通过、Ruff 通过，Alembic 从空库升级到 0008 通过；真实仓库同步成功，当前候选合并 PR 为 0。
- 本地 SQLite 已保存 1 个真实 GitHub 用户和绑定仓库 `sunnier-glad/life-deadline-radar`。
- 已调用真实 GitHub 同步：PR 0、失败 Workflow 0、Release 0；这是仓库当前真实状态，不是演示数据或同步异常。
- OAuth 完成后：同步真实仓库，验证 PR、失败 Workflow 和 Release 详情页；不要创建演示数据。
- 后端运行时演示接口、服务和 `is_demo` 字段已移除；保留 `0005` 历史迁移，并由 `0006` 向前删除旧字段。
- 真实数据模式清理验证：后端完整测试 36/36 通过、Ruff 通过、Alembic 从空库升级到 `0006_remove_demo_flags` 通过。
- Docker 修复未完成，不要执行 factory reset；重启系统后先确认 stale socket 是否自动消失。

## 当前遗留问题与下一步

1. 用户刷新 `http://localhost:5174/`，进入“Release 质量”查看草稿编辑器与发布前检查单。
2. 当前真实仓库没有已合并 PR；若要验证非零来源列表，需要先在 GitHub 合并真实 PR，再同步仓库并重新生成草稿。
3. 当前本地 LLM Key 是否可用尚未做真实模型调用验证；下一步在已登录页面点击“AI 润色建议”，再用真实合并 PR 验证非空来源的润色结果。
4. Docker Desktop 的 Windows socket 问题仍未解决；当前开发验证继续使用 SQLite + `.venv`。

## 2026-08-31 真实验收、部署与文档包装进展

- 已创建公开 GitHub 仓库 `https://github.com/sunnier-glad/repoops`，并将 RepoOps 推送到 `main`。
- 已新增并推送提交 `492c9c2 docs: package deployment and acceptance guidance`，包含：
  - `docs/DEPLOYMENT.md`：Ubuntu + Docker Compose 部署、无域名服务器 IP 预览、有域名 HTTPS 正式环境、健康检查、备份与边界。
  - `docs/ACCEPTANCE.md`：真实 GitHub 数据验收对象、验收矩阵、证据留存要求和结论口径。
  - `README.md`：补充 GitHub、部署和验收文档入口。
  - `docker-compose.yml` / `.env.example`：PostgreSQL 数据库名、用户、密码和 `DATABASE_URL` 改为可配置变量。
  - `docs/RESUME.md`：更新项目链接、验证数字和公网部署边界。
- 本轮验证：后端 `42 passed`、前端 `17 passed`、Vite production build 通过、Compose config 通过、`git diff --check` 通过；普通测试环境首次失败是 `.env` 使用容器数据库主机和 Windows 临时目录权限，改用临时 SQLite 与项目内隔离临时目录后通过。
- 真实验收仓库仍为 `sunnier-glad/life-deadline-radar`。此前已核对其当前无 PR、无 Workflow Run、无 Release；因此目前只能验收“空数据同步正确”，不能声称非空事件链已完成。
- 当前 GitHub CLI 本地授权令牌已失效，已重新发起设备授权，等待用户在 GitHub 设备页面完成授权；不记录设备验证码。
- Ubuntu 服务器尚未提供 IP/SSH 入口，因此只完成部署文档，未声称已完成远程部署；无域名时只能做服务器 IP 预览和手动同步，公网 Webhook 仍需 HTTPS 地址。

### 当前下一步

1. 用户完成 GitHub CLI 设备授权后，复核 `repoops` 最新 CI 和真实验收仓库状态。
2. 单独确认是否允许在 `life-deadline-radar` 创建无业务影响的真实验收 PR、Workflow Run 和 Release；未经确认不创建外部资源。
3. 获取 Ubuntu 服务器地址和 SSH 登录方式（不要在聊天中发送密码或密钥），按 `docs/DEPLOYMENT.md` 完成部署与健康检查。
4. 将真实验收链接、数量变化、截图和线上检查结果补回 `docs/ACCEPTANCE.md`，再更新简历口径。
