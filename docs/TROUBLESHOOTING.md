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
