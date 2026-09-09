# 企业微信自建应用通知

## 学习目标

Day 45 学习企业微信服务端 API，并在 Enterprise AI Platform 中实现面向一个内部测试成员的自建应用文本通知。当前完成配置、请求契约、Token 缓存、发送服务、FastAPI 路由、Docker 与 Mock 测试；真实发送受企业微信后台域名准入条件限制，保留为待联调项。

## 当前验收状态

已完成：

- 读取并校验 CorpID、AgentID、应用 Secret 和测试成员 UserID。
- 只允许一个服务端配置的成员作为接收者，拒绝 `@all`、部门和标签群发。
- 获取并缓存 `access_token`，在到期前刷新并避免并发重复获取。
- 调用企业微信自建应用消息接口发送文本。
- 明确 Token 失效时最多重新获取并补发一次。
- 区分确定失败与 `delivery_unknown`，结果不确定时不自动重发。
- FastAPI、OpenAPI、Docker、Mock 测试和全量回归通过。

待完成：

- 真实企业微信消息送达验收。

当前企业微信管理后台要求先配置可信域名或接收消息服务器 URL，两个入口均要求满足域名主体及归属验证条件。当前没有符合要求的可管理域名，因此没有绕过平台限制，也没有把 Mock 成功记录成真实发送成功。

## 调用链

```text
调用方
  -> POST /integrations/wecom/messages
  -> 请求模型校验正文和 request_id
  -> 按需读取 WeComConfig
  -> 复用 WeComMessageService
  -> 复用或刷新 access_token
  -> POST /cgi-bin/message/send
  -> 校验 HTTP 状态、业务错误码和无效接收者字段
  -> 返回 sent 或安全的 503 错误
```

## 环境变量

```dotenv
WECOM_CORP_ID=
WECOM_AGENT_ID=
WECOM_APP_SECRET=
WECOM_TO_USER=
WECOM_API_BASE_URL=https://qyapi.weixin.qq.com
WECOM_TIMEOUT_SECONDS=10
```

四个身份值必须来自同一个企业及其自建应用：

| 变量 | 含义 |
| --- | --- |
| `WECOM_CORP_ID` | 企业 ID |
| `WECOM_AGENT_ID` | 自建应用 AgentID，服务内转换为正整数 |
| `WECOM_APP_SECRET` | 该自建应用的 Secret |
| `WECOM_TO_USER` | 一个内部测试成员的 UserID |

真实值只能放在本地 `.env`。`.env.example` 和 `compose.yaml` 只保存变量名与安全默认值。

## FastAPI 契约

接口：

```text
POST /integrations/wecom/messages
```

请求示例：

```json
{
  "text": "Day 45 企业微信测试消息",
  "request_id": "day45-smoke-001"
}
```

请求约束：

- `text` 去除首尾空白后不能为空，UTF-8 编码最多 2048 字节。
- `request_id` 长度为 1 到 128，只允许字母、数字、点、下划线、冒号和连字符。
- `request_id` 只用于追踪，不提供持久化幂等保证。
- 请求不能传入接收者、AgentID 或 Secret。

成功响应示例：

```json
{
  "status": "sent",
  "message_id": "example-message-id",
  "request_id": "day45-smoke-001",
  "attempts": 1
}
```

如果上游未返回消息 ID，`message_id` 为 `null`。`sent` 表示上游接口确认成功，不代表成员已经阅读。

## Token 缓存

`WeComTokenProvider` 使用进程内缓存和异步锁：

- 缓存仍有效时直接复用。
- 到期前按安全余量刷新。
- 并发请求共享一次 Token 获取。
- 消息接口明确返回 Token 失效时，只清除被拒绝的旧 Token。
- 配置变化时创建新的服务实例，避免新凭据复用旧 Token。
- 应用重启或存在多个进程时，各进程拥有独立缓存。

## 发送与错误语义

| 结果 | API 行为 |
| --- | --- |
| HTTP 200、`errcode=0`，且没有无效接收者 | 返回 `200 sent` |
| 明确的 Token 无效或过期 | 刷新 Token，最多补发一次 |
| 其他业务错误 | 返回 `503`，`detail.code=wecom_unavailable` |
| 网络异常、HTTP 408/5xx、无法确认响应 | 返回 `503`，`detail.code=delivery_unknown` |
| 请求模型不合法 | 返回 `422`，不读取配置、不发网络请求 |

`delivery_unknown` 表示请求可能已经被上游接收。调用方应先核对成员是否实际收到消息，不得直接自动重发。更完整的持久化幂等和重试策略留到 Day 48。

## 安全约束

- 不在日志中输出 CorpID、Secret、完整 Token 或携带敏感查询参数的 URL。
- 不直接透传上游 `errmsg` 或响应正文。
- 不跟随企业微信接口的 HTTP 重定向。
- API 地址固定为 `https://qyapi.weixin.qq.com`，测试使用 `httpx.MockTransport`。
- 真实凭据不进入测试、文档、Git 差异和 Docker Compose 文件。
- 仅允许一个测试成员，不使用 `@all`、部门或标签群发。

## 主要实现文件

- `backend/app/models/wecom.py`：请求和响应模型。
- `backend/app/services/wecom_config.py`：配置读取与校验。
- `backend/app/services/wecom_token_service.py`：Token 获取、缓存和失效处理。
- `backend/app/services/wecom_service.py`：文本发送与错误语义。
- `backend/app/routers/wecom.py`：FastAPI 路由与服务实例复用。
- `tests/test_wecom_*.py`：配置、模型、Token、服务和路由测试。

## 本地验收

```powershell
docker compose config --quiet
docker compose up -d --build --no-deps api
docker compose ps api
Invoke-RestMethod -Uri "http://127.0.0.1:8000/health"
```

OpenAPI 应包含：

```text
/integrations/wecom/messages
```

质量门禁：

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe -m ruff check backend/app tests
git diff --check
```

Day 45 本地验收结果为 `302 passed, 1 warning`。警告来自 ChromaDB 依赖对已弃用 `asyncio.iscoroutinefunction` 的调用，与本次企业微信功能无关。

## 真实联调清单

具备符合企业微信后台要求的域名后，再执行真实联调：

1. 完成可信域名或接收消息服务器 URL 的域名主体及归属验证。
2. 配置运行 API 服务的公网出口可信 IP。
3. 确认测试成员在自建应用可见范围内。
4. 核对 CorpID、AgentID、应用 Secret 和 UserID 属于同一企业及应用。
5. 重建 API 容器，让最新 `.env` 生效。
6. 只发送一条带唯一 `request_id` 的测试消息。
7. 同时核对 API 响应和企业微信客户端实际收件情况。
8. 记录真实业务错误码，不记录 Secret、Token 或完整敏感响应。

在完成以上检查前，本项目只声明“本地实现及 Mock 测试完成”，不声明企业微信真实通知已经送达。
