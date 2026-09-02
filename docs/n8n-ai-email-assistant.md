# Day 39：n8n AI 邮件助手

## 学习目标

Day 39 在 Day 38 AI 请求闭环的基础上实现一个安全的邮件处理场景，目标包括：

- 接收统一格式的模拟邮件事件
- 规范化主题、正文、发件人、优先级和来源信息
- 对邮件执行规则分类与风险判断
- 将高优先级、敏感、模糊或字段不完整的邮件转交人工复核
- 仅对低风险邮件调用 FastAPI / Dify 生成回复草稿
- 让人工分支与 AI 分支返回相同的 JSON 契约
- 将脱敏后的 n8n 工作流和自动化结构测试纳入 Git

开发分支：

```text
feature/n8n-ai-email-assistant
```

工作流名称：

```text
W6D39 - AI Email Assistant
```

## 场景边界

Day 39 使用 Webhook 模拟邮件事件，不连接 Gmail、Outlook、IMAP 或 SMTP，也不会自动发送邮件。工作流只生成回复草稿或人工复核任务，因此无需把邮箱账号、OAuth Token 或邮件系统 Credential 保存到 n8n 导出文件中。

该边界适合先验证分类、路由和 AI 草稿逻辑。连接真实邮箱和发送动作前，还需要补充调用方认证、权限最小化、审计、幂等和人工批准机制。

## 架构

```text
模拟邮件事件
    ↓
n8n Webhook
    ↓
字段规范化
    ↓
规则分类与风险判断
    ↓
是否需要人工复核？
    ├─ 是 → 构造人工复核响应 ─┐
    └─ 否 → FastAPI / Dify → 构造 AI 草稿响应
                                  ↓
                         HTTP JSON Response
```

人工分支不会调用 AI。这既减少不必要的模型调用，也避免把敏感、投诉、退款或字段不完整的邮件继续发送到下游模型。

## Webhook 输入契约

Webhook Path：

```text
w6d39-ai-email-assistant
```

请求体字段：

| 字段 | 必填 | 说明 |
|---|---|---|
| `event_id` | 是 | 邮件事件的唯一标识 |
| `requester` | 是 | 发件人标识；调用 AI 前会转换为安全的 `user` 值 |
| `subject` | 是 | 邮件主题 |
| `body` | 是 | 邮件正文 |
| `priority` | 否 | `low`、`normal`、`high`、`urgent` 或 `critical` |
| `source` | 否 | 事件来源，默认使用请求头或 `mock-email` |
| `received_at` | 否 | 上游接收时间，缺省时使用当前时间 |

Query 参数 `channel` 默认为 `email`。请求体没有 `source` 时，工作流依次尝试请求头 `X-Client-Name` 和默认值 `mock-email`。

低风险产品咨询示例：

```json
{
  "event_id": "mail-day39-001",
  "requester": "customer-001@example.test",
  "subject": "文档格式咨询",
  "body": "请问系统支持上传哪些文档格式？",
  "priority": "normal",
  "source": "mock-email"
}
```

需要人工复核的示例：

```json
{
  "event_id": "mail-day39-002",
  "requester": "customer-002@example.test",
  "subject": "退款投诉",
  "body": "我要投诉并申请退款，请安排人工处理。",
  "priority": "urgent",
  "source": "mock-email"
}
```

示例使用保留域名 `example.test`，不包含真实个人邮箱。

## 工作流节点

Day 39 工作流包含 8 个节点和 7 个连接：

```text
Receive Customer Request
    ↓
Normalize Email Request
    ↓
Classify Email Request
    ↓
Needs Human Review?
    ├─ true  → Build Human Review Response ─┐
    └─ false → Call AI Workflow             │
                  ↓                         │
             Build Email Draft Response     │
                  └──────────────┬──────────┘
                                 ↓
                      Return JSON Response
```

### Receive Customer Request

| 参数 | 值 |
|---|---|
| HTTP Method | `POST` |
| Path | `w6d39-ai-email-assistant` |
| Authentication | `None` |
| Respond | `Using 'Respond to Webhook' Node` |

无认证 Webhook 只适用于绑定在 `127.0.0.1` 的本地学习环境。验收后应保持未发布状态。

### Normalize Email Request

该节点输出 14 个受控字段，并关闭 `Include Other Input Fields`，避免把原始 Header、Cookie 或其他无关字段传给分类和 AI 节点。

主题与正文组合为发送给 AI 的 `message`：

```text
subject

body
```

### Classify Email Request

Code 节点先校验必填字段并规范化优先级，再按以下优先顺序分类：

1. `sensitive`：命中敏感、投诉、退款、法律或个人数据关键词。
2. `technical`：命中 API、HTTP、错误、部署、容器、超时等技术关键词。
3. `product`：命中文档格式、上传、功能、价格、知识库等产品关键词。
4. `other`：没有命中以上规则。

以下任一条件会进入人工复核：

- 缺少 `event_id`、`requester`、`subject` 或 `body`
- 优先级为 `high`、`urgent` 或 `critical`
- 命中敏感关键词
- 正文过短、整体内容过短或命中模糊表达

对应的 `review_reason` 值包括：

```text
missing_required_fields
high_priority
sensitive_content:<keyword>
ambiguous_request
```

多个原因使用逗号连接。

### Needs Human Review?

IF 节点以布尔值 `need_human_review` 路由：

- true 输出连接 `Build Human Review Response`
- false 输出连接 `Call AI Workflow`

### Build Human Review Response

人工分支不调用 AI，并返回：

```text
draft_reply = ""
need_human_review = true
status = needs_human_review 或 invalid_request
next_step = human_review 或 request_correction
```

