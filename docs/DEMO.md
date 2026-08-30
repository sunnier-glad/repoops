# RepoOps 真实数据联调脚本

## 启动

1. 复制 `.env.example` 为 `.env`，填写 GitHub OAuth、Session Secret 和 Fernet 密钥。
2. 启动 `docker compose up -d --build`。
3. 打开 `http://localhost:5174`，点击 GitHub 登录。
4. 登录后在“选择工作仓库”面板选择并绑定真实仓库，再点击“同步仓库数据”。

本机开发可将 `GITHUB_WEBHOOK_ENABLED=false`，绑定会保存仓库并通过 GitHub API 手动同步真实数据。要接收真实 GitHub Webhook，必须将开关设为 `true`，并把 `GITHUB_WEBHOOK_BASE_URL` 设置为 GitHub 可访问的公网 HTTPS 地址；`localhost` 不能作为 GitHub 回调地址。

## 联调顺序

1. 展示 OAuth 登录后 `/api/auth/me` 只返回用户标识，不返回 access token。
2. 选择一个可访问仓库，说明绑定前会重新调用 GitHub `/user/repos` 校验权限。
3. 在 GitHub 创建真实 PR，点击“同步仓库数据”，确认 PR 出现在协作列表。
4. 触发一次真实 CI 失败，确认失败 Workflow 出现在失败任务列表。
5. 发布一个真实 Release，确认版本记录出现在 Release 列表。
6. 若开启 Webhook，推送提交、更新 PR 或发布 Release 后检查事件流和异步任务；重复 delivery 不产生重复数据。

## 面试时的主线

“我把 GitHub 的不可靠外部事件拆成了接收层、状态层和分析层。接收层只做签名、幂等和落盘，状态层负责 PR/CI/Release 事务更新，分析层异步生成可失败的草稿。这样第三方 API 或 LLM 出问题时，原始事件和质量状态仍然可追溯。”
