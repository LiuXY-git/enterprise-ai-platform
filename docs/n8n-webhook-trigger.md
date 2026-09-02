# Day 37：n8n Webhook 触发与请求响应

## 学习目标

Day 37 的目标是掌握 n8n Webhook 触发机制，完成一个可以被外部 HTTP 请求调用的最小工作流闭环：

- 理解 Webhook Trigger 的作用
- 区分 Test URL 与 Production URL
- 接收 HTTP Header、Query 和 JSON Body
- 使用 Edit Fields 规范化请求数据
- 使用 Respond to Webhook 显式返回 JSON
- 验证测试模式与生产模式
- 理解发布、取消发布和安全边界
- 将工作流导出并纳入 Git 版本控制

Day 37 不调用 LLM。LLM 节点将在 Day 38 接入。

## 完成结果

本次创建的 n8n 工作流为：

```text
W6D37 - Customer Request Webhook
```

版本化文件为：

```text
n8n/workflows/w6d37-customer-request-webhook.json
```

功能分支为：

```text
feature/n8n-webhook-trigger
```

## 工作流架构

工作流包含三个节点：

```text
Receive Customer Request
          ↓
Normalize Request
          ↓
Return JSON Response
```

各节点职责如下：

| 节点 | 类型 | 职责 |
|---|---|---|
| `Receive Customer Request` | Webhook | 接收外部 POST 请求 |
| `Normalize Request` | Edit Fields | 提取并规范化 Header、Query 和 Body |
| `Return JSON Response` | Respond to Webhook | 返回 HTTP 200 JSON 响应 |

## Webhook 请求契约

### HTTP 方法与路径

```text
POST /w6d37-customer-request
```

Test URL：

```text
http://127.0.0.1:5678/webhook-test/w6d37-customer-request
```

Production URL：

```text
http://127.0.0.1:5678/webhook/w6d37-customer-request
```

Test URL 只在测试监听期间有效。

Production URL 只有在工作流发布后才会注册。

### 请求 Header

可选请求头：

```text
X-Client-Name
```

该值用于标识请求来源。

未提供时，工作流返回：

```text
source = unknown
```

### Query 参数

可选参数：

```text
channel
```

示例：

```text
?channel=learning
```

未提供时，工作流返回：

```text
channel = unknown
```

### JSON Body

请求体示例：

```json
{
  "request_id": "req-day37-001",
  "customer_id": "customer-001",
  "message": "How can I reset my password?",
  "priority": "high"
}
```

字段说明：

| 字段 | 是否必填 | 说明 |
|---|---:|---|
| `request_id` | 是 | 本次请求的唯一标识 |
| `customer_id` | 是 | 客户标识 |
| `message` | 是 | 客户请求内容 |
| `priority` | 否 | 请求优先级，默认值为 `normal` |

> 这里的“必填”表示调用约定。Day 37 工作流尚未实现必填字段校验；缺失字段时仍可能返回 HTTP 200。输入校验和错误分支将在后续学习中补充。

Webhook 节点接收到的数据包含：

```text
headers
params
query
body
webhookUrl
executionMode
```

业务请求字段位于 `$json.body`，不能直接使用 `$json.message` 读取。

## 节点配置

### Receive Customer Request

节点类型：

```text
Webhook
```

配置：

| 参数 | 值 |
|---|---|
| HTTP Method | `POST` |
| Path | `w6d37-customer-request` |
| Authentication | `None` |
| Respond | `Using 'Respond to Webhook' Node` |

`Authentication=None` 仅用于绑定在 `127.0.0.1` 的本地学习环境。

如果以后将 n8n 暴露到局域网或公网，必须增加认证和网络保护。

### Normalize Request

节点类型：

```text
Edit Fields (Set)
```

配置：

```text
Mode = Manual Mapping
Include Other Input Fields = Off
```

关闭 `Include Other Input Fields`，可以防止原始 Header、Cookie 和其他请求数据被直接返回。

规范化字段如下：

