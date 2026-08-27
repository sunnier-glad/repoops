# 简历项目描述

## 后端 / AI 应用方向

**GitHub 项目协作与发布质量平台｜RepoOps**　FastAPI、Vue 3、PostgreSQL、Redis、Celery、GitHub API、LLM

- 基于 GitHub OAuth、Webhook 和 API 构建项目协作与发布质量平台，支持仓库绑定、PR、CI 失败和 Release 状态统一查看。
- 使用 HMAC-SHA256 校验 Webhook，并以 `repository_id + delivery_id` 做事件幂等；接收接口先保存原始 payload，再异步处理耗时任务。
- 设计 PR、Workflow Run、Release 和 Job 数据模型，按用户授权范围过滤查询；GitHub Token 和 Webhook Secret 加密保存。
- 接入 Celery/Redis 执行事件处理、PR 摘要、CI 失败解释和 Release Notes 草稿；AI 输出异常独立记录，不影响原始业务状态。
- 使用 pytest、Vitest、Ruff、Alembic 和 GitHub Actions 验证认证、签名、幂等、权限、任务和前端构建链路。

## 通用后端方向

- 负责 GitHub OAuth、仓库绑定、Webhook 入库、事件幂等和 PR/CI/Release 状态流转的后端实现。
- 通过 SQLAlchemy/Alembic 建立用户、仓库、事件、PR、Workflow Run、Release 和任务模型，使用服务端权限过滤避免越权查询。
- 使用 Redis/Celery 隔离 Webhook 接收与后台处理，任务失败可追踪，LLM 失败不回滚 GitHub 原始数据。

## 面试真实性边界

当前已验证：后端 `28 passed`、前端 `3 passed`、Ruff 全部通过、Alembic 可升级到 `0004_jobs_ai`、Vite production build 成功、Compose 配置可解析。Docker 镜像构建仍需在 Docker daemon 启动后复验，不能在简历中写“已完成生产部署”。
