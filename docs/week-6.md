# Week 6：n8n 自动化与工作流持久化

学习路线：Day 36–42。

按学习路线归档，计划、实施记录与阶段总结集中在本页。记录中的版本、验收结果和“当前”均对应各节写作时点；后续修订会单独注明。

[总目录](README.md#按周阅读) · [上一周](week-5.md) · [下一周](week-7.md)

<a id="contents"></a>

## 本周目录

- [Day 36：n8n 基础与本地部署](#n8n-foundation)
- [Day 37：n8n Webhook 触发与请求响应](#n8n-webhook-trigger)
- [Day 38：n8n 连接 AI 工作流](#n8n-ai-integration)
- [Day 39：n8n AI 邮件助手](#n8n-ai-email-assistant)
- [Day 40：n8n AI 工作流日报](#n8n-daily-workflow-report)
- [Day 41：n8n 工作流数据库持久化](#n8n-workflow-persistence)
- [Workflow Center v0.1.0 发布说明](#workflow-center-v0.1)
- [本周总结（阶段记录）](#summary)

---

<a id="n8n-foundation"></a>

## Day 36：n8n 基础与本地部署

<a id="n8n-foundation-学习目标"></a>

### 学习目标

Day 36 的目标是为 Enterprise AI Platform 建立 n8n 工作流自动化基础，包括：

- 理解 n8n Workflow、Trigger、Node、Item 和 Expression 等核心概念
- 使用 Docker Compose 部署固定版本的 n8n
- 使用环境变量管理运行配置与加密密钥
- 配置健康检查、执行记录清理和持久化存储
- 创建并执行第一个最小工作流
- 将工作流导出为 JSON 并纳入 Git 版本控制
- 验证容器重建后账户和工作流数据仍然存在

本次使用的 n8n 版本为：

```text
2.36.8
```

开发分支为：

```text
feature/n8n-foundation
```

<a id="n8n-foundation-核心概念"></a>

### 核心概念

<a id="n8n-foundation-workflow"></a>

#### Workflow

Workflow 是由一组节点以及节点之间的连接关系构成的自动化流程。

一个工作流通常包括：

1. 触发工作流的 Trigger
2. 读取、转换或生成数据的处理节点
3. 调用外部服务的集成节点
4. 保存、发送或返回结果的输出节点

n8n 工作流可以导出为 JSON 文件，从而进入 Git 版本控制。

<a id="n8n-foundation-trigger"></a>

#### Trigger

Trigger 是工作流的起点，用于决定工作流何时开始执行。

常见 Trigger 包括：

- Manual Trigger：由开发者手动执行
- Webhook Trigger：收到 HTTP 请求时执行
- Schedule Trigger：按照时间计划执行
- 应用 Trigger：收到外部系统事件时执行

Day 36 使用 `Manual Trigger`，因为当前目标是验证基础环境和数据流，不对外提供正式触发入口。

<a id="n8n-foundation-node"></a>

#### Node

Node 是工作流中的单个处理单元。

节点可以执行以下任务：

- 创建或修改字段
- 调用 HTTP API
- 执行条件判断
- 处理数组或文本
- 调用数据库
- 发送消息
- 调用 AI 模型

本次工作流使用：

- `Manual Trigger`
- `Edit Fields (Set)`

<a id="n8n-foundation-item"></a>

#### Item

Item 是 n8n 节点之间传递数据的基本单位。

一个节点可以接收或输出一个或多个 Item。每个 Item 通常包含一个 JSON 对象。

本次工作流最终输出一个 Item，其中包含六个字段。

<a id="n8n-foundation-expression"></a>

#### Expression

Expression 用于在节点参数中动态计算值。

n8n 表达式使用双大括号，例如：

```text
{{ $now.toISO() }}
```

本次使用该表达式动态生成工作流执行时间。

成功执行后，表达式会被计算为类似以下值：

```text
2026-08-31T16:39:24.741+08:00
```

这说明 n8n 已按照 `Asia/Shanghai` 时区生成时间。

<a id="n8n-foundation-手动执行与发布"></a>

#### 手动执行与发布

编辑器中的 `Execute workflow` 用于开发和测试阶段的手动执行。

当前工作流只用于基础验证，因此保持未发布状态。导出的工作流 JSON 中：

```json
"active": false
```

后续创建 Webhook、Schedule 或其他生产触发工作流时，再根据实际需要发布或启用。

<a id="n8n-foundation-本地部署架构"></a>

### 本地部署架构

当前本地架构如下：

```text
浏览器
  │
  │ http://localhost:5678
  ▼
Docker 主机端口 5678
  │
  ▼
n8n 容器
  ├── /home/node/.n8n
  │       │
  │       ▼
  │   n8n_data 命名卷
  │
  └── http://api:8000
          │
          ▼
      FastAPI 容器
```

宿主机访问服务时使用：

```text
http://localhost:5678
http://localhost:8000
```

n8n 容器访问 FastAPI 容器时使用：

```text
http://api:8000
```

在 Docker Compose 网络中，容器不能使用 `localhost:8000` 访问另一个容器，因为容器内的 `localhost` 指向容器自身。应使用 Compose 服务名 `api`。

<a id="n8n-foundation-项目资产"></a>

### 项目资产

Day 36 新增或修改的主要文件如下：

```text
enterprise-ai-platform/
├── .env
├── .env.example
├── compose.yaml
├── docs/
│   ├── README.md
│   └── week-6.md
└── n8n/
    └── workflows/
        └── w6d36-foundation-check.json
```

各文件用途：

- `.env`：保存本地真实配置和加密密钥，不提交到 Git
- `.env.example`：保存不含真实密钥的配置模板
- `compose.yaml`：定义 FastAPI 和 n8n 服务
- [Week 6 的 Day 36 章节](#n8n-foundation)：记录学习与验收结果
- `n8n/workflows/w6d36-foundation-check.json`：版本化保存的工作流

<a id="n8n-foundation-环境变量说明"></a>

### 环境变量说明

n8n 使用以下环境变量：

| 环境变量 | 当前用途 |
|---|---|
| `N8N_ENCRYPTION_KEY` | 加密 n8n 保存的凭据和敏感配置 |
| `N8N_HOST` | 设置 n8n 主机名 |
| `N8N_PORT` | 设置 n8n 服务端口 |
| `N8N_PROTOCOL` | 设置 HTTP 或 HTTPS 协议 |
| `N8N_EDITOR_BASE_URL` | 设置编辑器对外访问地址 |
| `N8N_WEBHOOK_URL` | 设置 Webhook 基础地址 |
| `N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS` | 强制检查配置文件权限 |
| `GENERIC_TIMEZONE` | 设置工作流默认时区 |
| `TZ` | 设置容器系统时区 |
| `EXECUTIONS_DATA_PRUNE` | 启用历史执行记录清理 |
| `EXECUTIONS_DATA_MAX_AGE` | 设置执行记录最长保留时间 |

当前本地环境使用：

```text
N8N_HOST=localhost
N8N_PORT=5678
N8N_PROTOCOL=http
N8N_EDITOR_BASE_URL=http://localhost:5678/
N8N_WEBHOOK_URL=http://localhost:5678/
GENERIC_TIMEZONE=Asia/Shanghai
TZ=Asia/Shanghai
EXECUTIONS_DATA_PRUNE=true
EXECUTIONS_DATA_MAX_AGE=168
```

`168` 表示执行记录最多保留 168 小时，即 7 天。

`N8N_ENCRYPTION_KEY` 的真实值只保存在 `.env` 中。`.env.example` 中必须保持为空：

```text
N8N_ENCRYPTION_KEY=
```

<a id="n8n-foundation-docker-compose-配置"></a>

### Docker Compose 配置

n8n 使用固定版本镜像：

```text
docker.n8n.io/n8nio/n8n:2.36.8
```

固定镜像版本可以避免 `latest` 标签发生变化后引起不可预期的升级。

容器名称为：

```text
enterprise-ai-platform-n8n
```

端口映射为：

```text
127.0.0.1:5678:5678
```

持久化卷映射为：

```text
n8n_data:/home/node/.n8n
```

该目录保存：

- Owner 账户
- 工作流
- 执行记录
- 凭据的加密数据
- n8n 本地数据库
- 实例配置

Compose 还配置了：

```text
init: true
restart: unless-stopped
stop_grace_period: 30s
```

这些配置分别用于：

- 正确处理容器子进程
- Docker 重启后自动恢复服务
- 停止时给 n8n 足够时间完成清理工作

<a id="n8n-foundation-启动与状态检查"></a>

### 启动与状态检查

启动全部服务：

```powershell
docker compose up -d
```

只启动 n8n：

```powershell
docker compose up -d n8n
```

查看 n8n 状态：

```powershell
docker compose ps n8n
```

正常状态应包含：

```text
Up ... (healthy)
```

检查 n8n 版本：

```powershell
docker compose exec -T n8n n8n --version
```

预期输出：

```text
2.36.8
```

查看日志：

```powershell
docker compose logs --tail 80 n8n
```

首次启动时会执行数据库迁移。出现 `Starting migration` 和 `Finished migration` 属于正常现象。

<a id="n8n-foundation-健康检查"></a>

### 健康检查

Compose 使用以下容器内检查地址：

```text
http://127.0.0.1:5678/healthz/readiness
```

其中：

- `/healthz` 用于确认 n8n 进程是否存活
- `/healthz/readiness` 用于确认 n8n 是否已经完成启动并可以接收请求

在 PowerShell 中可以执行：

```powershell
(Invoke-WebRequest `
    -Uri http://127.0.0.1:5678/healthz `
    -UseBasicParsing).StatusCode

(Invoke-WebRequest `
    -Uri http://127.0.0.1:5678/healthz/readiness `
    -UseBasicParsing).StatusCode
```

两个请求的预期结果均为：

```text
200
```

readiness 的响应内容为：

```json
{
  "status": "ok"
}
```

FastAPI 健康检查：

```powershell
Invoke-RestMethod `
    -Uri http://127.0.0.1:8000/health `
    -Method Get
```

预期返回：

```json
{
  "status": "ok"
}
```

<a id="n8n-foundation-w6d36-foundation-check-工作流"></a>

### W6D36 Foundation Check 工作流

工作流名称：

```text
W6D36 - n8n Foundation Check
```

工作流包含两个节点：

```text
Start Manually
       │
       ▼
Build Foundation Result
```

<a id="n8n-foundation-start-manually"></a>

#### Start Manually

节点类型：

```text
Manual Trigger
```

作用是由开发者在编辑器中手动启动工作流。

Manual Trigger 本身不提供业务字段，因此输入面板显示没有字段属于正常现象。

<a id="n8n-foundation-build-foundation-result"></a>

#### Build Foundation Result

节点类型：

```text
Edit Fields (Set)
```

配置模式：

```text
Manual Mapping
```

该节点创建以下六个字段：

| 字段 | 类型 | 值 |
|---|---|---|
| `day` | Number | `36` |
| `component` | String | `n8n` |
| `status` | String | `ready` |
| `api_internal_url` | String | `http://api:8000` |
| `timezone` | String | `Asia/Shanghai` |
| `checked_at` | String/Expression | `{{ $now.toISO() }}` |

执行结果类似：

```json
[
  {
    "day": 36,
    "component": "n8n",
    "status": "ready",
    "api_internal_url": "http://api:8000",
    "timezone": "Asia/Shanghai",
    "checked_at": "2026-08-31T16:39:24.741+08:00"
  }
]
```

其中 `checked_at` 每次执行都会生成新的时间。

<a id="n8n-foundation-工作流导出与版本控制"></a>

### 工作流导出与版本控制

在 n8n 编辑器中：

1. 保存工作流
2. 点击工作流标题旁的三点菜单
3. 选择 `Download`
4. 将导出的 JSON 复制到仓库

仓库内保存路径：

```text
n8n/workflows/w6d36-foundation-check.json
```

验证 JSON 格式：

```powershell
Get-Content `
    .\n8n\workflows\w6d36-foundation-check.json `
    -Raw |
    ConvertFrom-Json |
    Out-Null

if ($?) {
    "WORKFLOW_JSON_OK"
}
```

预期输出：

```text
WORKFLOW_JSON_OK
```

导出文件的验收结果：

- 工作流名称正确
- 工作流保持未启用状态
- 包含两个节点
- 包含一条正确连接
- `Edit Fields` 包含六个字段
- `checked_at` 保持为动态表达式
- 没有凭据引用
- 没有 API Key、Token、密码或其他真实密钥

n8n UI 导出会包含顶层 `id`、`versionId` 和
`meta.instanceId`。这些字段不是密钥，但与来源实例相关。
为了降低跨实例导入时的 ID 冲突风险，进入 Git 的模板已删除
这些顶层字段。节点内部的 `id` 用于区分节点，应继续保留。

<a id="n8n-foundation-持久化验收"></a>

### 持久化验收

为了验证 `n8n_data` 命名卷，执行以下操作：

```powershell
docker compose stop n8n
docker compose rm -f n8n
docker compose up -d n8n
docker compose ps n8n
```

该过程会：

1. 停止原 n8n 容器
2. 删除原容器
3. 根据 Compose 配置创建新容器
4. 将原有 `n8n_data` 卷挂载到新容器

重建后验证结果：

- 新容器状态为 `healthy`
- readiness 返回 `200`
- Owner 账户仍然存在
- 无需导入 JSON，工作流自动存在
- 两个节点仍然存在
- 六个字段配置没有丢失
- 工作流可以再次成功执行
- 新执行时间为 `2026-08-31T16:39:24.741+08:00`

这说明账户、工作流和实例数据已经正确保存到命名卷，而不是只保存在原容器的临时文件系统中。

<a id="n8n-foundation-安全注意事项"></a>

### 安全注意事项

<a id="n8n-foundation-不提交-env"></a>

#### 不提交 `.env`

真实的 `N8N_ENCRYPTION_KEY` 只允许保存在 `.env`。

提交前检查：

```powershell
git check-ignore -v .env
git ls-files .env
```

预期：

- `git check-ignore` 显示 `.env` 被 `.gitignore` 忽略
- `git ls-files .env` 没有任何输出

<a id="n8n-foundation-不公开真实密钥"></a>

#### 不公开真实密钥

以下信息不得进入：

- Git 仓库
- Markdown 文档
- 工作流 JSON
- 截图
- Issue 或聊天消息

敏感信息包括：

- `N8N_ENCRYPTION_KEY`
- API Key
- Access Token
- Owner 密码
- 第三方服务凭据

<a id="n8n-foundation-检查工作流凭据引用"></a>

#### 检查工作流凭据引用

导出包含凭据节点的工作流时，即使没有导出真实密钥，也可能包含凭据名称或内部 ID。

因此，每次提交工作流 JSON 前都应检查：

- 是否存在 `credentials`
- 是否存在真实 Token 或 API Key
- 是否包含测试数据中的个人信息
- 是否包含不应公开的内部地址

当前 Day 36 工作流没有使用任何凭据。

<a id="n8n-foundation-谨慎删除数据卷"></a>

#### 谨慎删除数据卷

以下命令不会删除命名卷：

```powershell
docker compose down
```

以下命令会删除 Compose 管理的命名卷：

```powershell
docker compose down -v
```

除非明确准备清空 n8n 的账户、工作流和本地数据，否则不要使用 `-v`。

<a id="n8n-foundation-常见问题"></a>

### 常见问题

<a id="n8n-foundation-容器显示-health-starting"></a>

#### 容器显示 `health: starting`

n8n 刚启动时需要初始化数据库和服务。

等待约 20 秒后重新检查：

```powershell
docker compose ps n8n
```

如果长时间没有变为 `healthy`，查看日志：

```powershell
docker compose logs --tail 100 n8n
```

<a id="n8n-foundation-powershell-无法调用静态-getbytes"></a>

#### PowerShell 无法调用静态 GetBytes

部分 Windows PowerShell 5.1 环境不支持：

```powershell
[System.Security.Cryptography.RandomNumberGenerator]::GetBytes(32)
```

可以创建随机数生成器实例：

```powershell
$bytes = New-Object byte[] 32
$rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
$rng.GetBytes($bytes)
$key = ([System.BitConverter]::ToString($bytes)).Replace("-", "").ToLowerInvariant()
$rng.Dispose()

$key
$key.Length
```

生成后将密钥写入本地 `.env`，不要把输出提交到 Git 或写入文档。

<a id="n8n-foundation-n8n-容器无法访问-fastapi"></a>

#### n8n 容器无法访问 FastAPI

在 n8n 容器内部，不应使用：

```text
http://localhost:8000
```

应使用 Compose 服务名：

```text
http://api:8000
```

因为两个容器通过 Docker Compose 默认网络进行通信。

<a id="n8n-foundation-工作流重建后丢失"></a>

#### 工作流重建后丢失

依次检查：

```powershell
docker compose config --volumes
docker volume ls
docker compose logs --tail 100 n8n
```

确认 Compose 中存在：

```text
n8n_data:/home/node/.n8n
```

同时确认没有执行过：

```powershell
docker compose down -v
```

<a id="n8n-foundation-day-36-验收结果"></a>

### Day 36 验收结果

| 验收项 | 结果 |
|---|---|
| Git 分支为 `feature/n8n-foundation` | 通过 |
| Docker Engine 可用 | 通过 |
| Docker Compose 可用 | 通过 |
| n8n 镜像固定为 `2.36.8` | 通过 |
| n8n 容器状态为 `healthy` | 通过 |
| `/healthz` 返回 `200` | 通过 |
| `/healthz/readiness` 返回 `200` | 通过 |
| FastAPI `/health` 返回正常 | 通过 |
| Owner 初始化完成 | 通过 |
| 最小工作流创建完成 | 通过 |
| 六个字段输出正确 | 通过 |
| 动态时间表达式正确 | 通过 |
| 工作流 JSON 导出成功 | 通过 |
| 导出文件无凭据引用 | 通过 |
| 容器删除重建后账户仍存在 | 通过 |
| 容器删除重建后工作流仍存在 | 通过 |
| 工作流重建后再次执行成功 | 通过 |

<a id="n8n-foundation-day-36-总结"></a>

### Day 36 总结

Day 36 完成了 n8n 自动化平台的基础建设。

当前项目已经具备：

- 可重复启动的 n8n Docker Compose 服务
- 固定版本的 n8n 镜像
- 健康检查与自动重启
- 时区和执行记录清理配置
- 安全的本地加密密钥管理
- 命名卷持久化
- 第一个可执行的 n8n 工作流
- 可进入 Git 版本控制的工作流 JSON
- 容器级持久化验收记录

Day 36 建立的是 n8n 基础设施和工作流开发规范。后续可以在此基础上继续学习 HTTP Request、Webhook、条件分支、错误处理以及 FastAPI 集成。
下一步进入 [Day 37：n8n Webhook 触发与请求响应](#n8n-webhook-trigger)，完成外部请求触发、字段标准化和显式 JSON 响应闭环。

<a id="n8n-foundation-参考资料"></a>

### 参考资料

- [n8n 官方文档](https://docs.n8n.io/)
- [n8n Docker 安装](https://docs.n8n.io/hosting/installation/docker/)
- [n8n 工作流导入与导出](https://docs.n8n.io/build/manage-workflows/export-and-import)
- [n8n 环境变量：Endpoints](https://docs.n8n.io/hosting/configuration/environment-variables/endpoints/)
- [n8n GitHub Releases](https://github.com/n8n-io/n8n/releases)

---

<a id="n8n-webhook-trigger"></a>

## Day 37：n8n Webhook 触发与请求响应

<a id="n8n-webhook-trigger-学习目标"></a>

### 学习目标

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

<a id="n8n-webhook-trigger-完成结果"></a>

### 完成结果

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

<a id="n8n-webhook-trigger-工作流架构"></a>

### 工作流架构

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

<a id="n8n-webhook-trigger-webhook-请求契约"></a>

### Webhook 请求契约

<a id="n8n-webhook-trigger-http-方法与路径"></a>

#### HTTP 方法与路径

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

<a id="n8n-webhook-trigger-请求-header"></a>

#### 请求 Header

可选请求头：

```text
X-Client-Name
```

该值用于标识请求来源。

未提供时，工作流返回：

```text
source = unknown
```

<a id="n8n-webhook-trigger-query-参数"></a>

#### Query 参数

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

<a id="n8n-webhook-trigger-json-body"></a>

#### JSON Body

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

<a id="n8n-webhook-trigger-节点配置"></a>

### 节点配置

<a id="n8n-webhook-trigger-receive-customer-request"></a>

#### Receive Customer Request

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

<a id="n8n-webhook-trigger-normalize-request"></a>

#### Normalize Request

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

<a id="n8n-webhook-trigger-return-json-response"></a>

#### Return JSON Response

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

<a id="n8n-webhook-trigger-test-url-验收"></a>

### Test URL 验收

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

<a id="n8n-webhook-trigger-默认值验收"></a>

### 默认值验收

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

<a id="n8n-webhook-trigger-production-url-验收"></a>

### Production URL 验收

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

<a id="n8n-webhook-trigger-test-url-与-production-url"></a>

### Test URL 与 Production URL

| 对比项 | Test URL | Production URL |
|---|---|---|
| URL 前缀 | `/webhook-test/` | `/webhook/` |
| 是否需要监听 | 是 | 否 |
| 是否需要发布 | 否 | 是 |
| 执行模式 | `test` | `production` |
| 主要查看位置 | 编辑器画布 | Executions |
| 适用场景 | 开发调试 | 已发布调用 |

测试和生产 URL 不能混用。

<a id="n8n-webhook-trigger-取消发布验收"></a>

### 取消发布验收

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

<a id="n8n-webhook-trigger-安全注意事项"></a>

### 安全注意事项

<a id="n8n-webhook-trigger-本地监听"></a>

#### 本地监听

当前 n8n 端口只绑定到：

```text
127.0.0.1:5678
```

因此只能从本机访问。

<a id="n8n-webhook-trigger-authenticationnone-的边界"></a>

#### Authentication=None 的边界

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

<a id="n8n-webhook-trigger-不返回原始请求"></a>

#### 不返回原始请求

`Include Other Input Fields` 保持关闭，避免把以下内容原样返回：

- Cookie
- Authorization Header
- 内部代理 Header
- 客户端网络信息
- 其他未审核输入

<a id="n8n-webhook-trigger-不提交真实密钥"></a>

#### 不提交真实密钥

工作流模板不得包含：

- API Key
- Access Token
- 密码
- Secret
- Credential 引用
- 客户真实数据

<a id="n8n-webhook-trigger-导出与版本控制"></a>

### 导出与版本控制

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

<a id="n8n-webhook-trigger-day-37-验收结果"></a>

### Day 37 验收结果

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

<a id="n8n-webhook-trigger-day-37-总结"></a>

### Day 37 总结

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

Day 38 已在 `Normalize Request` 与 `Return JSON Response` 之间接入 AI 调用与响应整理节点。详见 [Day 38：n8n 连接 AI 工作流](#n8n-ai-integration)。

<a id="n8n-webhook-trigger-参考资料"></a>

### 参考资料

- [n8n Webhook node](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.webhook/)
- [Webhook workflow development](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.webhook/workflow-development/)
- [Respond to Webhook node](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.respondtowebhook/)
- [n8n built-in metadata](https://docs.n8n.io/build/code-in-n8n/use-built-in-shortcuts/n8n-metadata/)

---

<a id="n8n-ai-integration"></a>

## Day 38：n8n 连接 AI 工作流

<a id="n8n-ai-integration-学习目标"></a>

### 学习目标

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

<a id="n8n-ai-integration-架构"></a>

### 架构

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

<a id="n8n-ai-integration-集成边界"></a>

### 集成边界

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

<a id="n8n-ai-integration-webhook-输入契约"></a>

### Webhook 输入契约

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

<a id="n8n-ai-integration-工作流节点"></a>

### 工作流节点

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

<a id="n8n-ai-integration-receive-customer-request"></a>

#### Receive Customer Request

| 参数 | 值 |
|---|---|
| HTTP Method | `POST` |
| Path | `w6d38-ai-customer-request` |
| Authentication | `None` |
| Respond | `Using 'Respond to Webhook' Node` |

该无认证 Webhook 只用于绑定在 `127.0.0.1` 的本地学习环境。验收完成后保持未发布状态。

<a id="n8n-ai-integration-normalize-request"></a>

#### Normalize Request

该节点复用 Day 37 的请求字段映射，并将：

```text
day = 38
next_step = ai_processing
```

`Include Other Input Fields` 保持关闭，避免把原始 Header、Cookie 或其他无关字段继续传递。

<a id="n8n-ai-integration-call-ai-workflow"></a>

#### Call AI Workflow

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

<a id="n8n-ai-integration-build-ai-response"></a>

#### Build AI Response

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

<a id="n8n-ai-integration-return-json-response"></a>

#### Return JSON Response

该节点返回 `Build AI Response` 生成的第一个 item，并使用 HTTP 状态码 `200`。

<a id="n8n-ai-integration-test-url-验收"></a>

### Test URL 验收

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

<a id="n8n-ai-integration-production-url-验收"></a>

### Production URL 验收

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

<a id="n8n-ai-integration-取消发布验收"></a>

### 取消发布验收

完成 Production 测试后取消发布工作流，再次调用 Production URL 返回：

```text
HTTP Status = 404
The requested webhook "POST w6d38-ai-customer-request" is not registered.
```

这证明 Production Webhook 已注销。取消发布不会删除工作流或执行记录。

<a id="n8n-ai-integration-导出与版本控制"></a>

### 导出与版本控制

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

<a id="n8n-ai-integration-当前限制"></a>

### 当前限制

- Webhook 尚未增加调用方认证与限流
- Day 38 使用受控的 `customer_id`，尚未增加格式校验节点
- AI 调用失败时由工作流停止执行，尚未建立面向调用方的错误响应分支
- 当前调用为阻塞模式，请求耗时取决于 Dify 工作流和模型响应时间

这些限制将在后续条件分支、输入校验和错误处理学习中继续完善。

<a id="n8n-ai-integration-day-38-验收结果"></a>

### Day 38 验收结果

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

<a id="n8n-ai-integration-day-38-总结"></a>

### Day 38 总结

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

下一步进入 [Day 39：n8n AI 邮件助手](#n8n-ai-email-assistant)，在 AI 调用之前增加邮件分类与人工复核分支。

<a id="n8n-ai-integration-相关文档"></a>

### 相关文档

- [Day 37：n8n Webhook 触发与请求响应](#n8n-webhook-trigger)
- [Day 39：n8n AI 邮件助手](#n8n-ai-email-assistant)
- [FastAPI 调用 Dify 工作流](week-5.md#dify-fastapi-integration)
- [API 文档](week-4.md#api)
- [n8n 基础与本地部署](#n8n-foundation)

---

<a id="n8n-ai-email-assistant"></a>

## Day 39：n8n AI 邮件助手

<a id="n8n-ai-email-assistant-学习目标"></a>

### 学习目标

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

<a id="n8n-ai-email-assistant-场景边界"></a>

### 场景边界

Day 39 使用 Webhook 模拟邮件事件，不连接 Gmail、Outlook、IMAP 或 SMTP，也不会自动发送邮件。工作流只生成回复草稿或人工复核任务，因此无需把邮箱账号、OAuth Token 或邮件系统 Credential 保存到 n8n 导出文件中。

该边界适合先验证分类、路由和 AI 草稿逻辑。连接真实邮箱和发送动作前，还需要补充调用方认证、权限最小化、审计、幂等和人工批准机制。

<a id="n8n-ai-email-assistant-架构"></a>

### 架构

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

<a id="n8n-ai-email-assistant-webhook-输入契约"></a>

### Webhook 输入契约

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

<a id="n8n-ai-email-assistant-工作流节点"></a>

### 工作流节点

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

<a id="n8n-ai-email-assistant-receive-customer-request"></a>

#### Receive Customer Request

| 参数 | 值 |
|---|---|
| HTTP Method | `POST` |
| Path | `w6d39-ai-email-assistant` |
| Authentication | `None` |
| Respond | `Using 'Respond to Webhook' Node` |

无认证 Webhook 只适用于绑定在 `127.0.0.1` 的本地学习环境。验收后应保持未发布状态。

<a id="n8n-ai-email-assistant-normalize-email-request"></a>

#### Normalize Email Request

该节点输出 14 个受控字段，并关闭 `Include Other Input Fields`，避免把原始 Header、Cookie 或其他无关字段传给分类和 AI 节点。

主题与正文组合为发送给 AI 的 `message`：

```text
subject

body
```

<a id="n8n-ai-email-assistant-classify-email-request"></a>

#### Classify Email Request

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

<a id="n8n-ai-email-assistant-needs-human-review"></a>

#### Needs Human Review?

IF 节点以布尔值 `need_human_review` 路由：

- true 输出连接 `Build Human Review Response`
- false 输出连接 `Call AI Workflow`

<a id="n8n-ai-email-assistant-build-human-review-response"></a>

#### Build Human Review Response

人工分支不调用 AI，并返回：

```text
draft_reply = ""
need_human_review = true
status = needs_human_review 或 invalid_request
next_step = human_review 或 request_correction
```

AI 运行信息使用空字符串或 `0`，使两个分支维持统一响应结构。

<a id="n8n-ai-email-assistant-call-ai-workflow"></a>

#### Call AI Workflow

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

<a id="n8n-ai-email-assistant-build-email-draft-response"></a>

#### Build Email Draft Response

AI 分支把 FastAPI 响应中的回答、运行 ID、耗时、Token 和步骤数与邮件元数据组合为稳定结果：

```text
draft_reply = answer
need_human_review = false
review_reason = ""
next_step = completed
```

<a id="n8n-ai-email-assistant-return-json-response"></a>

#### Return JSON Response

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

<a id="n8n-ai-email-assistant-本地运行态验收"></a>

### 本地运行态验收

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

<a id="n8n-ai-email-assistant-test-url"></a>

#### Test URL

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

<a id="n8n-ai-email-assistant-production-url"></a>

#### Production URL

仅在本地验收窗口内发布工作流：

```text
POST http://127.0.0.1:5678/webhook/w6d39-ai-email-assistant?channel=production-check
```

完成后立即取消发布。再次调用 Production URL 应返回 `404`，证明生产 Webhook 已注销。

本次回归中 Production URL 返回 `404` 和 `not registered`，确认 Day 39 工作流当前保持未发布状态。

<a id="n8n-ai-email-assistant-导出脱敏与版本控制"></a>

### 导出、脱敏与版本控制

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

<a id="n8n-ai-email-assistant-当前限制"></a>

### 当前限制

- Webhook 尚未增加认证、签名校验、限流和重放保护
- 分类规则基于关键词，不能代替合规或客服策略引擎
- `event_id` 尚未落库，当前没有幂等去重
- AI 分支尚未增加超时或下游失败的显式 JSON 错误分支
- 人工复核结果只通过响应返回，尚未进入工单队列
- 工作流只生成草稿，不读取真实邮箱，也不自动发送邮件

<a id="n8n-ai-email-assistant-day-39-验收清单"></a>

### Day 39 验收清单

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

<a id="n8n-ai-email-assistant-day-39-总结"></a>

### Day 39 总结

Day 39 将通用 AI 请求闭环扩展成可审慎处理邮件的业务自动化：低风险邮件进入 AI 草稿生成，高风险或信息不足的邮件进入人工复核。工作流没有连接真实邮箱，也不会自动发送回复，保留了明确的人机协作边界。

<a id="n8n-ai-email-assistant-相关文档"></a>

### 相关文档

- [Day 38：n8n 连接 AI 工作流](#n8n-ai-integration)
- [Day 37：n8n Webhook 触发与请求响应](#n8n-webhook-trigger)
- [FastAPI 调用 Dify 工作流](week-5.md#dify-fastapi-integration)
- [API 文档](week-4.md#api)

---

<a id="n8n-daily-workflow-report"></a>

## Day 40：n8n AI 工作流日报

<a id="n8n-daily-workflow-report-学习目标"></a>

### 学习目标

Day 40 使用 n8n 原生 LLM 节点完成每日工作流报告，目标包括：

- 每天 18:00 按 `Asia/Shanghai` 时区触发日报
- 支持 Webhook 指定日期进行手动回放
- 校验 `YYYY-MM-DD` 格式和真实日历日期
- 汇总执行数、成功率、耗时、Token、分类和失败事件
- 使用 `Basic LLM Chain` 与通义千问生成中文运营日报
- 对无数据日期设置事实边界，避免模型把“无记录”解释为“无风险”
- 将脱敏后的工作流和自动化结构测试纳入 Git

工作流名称：

```text
W6D40 - Daily Workflow Report
```

<a id="n8n-daily-workflow-report-架构"></a>

### 架构

```text
Daily Report Schedule ─┐
                      ├→ Prepare Report Context
Manual Report Replay ─┘          ↓
                       Load Fixed Workflow Runs
                                  ↓
                       Aggregate Daily Metrics
                                  ↓
                    Generate Daily Report Summary
                                  │
                    DashScope Qwen Chat Model
```

工作流包含 7 个节点。调度触发器与手动回放复用同一条统计和总结链路；
模型通过 n8n 原生 AI 子节点连接，不再调用 Day 39 的 FastAPI / Dify
客服工作流。

<a id="n8n-daily-workflow-report-触发方式"></a>

### 触发方式

`Daily Report Schedule` 每天 18:00 触发。n8n 实例时区由 Docker 环境配置为
`Asia/Shanghai`；工作流的日期计算也显式使用该时区。

手动回放使用：

```text
POST /webhook-test/w6d40-daily-workflow-report
```

请求体：

```json
{
  "report_date": "2026-09-01"
}
```

不传 `report_date` 时使用上海时区当天日期。`2026-02-30` 等不存在的日历
日期会在 `Prepare Report Context` 节点被拒绝，后续统计与模型节点不会执行。

<a id="n8n-daily-workflow-report-固定测试数据和指标"></a>

### 固定测试数据和指标

Day 40 使用 9 条脱敏固定记录验证日报链路，不连接生产数据库，也不包含真实
客户数据。`2026-09-01` 的验收基线为：

| 指标 | 期望值 |
|---|---:|
| 总执行数 | 6 |
| 成功数 | 4 |
| 失败数 | 2 |
| 成功率 | 66.67% |
| 平均耗时 | 4 秒 |
| 累计 Token | 3060 |
| 产品 / 技术 / 敏感 / 其他 | 2 / 2 / 1 / 1 |
| 失败事件 | `mail-report-005`、`mail-report-006` |

`Aggregate Daily Metrics` 在记录数为 0 时显式返回零值，避免出现 `NaN` 或
`Infinity`。

<a id="n8n-daily-workflow-report-n8n-原生-llm-配置"></a>

### n8n 原生 LLM 配置

根节点使用 `Basic LLM Chain`，模型子节点使用 `OpenAI Chat Model` 的
OpenAI 兼容接口模式：

| 参数 | 值 |
|---|---|
| Model ID | `qwen3.7-plus` |
| Responses API | 关闭 |
| Sampling Temperature | `0.2` |
| Maximum Number of Tokens | `1000` |

工作流导入后需要在 n8n 中创建 Credential：

```text
API Key  = DASHSCOPE_API_KEY 的值
Base URL = https://dashscope.aliyuncs.com/compatible-mode/v1
```

`Organization ID` 留空，不启用自定义 Header。Credential 应限制为仅访问
`dashscope.aliyuncs.com`（版本支持时），并只在 n8n 中保存；禁止把 API Key
写入节点、工作流 JSON、文档或 Git。

导入仓库版 JSON 后，将该 Credential 重新绑定到
`DashScope Qwen Chat Model` 即可运行。

<a id="n8n-daily-workflow-report-prompt-事实边界"></a>

### Prompt 事实边界

日报 Prompt 要求模型：

- 只使用聚合节点提供的数字
- 输出标题、指标概览、风险分析和优化建议
- 不补造记录、失败原因或指标
- 无数据时将成功率写为“无执行数据，不适用”
- 无数据时只能说明无法评估稳定性，不得声称系统平稳或无风险

这组规则解决了初版无数据报告把“没有执行记录”错误推断为“系统无风险”的
问题。

<a id="n8n-daily-workflow-report-运行态验收"></a>

### 运行态验收

2026-09-02 完成以下本地测试：

| 场景 | 输入 | 结果 |
|---|---|---|
| 正常数据 | `2026-09-01` | 指标与基线一致，生成四部分中文日报 |
| 无数据 | `2026-09-03` | 全部计数为 0，成功率显示不适用，不虚构风险结论 |
| 非法日期 | `2026-02-30` | HTTP 500，日期校验节点终止后续执行 |

正常场景中 n8n 原生 LLM Chain 和 Qwen 模型均执行成功，旧的
FastAPI / Dify HTTP 节点未保留在仓库版工作流中。

<a id="n8n-daily-workflow-report-导出与脱敏"></a>

### 导出与脱敏

版本化文件：

```text
n8n/workflows/w6d40-daily-workflow-report.json
```

入库前已执行：

- 删除顶层 `id`、`versionId` 和 `meta.instanceId`
- 删除 Webhook `webhookId`
- 删除模型节点的 Credential ID 和名称引用
- 修正 Webhook Path 的前导空格
- 修正 Prompt 导出时多出的表达式前缀 `=`
- 保持 `active: false` 和空 `pinData`
- 保留节点 ID 与连线，确保导入后编辑关系完整
- 确认没有明文 API Key、真实客户信息或生产数据

<a id="n8n-daily-workflow-report-当前限制"></a>

### 当前限制

- 本 Day 40 工作流仍保留固定测试记录作为可复现实验基线；Day 41 已在独立持久化工作流中接入数据库并保存输入、输出、时间和用户，详见 [Day 41：n8n 工作流数据库持久化](#n8n-workflow-persistence)
- 调度工作流尚未发布；发布前应确认 n8n 实例时区和 Credential 权限
- Webhook 仅用于本地回放，尚未增加认证、签名、限流和重放保护
- LLM 输出是自然语言，关键指标仍应以聚合节点结果作为事实来源
- 当前没有邮件、IM 或工单投递节点，日报只作为执行结果返回

<a id="n8n-daily-workflow-report-day-40-验收清单"></a>

### Day 40 验收清单

| 验收项 | 结果 |
|---|---|
| 每日调度与手动回放双触发 | 通过 |
| 真实日历日期校验 | 通过 |
| 固定数据筛选与指标聚合 | 通过 |
| 正常、无数据、非法日期测试 | 通过 |
| n8n 原生 LLM Chain + Qwen | 通过 |
| 无数据事实边界 | 通过 |
| 工作流保持未发布 | 通过 |
| 实例 ID、Webhook ID、Credential 引用清理 | 通过 |
| 无明文密钥和真实客户数据 | 通过 |
| 自动化结构测试 | 通过 |

<a id="n8n-daily-workflow-report-相关文档"></a>

### 相关文档

- [Day 39：n8n AI 邮件助手](#n8n-ai-email-assistant)
- [Day 38：n8n 连接 AI 工作流](#n8n-ai-integration)
- [n8n 基础与本地部署](#n8n-foundation)

---

<a id="n8n-workflow-persistence"></a>

## Day 41：n8n 工作流数据库持久化

<a id="n8n-workflow-persistence-学习目标"></a>

### 学习目标

Day 41 将 Day 39 的 AI 邮件助手接入 SQLite，保存工作流输入、输出、时间、
请求者、执行状态和错误信息，并增加重复事件拦截及失败回放能力。

本日完成：

- 新增 `workflow_runs` 表和索引
- 新增工作流登记、完成、失败、查询 API
- 使用 `(workflow_name, event_id)` 保证业务事件幂等
- 使用 n8n `Error Trigger` 自动保存生产执行失败
- 对失败记录提供最多 3 次回放
- 将人工审核、成功、重复、失败和回放场景纳入真实验收

<a id="n8n-workflow-persistence-架构"></a>

### 架构

```text
Webhook
  ↓
Normalize Email Request
  ↓
POST /workflow-runs/start
  ↓
Should Process?
  ├─ false → Build Duplicate Response → Webhook Response
  └─ true  → 分类与 AI / 人工审核
                  ↓
             PATCH /workflow-runs/{run_id}/result
                  ↓
             Webhook Response

生产执行失败
  ↓
Error Trigger
  ↓
PATCH /workflow-runs/executions/{n8n_execution_id}/failure
```

<a id="n8n-workflow-persistence-数据库设计"></a>

### 数据库设计

`workflow_runs` 保存以下核心信息：

| 字段 | 作用 |
|---|---|
| `run_id` | 平台生成的工作流运行 ID |
| `event_id` | 上游业务事件 ID |
| `workflow_name` | 工作流稳定名称 |
| `source` / `requester` | 来源与请求者 |
| `report_date` | 日报归属日期 |
| `status` | `running`、`succeeded`、`failed` 或 `needs_human_review` |
| `input_json` / `output_json` | 完整输入与输出 |
| `n8n_execution_id` | n8n 执行 ID，用于错误回调关联 |
| `retry_count` | 失败回放次数 |
| `duplicate_count` | 重复事件命中次数 |
| `elapsed_time` / `total_tokens` | AI 调用耗时与 Token |
| `error_type` / `error_message` | 最后一次失败信息 |
| `started_at` / `finished_at` | 开始与结束时间 |

唯一约束：

```text
UNIQUE(workflow_name, event_id)
```

同一工作流再次收到相同 `event_id` 时只增加 `duplicate_count`，不会再次调用
分类器或 AI。只有状态为 `failed` 且请求显式携带 `replay: true` 时才允许回放。

<a id="n8n-workflow-persistence-api"></a>

### API

| 方法 | 地址 | 作用 |
|---|---|---|
| `POST` | `/workflow-runs/start` | 登记新运行、拦截重复事件或开始回放 |
| `PATCH` | `/workflow-runs/{run_id}/result` | 保存成功或人工审核结果 |
| `PATCH` | `/workflow-runs/executions/{execution_id}/failure` | 按 n8n 执行号保存失败 |
| `GET` | `/workflow-runs/{run_id}` | 查询单条运行 |
| `GET` | `/workflow-runs?report_date=YYYY-MM-DD` | 查询指定日期运行 |

<a id="n8n-workflow-persistence-n8n-工作流"></a>

### n8n 工作流

版本化文件：

```text
n8n/workflows/w6d41-persistent-ai-email-assistant.json
n8n/workflows/w6d41-workflow-error-handler.json
```

仓库版工作流保持 `active: false`，并删除以下实例专属数据：

- 工作流 ID、版本 ID 和发布状态
- Webhook ID
- Credential 引用
- 项目、用户和实例元数据

导入后必须先发布错误处理工作流，再在主工作流设置中将它选为
`Error Workflow`。错误工作流通过执行号关联运行记录，因此不需要在失败分支
传递输入数据。

<a id="n8n-workflow-persistence-回放语义"></a>

### 回放语义

首次执行失败后，数据库状态为 `failed`。相同事件再次请求时：

- `replay: false`：视为重复事件，不重新处理
- `replay: true`：状态改回 `running`，`retry_count` 加 1
- 回放成功：状态改为 `succeeded`，清空旧错误字段
- 超过 3 次：API 返回冲突，不再执行

回放继续使用首次保存的 `input_json`，避免调用者在重试时悄悄修改原始业务
输入。

<a id="n8n-workflow-persistence-真实验收"></a>

### 真实验收

2026-09-03 完成 Docker 与 n8n 真实运行验收：

| 场景 | 结果 |
|---|---|
| 人工审核 | 保存为 `needs_human_review` |
| 正常 AI 请求 | 保存为 `succeeded`，记录分类、耗时和 Token |
| 重复事件 | 返回 `duplicate`，原任务不重复执行，计数加 1 |
| 自动执行失败 | Error Trigger 保存为 `failed` 和错误详情 |
| 失败回放 | 复用原 `run_id`，成功后 `retry_count = 1` |

验收同时确认：SQLite 中的中文输入和输出保持 UTF-8。Windows PowerShell 5.1
显示 FastAPI JSON 时可能出现乱码，这是客户端响应解码问题，不是数据库损坏。

<a id="n8n-workflow-persistence-当前限制"></a>

### 当前限制

- API 尚未增加认证和租户隔离，只适用于当前本地可信网络
- `source`、`requester` 和事件 ID 目前使用简单格式约束
- 失败回放由调用者显式设置 `replay: true`，尚未配置定时自动重试
- Error Trigger 只处理已绑定工作流的自动执行失败，手动测试执行不会触发

<a id="n8n-workflow-persistence-相关文档"></a>

### 相关文档

- [Day 40：n8n AI 工作流日报](#n8n-daily-workflow-report)
- [Day 39：n8n AI 邮件助手](#n8n-ai-email-assistant)
- [数据库设计](week-2.md#database)

---

<a id="workflow-center-v0.1"></a>

## Workflow Center v0.1.0 发布说明

状态：Day 42 发布候选验收完成，等待 Git 提交与组件标签。

<a id="workflow-center-v0.1-版本定位"></a>

### 版本定位

Workflow Center v0.1.0 是 Enterprise AI Platform v1.0.0 内的工作流自动化
组件版本，不改变平台 API 的 `1.0.0` 版本号。

仓库中已经存在平台早期标签 `v0.1.0`，因此本组件正式标签使用：

```text
workflow-center-v0.1.0
```

这样可以明确区分“平台版本”和“Workflow Center 组件版本”。

<a id="workflow-center-v0.1-发布范围"></a>

### 发布范围

v0.1.0 收录 Day 36 至 Day 41 的 7 个版本化工作流：

| 工作流 | 发布层级 | 用途 |
| --- | --- | --- |
| `W6D36 - n8n Foundation Check` | reference | 验证手动触发和运行环境 |
| `W6D37 - Customer Request Webhook` | reference | 演示 Webhook 请求响应闭环 |
| `W6D38 - AI Customer Request Processing` | reference | 演示 n8n 调用 FastAPI/Dify |
| `W6D39 - AI Email Assistant` | reference | 演示邮件分类和人工审核分支 |
| `W6D40 - Daily Workflow Report` | optional | 生成运营日报，需要单独绑定模型凭据 |
| `W6D41 - Workflow Error Handler` | release | 自动保存生产执行失败 |
| `W6D41 - Persistent AI Email Assistant` | release | v0.1.0 主业务入口 |

机器可读清单位于 `n8n/workflow-center-v0.1.0.json`，它固定组件版本、n8n
版本、API 版本、工作流文件、导入顺序、发布顺序、手动绑定项和质量门禁。

<a id="workflow-center-v0.1-核心能力"></a>

### 核心能力

- Docker Compose 部署固定版本 n8n
- Webhook 测试与生产请求入口
- 调用 FastAPI/Dify 企业 AI 工作流
- 邮件请求规范化、分类、AI 回复和人工审核
- 定时或手动生成运营日报
- SQLite 保存工作流输入、输出、请求者、状态、时间和 Token
- 使用业务事件 ID 拦截重复执行
- 使用 Error Trigger 自动保存失败
- 最多 3 次显式失败回放，并复用首次输入

<a id="workflow-center-v0.1-运行依赖"></a>

### 运行依赖

| 依赖 | 固定值或要求 |
| --- | --- |
| Enterprise AI Platform API | `1.0.0` |
| n8n | `2.36.8` |
| Docker Compose 服务 | `api`、`n8n` |
| 必需环境变量 | `N8N_ENCRYPTION_KEY`、`DIFY_WORKFLOW_API_KEY` |
| 时区 | `Asia/Shanghai` |
| 持久化 | `./data`、`./logs`、`n8n_data` 命名卷 |

真实密钥只允许保存在本地 `.env` 或 n8n Credential 中，不得写入工作流 JSON、
文档、测试或 Git 历史。

<a id="workflow-center-v0.1-启动发布候选"></a>

### 启动发布候选

在项目根目录执行：

```powershell
docker compose up -d --build api n8n
docker compose ps
```

预期 API 和 n8n 容器均为 `healthy`。继续检查版本和双向连通性：

```powershell
docker compose exec n8n n8n --version

Invoke-RestMethod `
    -Uri "http://127.0.0.1:8000/health" `
    -Method Get

docker compose exec n8n `
    wget -qO- http://api:8000/health
```

预期 n8n 版本为 `2.36.8`，两次健康检查均返回 `{"status":"ok"}`。

<a id="workflow-center-v0.1-导入与发布顺序"></a>

### 导入与发布顺序

在 n8n 编辑器中使用 Import from File，按发布清单顺序导入。核心链路必须：

1. 先导入 `W6D41 - Workflow Error Handler`
2. 再导入 `W6D41 - Persistent AI Email Assistant`
3. 打开主工作流 Settings
4. 将 Error Workflow 绑定到 `W6D41 - Workflow Error Handler`
5. 先发布错误处理工作流
6. 再发布主工作流

仓库导出文件保持 `active: false`，并移除了实例 ID、Webhook ID、项目元数据和
Credential 引用。导入后必须在目标实例重新完成绑定与发布，不能假设导入等于
生产启用。

Day 40 日报是可选组件。导入后需要为 `Qwen Chat Model` 重新选择
OpenAI-compatible 通义千问 Credential，并确认实例时区后才能发布调度。

<a id="workflow-center-v0.1-发布验收"></a>

### 发布验收

<a id="workflow-center-v0.1-自动化检查"></a>

#### 自动化检查

```powershell
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m ruff check --no-cache .
git diff --check
```

发布清单测试会自动验证：

- 清单覆盖全部 7 个工作流文件
- 工作流名称与清单一致且不重复
- 所有导出文件保持未激活
- 不包含实例 ID、Webhook ID 或 Credential 引用
- 不包含常见明文 Token
- 错误处理器在主工作流之前导入和发布
- 主工作流声明 Error Workflow 手动绑定

<a id="workflow-center-v0.1-真实场景"></a>

#### 真实场景

| 场景 | 通过标准 |
| --- | --- |
| AI 成功 | 数据库状态为 `succeeded`，保存输出、耗时和 Token |
| 人工审核 | 数据库状态为 `needs_human_review` |
| 重复事件 | 不再次调用 AI，`duplicate_count` 加 1 |
| 自动失败 | Error Trigger 将状态更新为 `failed` 并保存错误 |
| 失败回放 | 复用原 `run_id`，`retry_count` 加 1，成功后清空错误 |

<a id="workflow-center-v0.1-最终门禁结果"></a>

#### 最终门禁结果

2026-09-04 的发布候选检查结果：

- 自动化测试：`81 passed`
- Ruff：全部通过
- Git diff 格式检查：通过
- API 容器：`healthy`
- n8n 容器：`healthy`
- n8n 版本：`2.36.8`
- n8n 到 FastAPI：`{"status":"ok"}`
- FastAPI OpenAPI：版本 `1.0.0`，包含 5 个工作流路径

<a id="workflow-center-v0.1-n8n-安全审计"></a>

#### n8n 安全审计

执行 `docker compose exec n8n n8n audit` 后确认：

- HTTP Request 与 Code 节点被识别为高能力节点，发布前必须继续进行参数审查
- 主工作流 Webhook 当前没有认证，只允许用于本机或可信网络
- 本机存在一个未被激活工作流使用的 `OpenAI account` Credential，应由实例管理员确认是否仍需保留
- 审计提示存在较新的 n8n 补丁版本；v0.1.0 暂时冻结已完成真实验收的 `2.36.8`，升级需要单独执行兼容性回归

上述结果没有改变仓库工作流已移除 Credential 引用和明文 Token 的结论。

<a id="workflow-center-v0.1-发布流程"></a>

### 发布流程

质量门禁全部通过后：

```powershell
git add README.md CHANGELOG.md backend docs n8n tests
git commit -m "release: publish Workflow Center v0.1.0"
git tag -a workflow-center-v0.1.0 -m "Workflow Center v0.1.0"
git push -u origin feature/workflow-center-v0.1-release
git push origin workflow-center-v0.1.0
```

正式发布前必须再次确认 `git status --short` 没有未提交文件，并核对标签指向
最终验收提交。

<a id="workflow-center-v0.1-当前限制"></a>

### 当前限制

- 工作流运行接口尚未增加调用方认证和租户隔离
- 发布包不会携带 Credential，导入目标实例后必须重新绑定
- Error Workflow 使用实例内工作流 ID 关联，不能跨实例直接保留
- Day 40 当前仍使用固定测试记录，而不是直接查询 `workflow_runs`
- 失败回放由调用方显式传入 `replay: true`，尚未实现定时自动重试
- 当前是单机 SQLite 与 n8n 命名卷部署，不是高可用生产集群
- Webhook 尚未增加签名、限流和重放窗口校验
- n8n 2.36.8 不是审计时的最新补丁版本，外部部署前应先评估升级并执行全量回归

<a id="workflow-center-v0.1-参考资料"></a>

### 参考资料

- [n8n CLI commands](https://docs.n8n.io/hosting/cli-commands/)
- [n8n source control environments](https://docs.n8n.io/source-control-environments/create-environments/)
- [n8n security audit](https://docs.n8n.io/hosting/securing/security-audit/)
- [Day 41：n8n 工作流数据库持久化](#n8n-workflow-persistence)

---

<a id="summary"></a>

## 本周总结（阶段记录）

<a id="summary-本周目标"></a>

### 本周目标

Week 6 的目标是掌握 n8n 工作流自动化，并把 Webhook、FastAPI、Dify、LLM
和 SQLite 连接成可运行、可追踪、可恢复、可版本化发布的企业工作流中心。

本周最终产出为：Workflow Center v0.1.0。

<a id="summary-学习进度"></a>

### 学习进度

<a id="summary-day-36n8n-基础与部署"></a>

#### Day 36：n8n 基础与部署

- 使用 Docker Compose 部署固定版本 n8n 2.36.8
- 配置健康检查、时区、执行数据清理和命名卷
- 建立最小手动工作流
- 学习工作流 JSON 导出和安全脱敏

<a id="summary-day-37webhook-触发"></a>

#### Day 37：Webhook 触发

- 建立测试 URL 和生产 URL
- 规范化外部请求字段
- 使用 Respond to Webhook 返回显式 JSON
- 验证测试监听与发布后的生命周期差异

<a id="summary-day-38连接-ai-工作流"></a>

#### Day 38：连接 AI 工作流

- 从 n8n 调用 FastAPI `/dify/workflow`
- 完成请求映射、超时配置和结构化响应
- 验证测试与生产 Webhook

<a id="summary-day-39ai-邮件助手"></a>

#### Day 39：AI 邮件助手

- 规范化邮件事件
- 分类请求类型和优先级
- 为敏感或高风险请求增加人工审核
- 为低风险请求生成 AI 回复草稿

<a id="summary-day-40ai-工作流日报"></a>

#### Day 40：AI 工作流日报

- 支持 Schedule Trigger 和手动回放
- 聚合成功率、失败类型、耗时和 Token
- 使用原生 LLM Chain 生成受约束日报
- 验证正常、无数据和非法日期场景

<a id="summary-day-41数据库持久化"></a>

#### Day 41：数据库持久化

- 新增 SQLite `workflow_runs` 运行账本
- 新增登记、完成、失败和查询 API
- 使用 `(workflow_name, event_id)` 实现幂等
- 使用 Error Trigger 自动保存失败
- 支持失败记录最多 3 次回放
- 验证成功、人工审核、重复、失败和回放场景

<a id="summary-day-42发布-workflow-center-v010"></a>

#### Day 42：发布 Workflow Center v0.1.0

- 冻结 7 个版本化工作流的发布范围
- 新增机器可读发布清单
- 区分 reference、optional 和 release 工作流
- 固定导入、手动绑定和发布顺序
- 增加跨工作流可移植性与敏感信息测试
- 补齐 OpenAPI、API 文档和组件发布说明
- 使用独立组件标签避免与平台 `v0.1.0` 冲突

<a id="summary-系统架构"></a>

### 系统架构

```text
外部邮件 / HTTP 请求
        ↓
n8n Webhook
        ↓
运行登记与幂等判断 ───────→ SQLite workflow_runs
        ↓                              ↑
规则分类与人工审核                    │
        ↓                              │
FastAPI /dify/workflow                │
        ↓                              │
Dify 企业咨询分流                     │
        ↓                              │
Knowledge Hub / RAG                   │
        ↓                              │
统一响应与运行完成 ────────────────────┘

n8n 自动执行失败
        ↓
Error Trigger
        ↓
按 execution_id 保存失败
```

<a id="summary-v010-发布结构"></a>

### v0.1.0 发布结构

```text
n8n/
├── workflow-center-v0.1.0.json
└── workflows/
    ├── w6d36-foundation-check.json
    ├── w6d37-customer-request-webhook.json
    ├── w6d38-ai-customer-request.json
    ├── w6d39-ai-email-assistant.json
    ├── w6d40-daily-workflow-report.json
    ├── w6d41-workflow-error-handler.json
    └── w6d41-persistent-ai-email-assistant.json
```

发布清单是组件版本的单一事实来源。新增、删除或重命名工作流后，如果没有同步
修改清单，自动化测试会失败。

<a id="summary-工程能力"></a>

### 工程能力

- 工作流 JSON 纳入 Git 版本控制
- 导出文件默认未激活，避免导入即触发生产任务
- 实例 ID、Webhook ID、Credential 和项目元数据不进入仓库
- FastAPI OpenAPI 描述覆盖工作流运行接口
- SQLite 使用事务和唯一约束保护运行状态
- 自动化测试覆盖数据库、服务、路由、工作流结构和发布清单
- Docker Compose 提供 API 与 n8n 的可重复运行环境

<a id="summary-安全设计"></a>

### 安全设计

- `.env` 被 Git 忽略，`.env.example` 只保留空占位符
- Dify API Key 只由 FastAPI 服务端读取
- n8n Credential 不随工作流 JSON 导出
- n8n 仅绑定 `127.0.0.1:5678`
- 运行数据和 n8n 配置使用独立持久化目录或命名卷
- 发布清单测试扫描常见明文 Token 模式

<a id="summary-质量门禁"></a>

### 质量门禁

Workflow Center v0.1.0 发布必须同时满足：

- Pytest 全量通过
- Ruff 全量通过
- Git diff 格式检查通过
- API 与 n8n 容器健康
- n8n 版本为 2.36.8
- n8n 容器可以访问 FastAPI `/health`
- OpenAPI 包含 5 个工作流运行接口
- 7 个工作流文件均可解析且通过可移植性检查
- Day 41 五类真实场景结果保持有效

2026-09-04 最终结果为：`81 passed`、Ruff 全部通过、API 与 n8n 容器均为
`healthy`、n8n 到 FastAPI 健康检查成功、OpenAPI 包含 5 个工作流路径。

n8n 安全审计同时标记了无认证 Webhook、高能力 HTTP Request/Code 节点、一个
未使用 Credential 和可用的新补丁版本。这些项目已记录在发布说明中；它们是
本地 v0.1.0 的部署边界与后续加固事项，不是明文密钥泄露。

<a id="summary-当前限制"></a>

### 当前限制

- 运行接口尚未增加认证、租户隔离和限流
- Day 40 日报仍以固定记录作为可复现实验基线
- Credential 和 Error Workflow 需要在导入目标实例手动绑定
- 无认证 Webhook 只允许在本机或可信网络使用
- 当前冻结 n8n 2.36.8；升级到新补丁版本前必须执行兼容性回归
- 当前部署适合本地学习、内部演示和单机验证，不是高可用生产架构

<a id="summary-week-6-成果"></a>

### Week 6 成果

Week 6 已完成从最小 n8n 节点到可发布工作流组件的完整闭环。Workflow Center
v0.1.0 已具备接收业务事件、调用 AI、人工兜底、运行留痕、错误恢复、版本控制
和发布验收能力，为 Week 7 接入飞书、企业微信和 CRM 奠定了统一运行基础。

详细发布步骤见 [Workflow Center v0.1.0 发布说明](#workflow-center-v0.1)。