| 字段 | 类型 | 值 |
|---|---|---|
| `accepted` | Boolean | `true` |
| `day` | Number | `37` |
| `request_id` | String | `{{ $json.body.request_id }}` |
| `customer_id` | String | `{{ $json.body.customer_id }}` |
| `message` | String | `{{ $json.body.message }}` |
| `priority` | String | `{{ $json.body.priority \|\| 'normal' }}` |
| `channel` | String | `{{ $json.query.channel \|\| 'unknown' }}` |
| `source` | String | `{{ $json.headers['x-client-name'] \|\| 'unknown' }}` |
| `next_step` | String | `llm_processing_pending` |
| `execution_mode` | String | `{{ $execution.mode }}` |
| `received_at` | String | `{{ $now.toISO() }}` |

字段名称必须保持 Fixed 模式。

只有需要动态求值的字段值使用 Expression 模式。

`$execution.mode` 在测试执行中返回 `test`，在发布后的生产执行中返回 `production`。

### Return JSON Response

节点类型：

```text
Respond to Webhook
```

配置：

| 参数 | 值 |
|---|---|
| Respond With | `First Incoming Item` |
| Response Code | `200` |

该节点返回 `Normalize Request` 生成的第一个 item。

JSON 响应不需要手动添加 `Content-Type`，n8n 会自动返回 JSON 类型。

## Test URL 验收

为了执行完整工作流，应在画布上点击：

```text
Execute workflow
```

然后在测试 Webhook 等待期间发送请求。

测试命令：

```powershell
$headers = @{
    "X-Client-Name" = "powershell"
}

$payload = @{
    request_id  = "req-day37-001"
    customer_id = "customer-001"
    message     = "How can I reset my password?"
    priority    = "high"
} | ConvertTo-Json

$payloadBytes = [System.Text.Encoding]::UTF8.GetBytes(
    $payload
)

$response = Invoke-WebRequest `
    -UseBasicParsing `
    -Uri "http://127.0.0.1:5678/webhook-test/w6d37-customer-request?channel=learning" `
    -Method Post `
    -Headers $headers `
    -ContentType "application/json; charset=utf-8" `
    -Body $payloadBytes

$response.StatusCode
$response.Content
```

验收结果：

```text
HTTP Status = 200
request_id = req-day37-001
customer_id = customer-001
priority = high
channel = learning
source = powershell
execution_mode = test
```

三个节点均成功执行，每条连接传递一个 item。

## 默认值验收

Test URL 只在等待测试事件时注册。开始第二次测试前，需要再次点击 `Execute workflow` 或 `Listen for test event`。

第二次测试不发送以下内容：

```text
priority
channel
X-Client-Name
```

请求体：

```json
{
  "request_id": "req-day37-002",
  "customer_id": "customer-002",
  "message": "Verify default values"
}
```

验收结果：

```json
{
  "priority": "normal",
  "channel": "unknown",
  "source": "unknown",
  "execution_mode": "test"
}
```

该测试证明默认值表达式可以正确处理缺少的可选字段。

## Production URL 验收

发布工作流后，不需要点击 `Execute workflow`，Production URL 会自动接收请求。

生产请求使用与验收结果一致的 Query、Header 和请求体：

```powershell
$headers = @{
    "X-Client-Name" = "powershell-production"
}

$payload = @{
    request_id  = "req-day37-prod-001"
    customer_id = "customer-prod-001"
    message     = "Verify production webhook"
} | ConvertTo-Json

$payloadBytes = [System.Text.Encoding]::UTF8.GetBytes(
    $payload
)

$response = Invoke-WebRequest `
    -UseBasicParsing `
    -Uri "http://127.0.0.1:5678/webhook/w6d37-customer-request?channel=production-check" `
    -Method Post `
    -Headers $headers `
    -ContentType "application/json; charset=utf-8" `
    -Body $payloadBytes

$response.StatusCode
$response.Content
```

验收结果：

```text
HTTP Status = 200
request_id = req-day37-prod-001
channel = production-check
source = powershell-production
execution_mode = production
```

本次生产执行记录：

```text
Execution ID = 7
Status = Succeeded
Duration = 21 ms
```

Production 执行应在工作流的 `Executions` 页面查看，不依赖编辑器画布实时显示。

## Test URL 与 Production URL

