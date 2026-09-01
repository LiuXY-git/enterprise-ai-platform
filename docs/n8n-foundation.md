# Day 36：n8n 基础与本地部署

## 学习目标

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

## 核心概念

### Workflow

Workflow 是由一组节点以及节点之间的连接关系构成的自动化流程。

一个工作流通常包括：

1. 触发工作流的 Trigger
2. 读取、转换或生成数据的处理节点
3. 调用外部服务的集成节点
4. 保存、发送或返回结果的输出节点

n8n 工作流可以导出为 JSON 文件，从而进入 Git 版本控制。

### Trigger

Trigger 是工作流的起点，用于决定工作流何时开始执行。

常见 Trigger 包括：

- Manual Trigger：由开发者手动执行
- Webhook Trigger：收到 HTTP 请求时执行
- Schedule Trigger：按照时间计划执行
- 应用 Trigger：收到外部系统事件时执行

Day 36 使用 `Manual Trigger`，因为当前目标是验证基础环境和数据流，不对外提供正式触发入口。

### Node

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

### Item

Item 是 n8n 节点之间传递数据的基本单位。

一个节点可以接收或输出一个或多个 Item。每个 Item 通常包含一个 JSON 对象。

本次工作流最终输出一个 Item，其中包含六个字段。

### Expression

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

### 手动执行与发布

编辑器中的 `Execute workflow` 用于开发和测试阶段的手动执行。

当前工作流只用于基础验证，因此保持未发布状态。导出的工作流 JSON 中：

```json
"active": false
```

后续创建 Webhook、Schedule 或其他生产触发工作流时，再根据实际需要发布或启用。

## 本地部署架构

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

## 项目资产

Day 36 新增或修改的主要文件如下：

```text
enterprise-ai-platform/
├── .env
├── .env.example
├── compose.yaml
├── docs/
│   ├── README.md
│   └── n8n-foundation.md
└── n8n/
    └── workflows/
        └── w6d36-foundation-check.json
```

各文件用途：

- `.env`：保存本地真实配置和加密密钥，不提交到 Git
- `.env.example`：保存不含真实密钥的配置模板
- `compose.yaml`：定义 FastAPI 和 n8n 服务
- `docs/n8n-foundation.md`：记录 Day 36 学习与验收结果
- `n8n/workflows/w6d36-foundation-check.json`：版本化保存的工作流

## 环境变量说明

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

## Docker Compose 配置

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

## 启动与状态检查

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

## 健康检查

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

## W6D36 Foundation Check 工作流

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

### Start Manually

节点类型：

```text
Manual Trigger
```

作用是由开发者在编辑器中手动启动工作流。

Manual Trigger 本身不提供业务字段，因此输入面板显示没有字段属于正常现象。

### Build Foundation Result

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

## 工作流导出与版本控制

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

## 持久化验收

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

## 安全注意事项

### 不提交 `.env`

真实的 `N8N_ENCRYPTION_KEY` 只允许保存在 `.env`。

提交前检查：

```powershell
git check-ignore -v .env
git ls-files .env
```

预期：

- `git check-ignore` 显示 `.env` 被 `.gitignore` 忽略
- `git ls-files .env` 没有任何输出

### 不公开真实密钥

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

### 检查工作流凭据引用

导出包含凭据节点的工作流时，即使没有导出真实密钥，也可能包含凭据名称或内部 ID。

因此，每次提交工作流 JSON 前都应检查：

- 是否存在 `credentials`
- 是否存在真实 Token 或 API Key
- 是否包含测试数据中的个人信息
- 是否包含不应公开的内部地址

当前 Day 36 工作流没有使用任何凭据。

### 谨慎删除数据卷

以下命令不会删除命名卷：

```powershell
docker compose down
```

以下命令会删除 Compose 管理的命名卷：

```powershell
docker compose down -v
```

除非明确准备清空 n8n 的账户、工作流和本地数据，否则不要使用 `-v`。

## 常见问题

### 容器显示 `health: starting`

n8n 刚启动时需要初始化数据库和服务。

等待约 20 秒后重新检查：

```powershell
docker compose ps n8n
```

如果长时间没有变为 `healthy`，查看日志：

```powershell
docker compose logs --tail 100 n8n
```

### PowerShell 无法调用静态 GetBytes

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

### n8n 容器无法访问 FastAPI

在 n8n 容器内部，不应使用：

```text
http://localhost:8000
```

应使用 Compose 服务名：

```text
http://api:8000
```

因为两个容器通过 Docker Compose 默认网络进行通信。

### 工作流重建后丢失

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

## Day 36 验收结果

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

## Day 36 总结

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

## 参考资料

- [n8n 官方文档](https://docs.n8n.io/)
- [n8n Docker 安装](https://docs.n8n.io/hosting/installation/docker/)
- [n8n 工作流导入与导出](https://docs.n8n.io/build/manage-workflows/export-and-import)
- [n8n 环境变量：Endpoints](https://docs.n8n.io/hosting/configuration/environment-variables/endpoints/)
- [n8n GitHub Releases](https://github.com/n8n-io/n8n/releases)