AI 运行信息使用空字符串或 `0`，使两个分支维持统一响应结构。

### Call AI Workflow

低风险邮件通过 Docker Compose 内部服务名调用 FastAPI：

```text
POST http://api:8000/dify/workflow
```

核心配置：

| 参数 | 值 |
|---|---|
| Body Content Type | JSON |
| `question` | 规范化后的主题和正文 |
| `user` | 清理后的 `requester` |
| Timeout | `120000` 毫秒 |

`requester` 中不符合 FastAPI 用户标识约束的字符会替换为下划线。Dify API Key 仍只由 FastAPI 服务端读取，n8n 不保存模型密钥。

### Build Email Draft Response

AI 分支把 FastAPI 响应中的回答、运行 ID、耗时、Token 和步骤数与邮件元数据组合为稳定结果：

```text
draft_reply = answer
need_human_review = false
review_reason = ""
next_step = completed
```

### Return JSON Response

两个分支最终都返回 21 个字段，HTTP 状态码为 `200`：

```text
accepted
day
event_id
source
requester
category
priority
summary
draft_reply
need_human_review
review_reason
status
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

业务状态通过 `accepted`、`status`、`need_human_review` 和 `next_step` 表达。调用方不应只依据 HTTP `200` 判断邮件是否已自动处理。

## 本地运行态验收

启动服务：

```powershell
docker compose up -d
docker compose ps
```

2026-09-02 容器级回归结果：

```text
API container = healthy
n8n container = healthy
GET /health = 200
GET n8n /healthz = 200
FastAPI -> Dify HTTP status = 200
FastAPI -> Dify status = succeeded
AI answer / task ID / workflow run ID = present
AI workflow total steps = 6
```

回归使用独立测试用户 `day39-runtime-check`，不包含真实个人信息。真实 AI 链路耗时约 6.8 秒。

### Test URL

在 n8n 中点击 `Listen for test event` 后发送低风险样例：

```text
POST http://127.0.0.1:5678/webhook-test/w6d39-ai-email-assistant?channel=email-test
```

预期低风险路径：

```text
category = product
need_human_review = false
draft_reply 非空
next_step = completed
```

再次监听 Test URL 并发送人工复核样例，预期：

```text
category = sensitive
priority = high
need_human_review = true
draft_reply = ""
next_step = human_review
```

### Production URL

仅在本地验收窗口内发布工作流：

```text
POST http://127.0.0.1:5678/webhook/w6d39-ai-email-assistant?channel=production-check
```

完成后立即取消发布。再次调用 Production URL 应返回 `404`，证明生产 Webhook 已注销。

本次回归中 Production URL 返回 `404` 和 `not registered`，确认 Day 39 工作流当前保持未发布状态。

## 导出、脱敏与版本控制

工作流导出到：

```text
n8n/workflows/w6d39-ai-email-assistant.json
```

进入 Git 前执行以下处理：

- 删除顶层 `id`、`versionId` 和 `meta`
- 删除 Webhook 节点的 `webhookId`
- 保留节点 ID、条件 ID 和 assignment ID，避免破坏编辑关系
- 保持 `active: false`
- 保持 `pinData` 为空
- 确认没有 Credential 引用、真实密钥或真实邮箱样例
- 使用 UTF-8 无 BOM 编码

仓库中的自动化测试覆盖：

- 脱敏字段与 inactive 状态
- 工作流名称、节点数、连接数和 Webhook 契约
- IF 节点 true/false 分支方向
- 所有连接端点均引用现有节点
- 四类人工复核原因
- 两个分支一致的 21 字段响应契约
- FastAPI 内部 AI 调用边界

## 当前限制

- Webhook 尚未增加认证、签名校验、限流和重放保护
- 分类规则基于关键词，不能代替合规或客服策略引擎
- `event_id` 尚未落库，当前没有幂等去重
- AI 分支尚未增加超时或下游失败的显式 JSON 错误分支
- 人工复核结果只通过响应返回，尚未进入工单队列
- 工作流只生成草稿，不读取真实邮箱，也不自动发送邮件

## Day 39 验收清单

| 验收项 | 结果 |
|---|---|
| 8 节点、7 连接工作流 | 通过 |
| Webhook 输入规范化 | 通过 |
| 邮件分类规则 | 通过 |
| 人工复核分支 | 通过 |
| 低风险 AI 草稿分支 | 通过 |
| 两分支 21 字段响应契约 | 通过 |
| FastAPI / Dify 密钥边界 | 通过 |
| API 与 n8n 容器健康 | 通过 |
| FastAPI / Dify 真实 AI 链路 | 通过 |
| Production Webhook 未发布 404 | 通过 |
| 工作流保持 inactive | 通过 |
| 顶层实例 ID 清理 | 通过 |
| Webhook ID 清理 | 通过 |
| 无 Credential 引用 | 通过 |
| UTF-8 无 BOM | 通过 |
| 自动化结构测试 | 通过 |

## Day 39 总结

Day 39 将通用 AI 请求闭环扩展成可审慎处理邮件的业务自动化：低风险邮件进入 AI 草稿生成，高风险或信息不足的邮件进入人工复核。工作流没有连接真实邮箱，也不会自动发送回复，保留了明确的人机协作边界。

## 相关文档

- [Day 38：n8n 连接 AI 工作流](n8n-ai-integration.md)
- [Day 37：n8n Webhook 触发与请求响应](n8n-webhook-trigger.md)
- [FastAPI 调用 Dify 工作流](dify-fastapi-integration.md)
- [API 文档](api.md)
