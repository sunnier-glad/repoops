# Ubuntu 部署手册

本文同时覆盖本地无服务器运行和 Ubuntu 部署。当前没有域名，因此优先使用本地真实验收：

- **本地无服务器模式（推荐当前使用）**：Docker Compose 在本机运行全部依赖，通过 GitHub API 手动同步真实数据。
- **服务器 IP 预览**：可以验证远程容器、数据库、前端和 API 的运行，但不开启公网 Webhook。
- **正式公网环境**：需要域名和 HTTPS，才能稳定使用 GitHub OAuth 回调和实时 Webhook。

## 0. 本地无服务器模式

不需要 Ubuntu、域名或公网 IP。准备 Docker Desktop 后，在项目根目录执行：

```powershell
Copy-Item .env.example .env
docker compose up -d --build
docker compose ps
curl.exe -f http://127.0.0.1:8000/api/health
curl.exe -f http://127.0.0.1:5174/api/health
```

`.env` 至少设置以下内容：

```dotenv
APP_ENV=development
CELERY_ENABLED=true
GITHUB_REDIRECT_URI=http://localhost:8000/api/auth/github/callback
FRONTEND_URL=http://localhost:5174/
GITHUB_WEBHOOK_ENABLED=false
```

浏览器打开 `http://localhost:5174/`，登录 GitHub、绑定验收仓库，然后点击“同步仓库数据”。该流程读取真实 PR、CI 和 Release，不需要服务器；GitHub 产生新事件后再次手动同步即可。

本地模式的明确边界是：不接收实时 Webhook，不提供公网访问，不等同于线上部署。它足以完成项目功能验收、截图、录屏和简历展示。

## 1. 服务器准备

建议 Ubuntu 22.04/24.04，至少 2 核、4 GB 内存和 20 GB 可用磁盘。安装 Docker Engine 与 Docker Compose Plugin，并确认：

```bash
docker --version
docker compose version
```

服务器只需要对外开放 SSH，以及预览或反向代理需要的 HTTP/HTTPS 端口。PostgreSQL 和 Redis 不应直接暴露到公网。

## 2. 获取代码

```bash
git clone https://github.com/sunnier-glad/repoops.git
cd repoops
cp .env.example .env
```

生产环境不要把密钥写入 Git。`.env` 只保存在服务器，并限制权限：

```bash
chmod 600 .env
```

## 3. 配置环境变量

### 无域名：服务器 IP 预览

先使用手动同步真实 GitHub 数据：

```dotenv
APP_ENV=production
APP_VERSION=0.1.0
POSTGRES_DB=repoops
POSTGRES_USER=repoops
POSTGRES_PASSWORD=生成一个只含字母数字的强密码
DATABASE_URL=postgresql+psycopg://repoops:同一个密码@postgres:5432/repoops
REDIS_URL=redis://redis:6379/0
CELERY_ENABLED=true
SESSION_SECRET=随机长字符串
GITHUB_CLIENT_ID=你的 GitHub OAuth App Client ID
GITHUB_CLIENT_SECRET=你的 GitHub OAuth App Client Secret
GITHUB_REDIRECT_URI=http://服务器IP:8000/api/auth/github/callback
FRONTEND_URL=http://服务器IP:5174/
GITHUB_WEBHOOK_ENABLED=false
GITHUB_WEBHOOK_BASE_URL=http://服务器IP:8000
GITHUB_TOKEN_ENCRYPTION_KEY=Fernet 密钥
LLM_BASE_URL=https://api.deepseek.com
LLM_API_KEY=可选的 LLM Key
LLM_MODEL=deepseek-chat
```

此模式通过“同步仓库数据”调用 GitHub API，不注册 Webhook。它适合没有域名时的部署验收，不应包装成实时生产环境。

### 有域名：正式公网环境

将上面的地址替换为 HTTPS 域名：

```dotenv
GITHUB_REDIRECT_URI=https://repoops.example.com/api/auth/github/callback
FRONTEND_URL=https://repoops.example.com/
GITHUB_WEBHOOK_ENABLED=true
GITHUB_WEBHOOK_BASE_URL=https://repoops.example.com
```

GitHub OAuth App 的回调地址必须与 `GITHUB_REDIRECT_URI` 完全一致。正式环境还需要在服务器前置 TLS 反向代理，并把 `/` 转发到前端容器、`/api/` 转发到 API 容器。

## 4. 启动与检查

```bash
docker compose config --quiet
docker compose up -d --build
docker compose ps
curl -f http://127.0.0.1:8000/api/health
curl -f http://127.0.0.1:5174/
docker compose logs --tail=100 api worker
```

API 容器启动时会执行 `alembic upgrade head`。只有 API 健康、Worker 正常运行且数据库迁移完成后，才进入 GitHub OAuth 验收。

## 5. 真实数据验收顺序

1. 浏览器打开 `http://服务器IP:5174/`，完成 GitHub 登录。
2. 绑定 `sunnier-glad/life-deadline-radar`，确认仓库权限校验成功。
3. 无域名模式点击“同步仓库数据”，确认页面只展示 GitHub 返回的数据。
4. 在 GitHub 产生真实 PR、CI Workflow Run 和 Release 后再次同步，核对详情页、质量门禁和发布草稿来源。
5. 有 HTTPS 地址时再开启 Webhook，检查签名校验、delivery 幂等和异步任务。

## 6. 日常运维

```bash
# 查看状态和日志
docker compose ps
docker compose logs -f api
docker compose logs -f worker

# 更新版本
git pull --ff-only
docker compose up -d --build

# 停止应用（不会删除数据库卷）
docker compose down
```

备份 PostgreSQL 前先确认服务器磁盘空间和备份位置：

```bash
docker compose exec -T postgres pg_dump -U repoops -d repoops > repoops-$(date +%F).sql
```

不要使用 `docker compose down -v`，它会删除数据库和 Redis 数据卷。

## 7. 部署边界

- 没有域名时只能完成服务器 IP 预览和 API 手动同步验收。
- GitHub OAuth、Webhook Secret、LLM Key 和数据库密码不进入镜像、不提交仓库、不写入截图。
- 当前部署方案不包含自动发布、自动合并、自动修改代码或自动申请证书。
- 真正公网发布前，需要补充域名、HTTPS、备份策略、日志轮转和服务器防火墙规则。
