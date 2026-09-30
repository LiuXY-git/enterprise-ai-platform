# 客服咨询模板

适用：基于已有企业知识库资料回答咨询。不适用：需要 n8n 平台账本、事件去重、CRM 写入或自动建工单的场景。

## 导出与依赖

导入 [W6D38 客服工作流](../../workflows/w6d38-ai-customer-request.json)。先准备 API、独立部署并已发布的 Dify 企业咨询工作流，以及该流程所需知识库。此模板不需要 n8n 模型 Credential；Dify 密钥由 API 持有。

入口：POST `/webhook-test/w6d38-ai-customer-request`；已发布时使用 `/webhook/w6d38-ai-customer-request`。旧流程保持 reference 层级，按需启用。

## 输入

| 字段 | 调用方约定 |
| --- | --- |
| request_id | 非空请求标识，仅用于关联；不会触发幂等拦截 |
| customer_id | 非空；传给 Dify user，仅使用字母、数字、点、下划线、冒号、连字符 |
| message | 非空咨询内容 |
| priority | 可选，省略时 normal；该模板不因 high 自动转人工 |

可选 query.channel 和请求头 X-Client-Name 用于来源信息。旧 Normalize 节点主要映射字段，不提供与销售模板相同的严格校验；调用方按上表准备输入，不能将 accepted=true 当成完整输入验证结果。

样例：[资料咨询](examples/question.json)、[资料缺失问题](examples/unknown-answer.json)。第二个样例用于未来观察资料不足时的回答，不承诺具体文本或固定分支，也未在 Day 50 调用模型验证。

## 输出与失败

主要输出 answer、ai_status、task_id、workflow_run_id、elapsed_time、total_tokens。这里 workflow_run_id 是 **Dify 运行 ID**，不能拿它查询平台 `/workflow-runs/{run_id}`。answer 的具体内容由知识库与模型决定。

此模板没有平台去重或检查点恢复，每次再次调用都可能再次调用 Dify。失败按现有 API/n8n 错误信息处理，不把失败重发描述为幂等重试。历史依据见 [Day 38 集成说明](../../../docs/week-6.md#n8n-ai-integration)。

## Day 52 配置归属

模型由对应的 Dify 应用节点与凭据选择；后端 `LLM_PROVIDER` 不影响本模板。后端用 `DIFY_WORKFLOW_API_KEY` 和 `DIFY_API_BASE_URL` 连接已发布的 Dify 工作流。可在项目根目录运行 `.\.venv\Scripts\python.exe -m backend.app.check_config --component dify` 检查本地调用配置；这不验证 Dify 内部模型或网络连通性。

配置优先级、完整字段与生效方式见 [配置中心说明](../../../docs/week-8.md#day52)。
