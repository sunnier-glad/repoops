# RepoOps 上下文记忆

## 当前目标

- 将 RepoOps 完成到适合求职展示的 GitHub 项目协作与发布质量平台。
- 仅使用真实 GitHub PR、CI 和 Release 数据，不在产品界面加载演示数据。
- 当前优先完成本地真实 OAuth、仓库绑定和同步冒烟验证。

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

## 用户原有改动

- 未发现未提交改动；不要回滚用户提交。
- `.env` 已配置 GitHub OAuth、加密密钥等本地设置；不得输出或提交其中的 Secret。

## 验证结果与遗留问题

- 已验证 API 健康检查和前端首页均可访问。
- 真实 GitHub OAuth 已到达回调并成功创建会话，但原实现回调到 API 根路径 `/`，导致 `GET /` 404。
- 已新增受控 `FRONTEND_URL` 配置，OAuth state 记录该地址，回调后返回 `http://localhost:5174/`；涉及 `config.py`、OAuth 路由、环境模板、Compose 和测试。
- OAuth 回归测试 5/5 通过，Ruff 通过；API 已重启并再次通过健康检查。
- 门禁及仓库 API 回归测试 10/10 通过，相关 Ruff 检查通过。
- 前端 Vitest 12/12 通过，Vite production build 通过；API 健康检查和前端 HTTP 200 通过。
- 本地 SQLite 已保存 1 个真实 GitHub 用户和绑定仓库 `sunnier-glad/life-deadline-radar`。
- 已调用真实 GitHub 同步：PR 0、失败 Workflow 0、Release 0；这是仓库当前真实状态，不是演示数据或同步异常。
- OAuth 完成后：同步真实仓库，验证 PR、失败 Workflow 和 Release 详情页；不要创建演示数据。
- 后端运行时演示接口、服务和 `is_demo` 字段已移除；保留 `0005` 历史迁移，并由 `0006` 向前删除旧字段。
- 真实数据模式清理验证：后端完整测试 36/36 通过、Ruff 通过、Alembic 从空库升级到 `0006_remove_demo_flags` 通过。
- Docker 修复未完成，不要执行 factory reset；重启系统后先确认 stale socket 是否自动消失。

## 下一步

1. 用户刷新 `http://localhost:5174/`，确认 OAuth 修复后不再落到 API 404。
2. 若需要验证非零真实数据，在绑定仓库创建真实 PR、GitHub Actions 运行和 Release 后重新同步。
3. 下一阶段实现真实 Release Notes 草稿工作流。
