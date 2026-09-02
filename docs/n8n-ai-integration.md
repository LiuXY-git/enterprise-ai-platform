# Day 38：n8n 连接 AI 工作流

## 学习目标

Day 38 在 Day 37 Webhook 请求闭环的基础上接入真实 AI 处理能力，目标包括：

- 使用 n8n HTTP Request 节点调用内部 FastAPI 接口
- 将规范化后的客户消息映射为 AI 工作流请求
- 复用 FastAPI 已有的 Dify 服务端密钥与错误边界
- 将 AI 回答、运行标识和 Token 统计整理成稳定 JSON 响应
- 验证 Test URL 与 Production URL 的完整执行链路
- 在验收后取消发布，并将工作流安全导出到 Git

开发分支：

```text
feature/n8n-llm-integration
```

工作流名称：

```text
W6D38 - AI Customer Request Processing
```

## 架构

```text
HTTP 调用方
    ↓
n8n Webhook
    ↓
请求字段规范化
    ↓
POST http://api:8000/dify/workflow
    ↓
FastAPI
    ↓
Dify 企业咨询工作流
    ↓
知识库检索与 LLM 回答
    ↓
n8n 整理响应
    ↓
HTTP JSON Response
```

n8n 与 FastAPI 位于同一个 Docker Compose 网络中，因此 n8n 使用服务名 `api` 访问后端：

```text
http://api:8000
```

不能在 n8n 容器中使用 `http://localhost:8000`，因为容器内的 `localhost` 指向 n8n 容器自身。

## 集成边界

Day 38 不在 n8n 中保存模型或 Dify API Key。n8n 只调用内部 FastAPI 接口：

```text
POST /dify/workflow
```

FastAPI 负责：

- 从服务端环境变量读取 Dify 应用 Key
- 调用已发布的 Dify 企业咨询工作流
- 统一处理超时、连接错误和无效响应
- 返回稳定的 AI 工作流响应模型

这种边界避免了在工作流 JSON 中出现真实密钥或 Credential 引用。

## Webhook 输入契约

Webhook Path：

```text
w6d38-ai-customer-request
```

请求示例：

```json
{
  "request_id": "req-day38-001",
  "customer_id": "customer-001",
  "message": "系统支持哪些文档格式？",
  "priority": "high"
}
```

Query 参数 `channel` 和请求头 `X-Client-Name` 继续沿用 Day 37 的输入契约。

## 工作流节点

Day 38 工作流包含 5 个节点和 4 条连接：

```text
Receive Customer Request
    ↓
Normalize Request
    ↓
Call AI Workflow
    ↓
Build AI Response
    ↓
Return JSON Response
```

### Receive Customer Request

| 参数 | 值 |
|---|---|
| HTTP Method | `POST` |
| Path | `w6d38-ai-customer-request` |
| Authentication | `None` |
| Respond | `Using 'Respond to Webhook' Node` |

该无认证 Webhook 只用于绑定在 `127.0.0.1` 的本地学习环境。验收完成后保持未发布状态。

### Normalize Request

该节点复用 Day 37 的请求字段映射，并将：

```text
day = 38
next_step = ai_processing
```

`Include Other Input Fields` 保持关闭，避免把原始 Header、Cookie 或其他无关字段继续传递。

### Call AI Workflow

节点类型：

```text
HTTP Request
```

核心配置：

| 参数 | 值 |
|---|---|
| Method | `POST` |
| URL | `http://api:8000/dify/workflow` |
| Authentication | `None` |
| Body Content Type | `JSON` |
| Timeout | `120000` 毫秒 |

请求体字段：

| 字段 | 表达式 |
|---|---|
| `question` | `{{ $json.message }}` |
| `user` | `{{ $json.customer_id }}` |

FastAPI 的 `user` 字段只允许字母、数字、点、下划线、冒号和连字符。Day 38 使用符合约束的测试客户标识。

### Build AI Response

HTTP Request 节点输出 AI 工作流结果。该节点将结果与 `Normalize Request` 中的原始请求元数据重新组合。

最终响应包含 19 个字段：

```text
accepted
day
request_id
customer_id
message
priority
channel
source
ai_status
answer
task_id
workflow_run_id
elapsed_time
total_tokens
total_steps
next_step
execution_mode
received_at
processed_at
```

其中：

```text
accepted = true
day = 38
next_step = completed
```

