# 真实数据验收记录

本文只记录真实 GitHub 数据和可复现的验收证据，不使用演示数据填充产品页面。

## 验收对象

| 项目 | 值 |
| --- | --- |
| RepoOps | https://github.com/sunnier-glad/repoops |
| 真实验收仓库 | https://github.com/sunnier-glad/life-deadline-radar |
| 本地预览入口 | `http://localhost:5174/`（无需服务器） |
| API 健康检查 | `GET /api/health` |
| Webhook 模式 | 本地 `false`；公网 HTTPS 后才开启 |

## 已完成证据

- RepoOps 已创建为公开 GitHub 仓库，并推送到 `main`。
- RepoOps GitHub Actions `CI` 已通过：
  https://github.com/sunnier-glad/repoops/actions/runs/33383914687
- 本地真实数据模式已移除演示记录和演示入口；空 PR、CI、Release 结果代表 GitHub 当前真实状态。
- API、前端、数据库迁移、Webhook 签名/幂等、质量门禁和 Release Notes 草稿均有自动化测试覆盖。
- 本地 Docker Compose 可以完成 PostgreSQL、Redis、API、Worker 和前端联调，不依赖 Ubuntu 服务器；未启用公网 Webhook 时使用 GitHub API 手动同步。

## 验收矩阵

| 场景 | 数据来源 | 预期结果 | 状态 |
| --- | --- | --- | --- |
| OAuth 登录 | GitHub OAuth | 创建会话并返回前端 | 已验证 |
| 仓库绑定 | GitHub `/user/repos` | 只绑定当前账号可访问仓库 | 已验证 |
| 手动同步 | GitHub PR/Actions/Release API | 页面与 GitHub 当前状态一致 | 已验证，当前仓库可能为 0 |
| PR 详情 | 真实 Pull Request | 出现在 PR 协作详情 | 待真实 PR |
| CI 失败 | 真实 Workflow Run | 出现在 CI 失败详情并阻塞门禁 | 待真实 Workflow |
| Release | 真实 GitHub Release | 出现在 Release 详情并作为发布记录 | 待真实 Release |
| Webhook | GitHub HTTPS Webhook | 签名校验、delivery 幂等、异步处理 | 无服务器模式不验收；待公网 HTTPS |
| AI 润色 | 配置的 LLM API | 生成可审阅建议，不覆盖草稿 | 待线上 Key 验收 |

## 复现命令

```bash
docker compose config --quiet
docker compose up -d --build
curl -f http://127.0.0.1:8000/api/health
curl -f http://127.0.0.1:5174/api/health
```

登录并绑定仓库后，在页面点击“同步仓库数据”。验收时应同时保留：

1. GitHub 原始 PR、Workflow Run、Release 页面链接；
2. RepoOps 对应详情页截图；
3. 同步前后的数量变化；
4. 失败场景下的错误提示和原始链接。

## 结论口径

在真实 PR、Workflow Run、Release 尚未产生前，只能证明“空数据同步正确”，不能声称已完成非空业务验收。没有公网 HTTPS 时，只能证明手动同步链路，不能声称实时 Webhook 已上线。
