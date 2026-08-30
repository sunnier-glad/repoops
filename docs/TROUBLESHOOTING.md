# RepoOps 排障清单

## OAuth 回调失败

- 检查 GitHub OAuth App 的 callback URL 是否与 `GITHUB_REDIRECT_URI` 完全一致。
- 检查 `SESSION_SECRET` 是否稳定；更换 Secret 会使旧 Session 失效。
- 生产环境确认 `GITHUB_TOKEN_ENCRYPTION_KEY` 是有效的 Fernet key，不能留空。

## Webhook 返回 401 或 400

- 401：检查 GitHub Secret 与绑定仓库的 Secret 是否一致，且请求体没有被代理改写。
- 400：检查 `X-GitHub-Delivery`、`X-GitHub-Event` 和 `X-Hub-Signature-256` 请求头。
- 重复 delivery 返回 202 且 `duplicate=true` 是预期行为。

## GitHub API 403/429

- 403 通常表示 OAuth App scope 或仓库权限不足；不要用客户端传来的仓库 owner 绕过服务端校验。
- 429 时保留 `Retry-After`，由异步任务重试；不要在 Webhook 请求线程等待。

## Celery 没有消费任务

- 确认 Redis 健康检查返回 `PONG`。
- 确认 API 和 Worker 使用相同的 `REDIS_URL`，并设置 `CELERY_ENABLED=true`。
- 查看 Worker 日志，任务只应出现内部 ID，不应出现 GitHub access token。

## Docker 构建失败

- Windows 先确认 Docker Desktop 的 Linux daemon 已启动，再运行 `docker compose build`。
- Compose 文件本身可用 `docker compose config --quiet` 做无启动校验。
- 如果 Docker Hub 拉取超时，先检查 Docker Desktop 的 HTTP/HTTPS 代理；构建成功后可用 `docker compose ps`、`http://localhost:8000/api/health` 和 `http://localhost:5174/api/health` 验证完整本地联调。

## 绑定仓库提示 Validation Failed

- GitHub 仓库列表能加载但绑定失败，通常是 `GITHUB_WEBHOOK_BASE_URL` 使用了 `localhost`，GitHub 无法验证本机 Webhook 地址。
- 本机真实数据联调可将 `GITHUB_WEBHOOK_ENABLED=false`，绑定仍会保存仓库，但不会注册远程 Webhook；页面通过“同步仓库数据”拉取 GitHub 真实记录。
- 生产环境将该开关设为 `true`，并使用公网 HTTPS 地址；修改 `.env` 后执行 `docker compose up -d`。

## 同步完成但所有指标为 0

- 先确认 GitHub 仓库确实存在开放 PR、Workflow Run 或 Release；空仓库返回 0 是正常结果。
- 在 GitHub 产生真实 PR、CI 或 Release 后，回到 RepoOps 点击“同步仓库数据”。页面不会生成或加载演示记录。
- 若需要实时更新，检查 Webhook 是否开启、回调地址是否为公网 HTTPS，以及 GitHub Webhook delivery 是否返回 202。