`Include Other Input Fields` 保持关闭，避免把 Dify 的完整原始输出直接暴露给 Webhook 调用方。

### Return JSON Response

该节点返回 `Build AI Response` 生成的第一个 item，并使用 HTTP 状态码 `200`。

## Test URL 验收

测试地址：

```text
POST http://127.0.0.1:5678/webhook-test/w6d38-ai-customer-request?channel=learning
```

验收结果：

```text
HTTP Status = 200
Content Length = 558
ai_status = succeeded
execution_mode = test
total_steps = 6
```

五个节点全部成功执行，每条连接传递一个 item。AI 回答正确说明系统支持 PDF、DOCX 和 Markdown。

## Production URL 验收

生产地址：

```text
POST http://127.0.0.1:5678/webhook/w6d38-ai-customer-request?channel=production-check
```

验收结果：

```text
HTTP Status = 200
Content Length = 595
ai_status = succeeded
execution_mode = production
Execution ID = 9
Execution Status = Succeeded
Execution Duration = 5.042 s
```

Production 执行记录中五个节点全部成功，每条连接传递一个 item。

## 取消发布验收

完成 Production 测试后取消发布工作流，再次调用 Production URL 返回：

```text
HTTP Status = 404
The requested webhook "POST w6d38-ai-customer-request" is not registered.
```

这证明 Production Webhook 已注销。取消发布不会删除工作流或执行记录。

## 导出与版本控制

工作流导出到：

```text
n8n/workflows/w6d38-ai-customer-request.json
```

进入 Git 前执行以下清理与验收：

- 删除顶层 `id`、`versionId` 和 `meta`
- 删除 Webhook 节点的 `webhookId`
- 保留所有节点 ID 和 Edit Fields assignment ID
- 保持 `active: false`
- 保持 `pinData` 为空
- 确认节点数量为 5、连接数量为 4
- 确认 AI 响应字段数量为 19
- 确认没有 Credential 引用或真实密钥
- 使用 UTF-8 无 BOM 编码

## 当前限制

- Webhook 尚未增加调用方认证与限流
- Day 38 使用受控的 `customer_id`，尚未增加格式校验节点
- AI 调用失败时由工作流停止执行，尚未建立面向调用方的错误响应分支
- 当前调用为阻塞模式，请求耗时取决于 Dify 工作流和模型响应时间

这些限制将在后续条件分支、输入校验和错误处理学习中继续完善。

## Day 38 验收结果

| 验收项 | 结果 |
|---|---|
| FastAPI 与 n8n 健康 | 通过 |
| FastAPI AI 链路预检 | 通过 |
| 五节点工作流 | 通过 |
| HTTP Request JSON 映射 | 通过 |
| 内部服务名访问 | 通过 |
| 19 字段 AI 响应 | 通过 |
| Test URL | 通过 |
| Production URL | 通过 |
| Production execution 记录 | 通过 |
| 取消发布后返回 404 | 通过 |
| 工作流保持 inactive | 通过 |
| 顶层实例 ID 清理 | 通过 |
| Webhook ID 清理 | 通过 |
| 无 Credential 引用 | 通过 |
| 无敏感信息 | 通过 |
| UTF-8 无 BOM | 通过 |

## Day 38 总结

Day 38 完成了从外部 HTTP 请求到真实 AI 回答的自动化闭环：

```text
HTTP 请求
    ↓
n8n 请求规范化
    ↓
FastAPI / Dify / Knowledge Hub / LLM
    ↓
n8n 响应整理
    ↓
HTTP JSON 回答
```

工作流复用了项目已有的 FastAPI 与 Dify 集成能力，同时保持模型密钥只存在于服务端配置中。Day 38 由此建立了可继续扩展条件分支、校验和错误处理的 AI 自动化基础。

下一步进入 [Day 39：n8n AI 邮件助手](n8n-ai-email-assistant.md)，在 AI 调用之前增加邮件分类与人工复核分支。

## 相关文档

- [Day 37：n8n Webhook 触发与请求响应](n8n-webhook-trigger.md)
- [Day 39：n8n AI 邮件助手](n8n-ai-email-assistant.md)
- [FastAPI 调用 Dify 工作流](dify-fastapi-integration.md)
- [API 文档](api.md)
- [n8n 基础与本地部署](n8n-foundation.md)
