# 邮件分类与草稿模板

适用：接收调用方提供的邮件文本，分类并生成回复草稿；高优先级、敏感或含糊请求进入人工复核。不包含邮箱接入、收件轮询或邮件发送。

## 导出与依赖

新环境先导入 [错误处理工作流](../../workflows/w6d41-workflow-error-handler.json)，再导入 [持久化邮件助手](../../workflows/w6d41-persistent-ai-email-assistant.json)。在主流程 Settings 的 Error Workflow 中选定前者，按原部署说明启用。Error Trigger 的真实失败落库能力以生产执行为准，不能用手动 Test 执行替代该验收。

依赖 API、SQLite 和已发布 Dify 企业咨询工作流；Dify 配置由 API 提供，不在 n8n 节点中粘贴 API Key。

入口：POST `/webhook-test/w6d41-persistent-ai-email-assistant`；已发布时使用 `/webhook/w6d41-persistent-ai-email-assistant`。

## 输入

| 字段 | 调用方约定 |
| --- | --- |
| event_id | 必填；新业务事件使用新标识，同一事件保持不变 |
| requester | 必填请求者；建议使用英文字母、数字、点、下划线、冒号、连字符 |
| subject / body | 必填邮件标题与正文；空缺、过短或含糊内容不能视为可自动回复 |
| priority | 可选，默认 normal；high/urgent/critical 会触发人工复核 |
| source / received_at | 可选来源及接收时间 |
| replay | 可选布尔值，默认 false；仅在确认需要失败回放时使用 true |

样例：[常规草稿](examples/normal.json)、[高优先级人工复核](examples/human-review.json)。人工复核样例的路由依据为 priority=high，具体分类可随内容而变化。工作流先登记运行再分类，因此不能承诺所有无效字段均返回统一 HTTP 422。

## 输出与恢复

主要输出 status、category、draft_reply、need_human_review、workflow_run_id、persisted_status。人工复核时 draft_reply 为空。workflow_run_id 是平台运行 ID；Dify 耗时与 Token 在 AI 草稿分支提供，人工复核和重复分支使用原有零值约定。

业务名称为 `w6d41_ai_email_assistant`；平台按 workflow_name 与 event_id 去重。重复请求不再生成草稿。仅 failed 运行可显式 replay，最多 3 次，复用首次保存的输入。错误处理需正确绑定，不能凭一次 HTTP 200 代替查看业务状态。

历史依据见 [持久化与回放说明](../../../docs/n8n-workflow-persistence.md)。

## Day 52 配置归属

模型由对应的 Dify 应用节点与凭据选择；后端 `LLM_PROVIDER` 不影响本模板。后端用 `DIFY_WORKFLOW_API_KEY` 和 `DIFY_API_BASE_URL` 连接已发布的 Dify 工作流。可在项目根目录运行 `.\.venv\Scripts\python.exe -m backend.app.check_config --component dify` 检查本地调用配置；这不验证 Dify 内部模型或网络连通性。

配置优先级、完整字段与生效方式见 [配置中心说明](../../../docs/week-8-notes.md#day52)。
