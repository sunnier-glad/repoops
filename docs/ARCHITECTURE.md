# RepoOps 架构说明

## 主链路

```text
GitHub OAuth → FastAPI Session → 仓库绑定 → GitHub Webhook
                                      ↓
                         原始事件 + delivery 幂等
                                      ↓
                          Redis/Celery 异步处理
                                      ↓
                  PR / Workflow Run / Release 状态
                                      ↓
                         Vue 质量工作台 + AI 草稿
```

## 关键设计

- OAuth 使用 Session 保存内部用户 ID，GitHub access token 使用 Fernet 加密后保存，不写入日志或前端 localStorage。
- Webhook 先读取原始字节，使用 `X-Hub-Signature-256` 做 HMAC-SHA256 常量时间比较；通过后才保存事件。
- `repository_id + delivery_id` 唯一约束保证重复投递不会产生第二条事件；重复请求仍快速返回 202。
- EventService 先保留原始 payload，再幂等更新 PR、Workflow Run、Release。AI 只新增分析记录，不覆盖原始状态。
- 所有质量查询先按当前用户拥有的 Repository 过滤，客户端传入的 owner 或仓库名不作为权限依据。
- 任务只传递内部 ID，Worker 从数据库读取数据；这样不会把 access token 放入 Redis 消息。

## 当前边界

第一版不自动修复代码、不自动提交、不自动合并、不自动发布。AI 的输出是 PR 摘要、CI 失败解释和 Release Notes 草稿，用户可以继续编辑和确认。
