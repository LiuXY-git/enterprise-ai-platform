# 飞书开放平台接入基础

## 学习目标

掌握飞书 Bot、Webhook 和服务端 API 的职责边界，完成企业自建应用、机器人能力、最小权限、测试范围、应用发布及 `tenant_access_token` 鉴权接入。

## 核心概念

### Bot

Bot 是企业自建应用在飞书会话中的机器人身份。本项目已创建 `Enterprise AI Platform Dev`，启用机器人能力，并发布测试版本 `0.1.0` 给指定测试成员。

当前机器人不接收用户消息，因为尚未配置事件订阅和消息回调。Day 43 完成平台基础与服务端鉴权，Day 44 已完成主动文本发送和测试群真实联调。

### Webhook

Webhook 用于飞书向本项目主动推送事件，例如用户向机器人发送消息、机器人被加入群聊或消息状态发生变化。完整接收链路通常需要：

1. 提供公网 HTTPS 回调地址。
2. 在飞书开放平台配置事件订阅。
3. 完成回调地址校验和请求来源验证。
4. 对重复事件进行幂等处理。

Day 43 不启用事件订阅，避免把入站消息处理混入基础鉴权范围。

### API

服务端 API 用于本项目主动调用飞书能力。当前接入的鉴权接口为：

```text
POST /open-apis/auth/v3/tenant_access_token/internal
```

请求使用 App ID 和 App Secret，成功后返回 `tenant_access_token` 及有效期 `expire`。后续调用消息 API 时，使用以下请求头：

```text
Authorization: Bearer <tenant_access_token>
```

## 应用配置

飞书开放平台侧已完成：

- 创建企业自建应用 `Enterprise AI Platform Dev`。
- 启用机器人能力。
- 配置发送单聊、群聊消息所需的最小权限。
- 创建测试企业和测试成员。
- 发布应用测试版本 `0.1.0`。
- 将可用范围限制到测试成员。

不添加与当前功能无关的通讯录管理、审批和群管理权限。

## 本地配置

项目通过以下环境变量读取配置：

```text
FEISHU_APP_ID
FEISHU_APP_SECRET
FEISHU_API_BASE_URL
FEISHU_TIMEOUT_SECONDS
```

真实凭证只保存在本地 `.env` 中，不得提交到 Git；`.env.example` 仅保留空白示例值。

## 鉴权调用链

```text
业务代码
  -> 读取 FeishuConfig
  -> 请求 tenant_access_token
  -> 检查 HTTP 状态
  -> 检查飞书业务错误码
  -> 校验 token 和有效期
  -> 返回 FeishuTenantToken
```

实现文件：

- `backend/app/services/feishu_config.py`：读取并校验环境变量。
- `backend/app/services/feishu_service.py`：异步请求并解析租户访问凭证。
- `tests/test_feishu_config.py`：配置成功和缺失、非法值测试。
- `tests/test_feishu_service.py`：成功、业务错误、HTTP 错误、无效 JSON、字段缺失和连接失败测试。

## 安全约束

- 日志和错误消息不得打印 App Secret。
- 日志和错误消息不得打印完整 access token。
- 服务端错误不得直接透传飞书的敏感响应内容。
- `.env` 必须被 `.gitignore` 忽略。
- 容器配置只引用环境变量，不写入真实凭证。

## Day 43 验收

- [x] 创建并发布飞书企业自建应用。
- [x] 启用机器人能力并限制测试范围。
- [x] 理解 Bot、Webhook 和 API 的职责。
- [x] 实现飞书配置读取与校验。
- [x] 实现 `tenant_access_token` 获取。
- [x] 覆盖成功与异常路径测试。
- [x] 将飞书环境变量传入 API 容器。
- [x] 确认真实凭证不进入版本控制。

## Day 44 验收

- [x] 使用服务端配置的 `open_id` 或 `chat_id` 指定接收者。
- [x] 调用 `/im/v1/messages` 发送文本消息。
- [x] 增加请求模型、幂等键、确定性 UUID、受限重试和安全错误信息。
- [x] 提供 `POST /integrations/feishu/messages` 和 OpenAPI 契约。
- [x] 完成自动化回归和测试群真实消息验收。
