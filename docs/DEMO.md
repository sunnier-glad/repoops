# RepoOps 演示脚本

## 启动

1. 复制 `.env.example` 为 `.env`，填写 GitHub OAuth、Session Secret 和 Fernet 密钥。
2. 启动 `docker compose up -d --build`。
3. 打开 `http://localhost:5174`，点击 GitHub 登录。
4. 登录后在“选择工作仓库”面板选择并绑定一个测试仓库，再在 GitHub Webhook 设置中确认回调地址可达。

本地演示时可将 `GITHUB_WEBHOOK_ENABLED=false`，这样绑定会保留仓库但跳过远程 Webhook 注册，界面会显示“Webhook 待配置”。要接收真实 GitHub 事件，生产环境必须改为 `true`，并将 `GITHUB_WEBHOOK_BASE_URL` 设置为公网 HTTPS 地址。

## 演示顺序

1. 展示 OAuth 登录后 `/api/auth/me` 只返回用户标识，不返回 access token。
2. 选择一个可访问仓库，说明绑定前会重新调用 GitHub `/user/repos` 校验权限。
3. 推送一次提交，展示 Webhook 返回 202、delivery ID 入库和异步任务。
4. 打开一个 PR，展示 PR 状态和摘要任务；重复发送同一个 delivery，展示不产生重复数据。
5. 触发一次失败 CI，展示失败列表、Workflow Run 状态和 AI 解释失败时的独立错误状态。
6. 发布一个测试 Release，展示版本记录和 Release Notes 草稿；强调不会自动发布回 GitHub。

## 面试时的主线

“我把 GitHub 的不可靠外部事件拆成了接收层、状态层和分析层。接收层只做签名、幂等和落盘，状态层负责 PR/CI/Release 事务更新，分析层异步生成可失败的草稿。这样第三方 API 或 LLM 出问题时，原始事件和质量状态仍然可追溯。”