| 对比项 | Test URL | Production URL |
|---|---|---|
| URL 前缀 | `/webhook-test/` | `/webhook/` |
| 是否需要监听 | 是 | 否 |
| 是否需要发布 | 否 | 是 |
| 执行模式 | `test` | `production` |
| 主要查看位置 | 编辑器画布 | Executions |
| 适用场景 | 开发调试 | 已发布调用 |

测试和生产 URL 不能混用。

## 取消发布验收

完成生产验证后，工作流已取消发布。

再次调用 Production URL 时返回：

```text
HTTP Status = 404
```

错误信息：

```text
The requested webhook "POST w6d37-customer-request" is not registered.
```

这证明取消发布后 Production Webhook 已经注销。

取消发布不会删除工作流或历史执行记录。

## 安全注意事项

### 本地监听

当前 n8n 端口只绑定到：

```text
127.0.0.1:5678
```

因此只能从本机访问。

### Authentication=None 的边界

无认证模式仅适用于本地学习。

如果服务需要对外开放，应至少配置：

- Header Authentication 或 JWT
- HTTPS
- 反向代理
- 请求限流
- IP allowlist
- 输入长度和字段校验
- 敏感字段脱敏
- 失败日志和告警

### 不返回原始请求

`Include Other Input Fields` 保持关闭，避免把以下内容原样返回：

- Cookie
- Authorization Header
- 内部代理 Header
- 客户端网络信息
- 其他未审核输入

### 不提交真实密钥

工作流模板不得包含：

- API Key
- Access Token
- 密码
- Secret
- Credential 引用
- 客户真实数据

## 导出与版本控制

工作流导出到：

```text
n8n/workflows/w6d37-customer-request-webhook.json
```

进入 Git 前执行了以下清理：

- 删除顶层 `id`
- 删除顶层 `versionId`
- 删除 `meta.instanceId`
- 删除顶层空 `meta`
- 删除 Webhook 节点的 `webhookId`
- 保留所有节点 `id`
- 保留 Edit Fields assignment `id`
- 保持 `active: false`
- 保持 `pinData` 为空
- 确认不存在 credentials
- 使用 UTF-8 无 BOM 编码

删除顶层实例级标识可以降低跨实例导入时的 ID 冲突风险。

`webhookId` 不是密钥。本项目将其作为工作流模板清理策略删除，让目标实例在导入时重新生成标识；固定的 Webhook `Path` 仍需在导入后重新验收。

节点 ID 用于维护画布与连接关系，因此需要保留。

同一个 n8n 实例中，同一 HTTP Method 和 Path 只能同时发布一个工作流。

## Day 37 验收结果

| 验收项 | 结果 |
|---|---|
| n8n 服务健康 | 通过 |
| 三节点工作流 | 通过 |
| Test URL 显式字段测试 | 通过 |
| Test URL 默认值测试 | 通过 |
| HTTP 200 JSON 响应 | 通过 |
| Production URL | 通过 |
| Production execution 记录 | 通过 |
| 取消发布后返回 404 | 通过 |
| 工作流保持 inactive | 通过 |
| 节点数量为 3 | 通过 |
| 连接数量为 2 | 通过 |
| 规范化字段数量为 11 | 通过 |
| 顶层实例 ID 清理 | 通过 |
| Webhook ID 清理 | 通过 |
| 无 Credential 引用 | 通过 |
| UTF-8 无 BOM | 通过 |

## Day 37 总结

Day 37 完成了从外部 HTTP 请求到 n8n 工作流响应的最小闭环：

```text
HTTP POST
    ↓
Webhook Trigger
    ↓
请求字段规范化
    ↓
JSON Response
```

该工作流已经具备清晰的输入契约、默认值处理、测试与生产生命周期，以及安全的版本化导出方式。

`next_step` 当前返回：

```text
llm_processing_pending
```

Day 38 将在 `Normalize Request` 与 `Return JSON Response` 之间接入 LLM 节点，实现真正的 AI 请求处理。

## 参考资料

- [n8n Webhook node](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.webhook/)
- [Webhook workflow development](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.webhook/workflow-development/)
- [Respond to Webhook node](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.respondtowebhook/)
- [n8n built-in metadata](https://docs.n8n.io/build/code-in-n8n/use-built-in-shortcuts/n8n-metadata/)
