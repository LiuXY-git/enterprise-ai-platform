# 平台使用指南

本指南对应 Day 54 的代码状态，带你完成启动、知识库问答、工作流试用和结果核对。首次使用从第 2 节开始；已有 Day 53 部署可以直接检查服务，再选择场景。

## 1. 选择入口

| 目标 | 使用入口 | 当前结果 |
| --- | --- | --- |
| 上传企业资料并提问 | API 的 `/docs` → `/upload`、`/rag/query`、`/rag/answer` | 文档索引、检索片段、带来源的回答 |
| 企业客服咨询 | [客服模板](../n8n/templates/customer-service/README.md) | Dify 依据已接入的知识库回答 |
| 邮件分类与草稿 | [邮件模板](../n8n/templates/email-assistant/README.md) | 分类、人工复核标记或回复草稿；没有邮箱监听和邮件发送 |
| 销售线索跟进 | [销售模板](../n8n/templates/sales-followup/README.md) | 分析、模拟 CRM 跟进记录和通知预览 |

本机默认入口为 [API 文档](http://127.0.0.1:8000/docs) 和 [n8n 编辑器](http://127.0.0.1:5678/)。当前没有统一的业务前端。`/chat` 仍为回显示例；知识库生成回答请使用 `/rag/answer`。

## 2. 准备和启动

### 首次使用

准备 Git、已运行的 Docker Desktop（Linux 容器）和 PowerShell。部署脚本要求 Docker Compose 2.20 或以上，默认使用本机 8000、5678 端口。Dify 需要按 [Dify 部署说明](dify-basics.md) 独立准备，本项目 Compose 只管理 API 与 n8n。

以下命令使用当前项目路径；放在其他位置时修改第一行。已有 `.env` 会保留：

```powershell
Set-Location 'C:\Users\Administrator\Desktop\enterprise-ai-platform'
if (-not (Test-Path -LiteralPath '.env')) {
    Copy-Item -LiteralPath '.env.example' -Destination '.env'
}
```

编辑本地 `.env`，按用途配置。变量说明和离线自检见 [Day 52 配置中心](day52-configuration-center.md)，n8n 首次账户和密钥设置见 [n8n 基础](n8n-foundation.md)。保留已有 `N8N_ENCRYPTION_KEY`，它用于解密实例内保存的凭据。

| 用途 | 配置位置 | 谁使用模型或密钥 |
| --- | --- | --- |
| n8n 启动 | `.env` 的 `N8N_ENCRYPTION_KEY` | n8n 凭据加密；不是模型密钥 |
| API RAG 回答 | `.env` 的 `LLM_PROVIDER` 及对应 DeepSeek/Qwen 配置 | API 的 LLM 服务 |
| 客服、邮件调用 Dify | `.env` 的 `DIFY_API_BASE_URL`、`DIFY_WORKFLOW_API_KEY` | API 调用已发布的 Dify 工作流；模型在 Dify 中选择 |
| Dify 回查知识库 | `.env` 的 `DIFY_EXTERNAL_KNOWLEDGE_API_KEY`、`DIFY_EXTERNAL_KNOWLEDGE_ID`，以及 Dify 外部知识库设置 | Dify 调用 API 的 `/retrieval`；与工作流应用 Key 不同 |
| 销售及 n8n 原生模型流程 | n8n Credentials 中的 DashScope 凭据 | n8n 模型节点；不会自动读取 API 的模型密钥 |

启动并检查：

```powershell
& .\scripts\start.ps1
```

脚本构建 API 镜像、启动 API/n8n、等待健康状态并检查数据库及挂载路径。准备好相关密钥后，也可以附加配置检查：

```powershell
& .\scripts\start.ps1 -CheckComponents llm,dify
```

`configuration_valid` 表示本地配置格式通过，`network_checked: false` 表示没有验证密钥是否有效或网络能否连通。容器 `healthy` 和 `Deployment completed and verified` 也不代表真实模型、Dify 业务流程或通知发送已经成功。

### 已部署环境

只检查现有容器，无需重新构建：

```powershell
& .\scripts\check-deployment.ps1 -CheckComponents llm,dify
```

更新应用代码或 `.env` 后再运行 `start.ps1`，使修改进入容器。仅启动 API 可加 `-ApiOnly`；Compose 配置仍要求 `N8N_ENCRYPTION_KEY`，细节见 [Day 53 部署说明](day53-compose-deployment.md)。

### 可选：本地 Python 环境

Docker 启动本身不依赖本机 Python。运行下面的离线请求生成器、开发或测试时，需要项目 Python 环境；当前 Docker 使用 Python 3.14。已有 `.venv` 可直接使用，没有时执行：

```powershell
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    py -3.14 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw '创建 Python 环境失败' }
}
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) { throw '安装依赖失败' }
```

本地调试入口和目录说明见 [后端说明](../backend/README.md)。

## 3. 使用知识库

1. 打开 API 文档，执行 `GET /health`，确认返回 `status: ok`。
2. 在 `POST /upload` 上传 PDF、DOCX 或 Markdown。可以使用 [Demo 资料](../demo/README.md)。确认索引状态为 `indexed`；仅上传成功但索引失败的文档不能视为可检索。
3. 执行 `POST /rag/query`，先检查返回的片段是否与问题相关。
4. 使用同样的请求调用 `POST /rag/answer`，核对回答及 `sources`。

```json
{
  "question": "员工如何申请 IT 支持？",
  "top_k": 3
}
```

`top_k` 范围为 1–10。`/rag/query` 只检索；`/rag/answer` 在检索到片段后才调用模型。未检索到片段时返回“无法从当前知识库确定。”和空来源。具体答案取决于实际上传资料；有来源也需要检查内容是否支持结论。

需要让 Dify 使用这些资料时，按 [Dify 接入 Knowledge Hub](dify-knowledge-hub.md) 配置外部知识库。只上传到 API 不会自动修改 Dify 应用配置。

## 4. 使用三类工作流模板

### 导入和绑定

先阅读对应模板说明，再导入其引用的工作流 JSON。`catalog.json` 和请求 `examples` 不是可导入工作流。同一实例已有可用工作流时直接复用，避免发布相同 Webhook 路径的副本。

| 模板 | 导入后必须完成的准备 |
| --- | --- |
| 客服 | API 能访问已发布的 Dify 工作流，Dify 知识库已接入；按 [客服说明](../n8n/templates/customer-service/README.md) 验证 |
| 邮件 | 先导入错误处理工作流，再导入主流程，在主流程 Settings 中绑定 Error Workflow；按 [邮件说明](../n8n/templates/email-assistant/README.md) 配置 Dify |
| 销售 | 在 `DashScope Qwen Chat Model` 节点绑定 DashScope 的 `openAiApi` 凭据；按 [销售说明](../n8n/templates/sales-followup/README.md) 核对模型和 API 地址 |

邮件的 Error Workflow 用于生产触发的错误处理，手动测试不能代替生产失败回调验收。销售流程使用自己的失败处理分支。

### 离线生成示例

以下示例只生成请求文件，不调用模型、不写 CRM，也不发送消息：

```powershell
$requestFile = Join-Path $env:TEMP ('workflow-demo-' + [guid]::NewGuid().ToString('N') + '.json')
.\.venv\Scripts\python.exe .\scripts\day50\render_template_request.py `
    --template sales-followup --scenario normal --output $requestFile
if ($LASTEXITCODE -ne 0) { throw '生成请求失败' }
$requestInfo = Get-Content -LiteralPath $requestFile -Raw -Encoding UTF8 | ConvertFrom-Json
$requestInfo | Select-Object template_id, scenario, execution_performed, url
```

替换参数可选择下列六种样例：

| `--template` | `--scenario` |
| --- | --- |
| `customer-service` | `question`、`unknown-answer` |
| `email-assistant` | `normal`、`human-review` |
| `sales-followup` | `normal`、`review-candidate` |

生成器为新样例生成独立事件标识，销售日期使用上海时区的当天日期，输出路径拒绝覆盖。`review-candidate` 只是复核候选输入，最终结果以模型输出及工作流校验为准。

### 手动执行并核对

默认生成 Test URL，先在 n8n 对相应 Webhook 开启测试监听。生产使用需先发布工作流，再给生成器加 `--production`；该参数只切换请求 URL。检查 `$requestInfo.body` 后，在同一 PowerShell 会话执行以下代码才会发送请求，可能产生模型用量并写入演示数据：

```powershell
$payload = $requestInfo.body | ConvertTo-Json -Depth 30 -Compress
$result = Invoke-RestMethod `
    -Method $requestInfo.method -Uri $requestInfo.url `
    -ContentType 'application/json; charset=utf-8' `
    -Headers @{ 'X-Client-Name' = 'day54-guide' } `
    -Body ([System.Text.Encoding]::UTF8.GetBytes($payload)) -TimeoutSec 180
$result | ConvertTo-Json -Depth 30
```

只发送生成文件内的 `body`，不要把整个请求说明文件作为业务请求体。请求超时时先核对 n8n 执行及原事件的运行记录，避免直接换新事件标识重复写入。

## 5. 看懂结果和标识

| 返回字段或标识 | 含义 | 查询位置 |
| --- | --- | --- |
| 客服的 `workflow_run_id`、直接 `/dify/workflow` 的 `workflow_run_id` | Dify 执行 ID | Dify 运行记录；不是平台账本 ID |
| 邮件的 `workflow_run_id` | 平台运行 ID | `GET /workflow-runs/{run_id}` |
| 销售的 `run_id` | 平台运行 ID | `GET /workflow-runs/{run_id}` |
| `event_id` | 调用方业务事件标识 | 邮件、销售按工作流名称与事件标识去重 |
| 销售的 `followup_id` | CRM 跟进记录 ID | CRM 接口；见 [API 文档](api.md) |
| `n8n_execution_id` | n8n 的某次执行 ID | n8n Executions；回放会产生新的执行 |

HTTP 请求成功后还要检查业务字段。邮件的人工复核分支可以没有草稿；销售需要同时看 `status`、`requires_human_review`、CRM 记录及 `notification`。`needs_human_review` 不等于系统故障，通知 `preview` 或 `skipped` 也不等于消息已送达。

销售流程当前输出通知预览；飞书独立接口的历史真实联调不能视为销售通知链路已接通。企业微信真实发送仍有环境前置条件，见 [企业微信说明](wecom-notifications.md)。

## 6. 排查与恢复

| 现象 | 先检查什么 | 处理方向 |
| --- | --- | --- |
| 容器未健康或 API 无法访问 | Docker 状态、端口、`check-deployment.ps1` 输出 | 按 [Day 53](day53-compose-deployment.md) 排查基础服务 |
| `configuration_valid`，业务调用仍失败 | Dify 是否发布、模型凭据、调用方可达的 URL、上游返回 | 离线配置检查没有验证这些条件 |
| Webhook 找不到或没有响应 | Test URL 是否正在监听，Production URL 对应流程是否发布 | 对齐触发方式与地址 |
| 请求返回 422 | 请求字段、类型、日期；是否误传整个请求说明文件 | 按模板契约修正；销售严格拒绝未知字段 |
| 重复事件没有再次执行 | 邮件/销售的原 `event_id` 与平台运行状态 | 这是重复保护；不要把重复事件当新事件重发 |
| 销售失败 | 运行中的失败阶段、检查点、CRM 是否已保存 | CRM 写入失败可显式回放并复用检查点；CRM 已保存后禁止整条回放 |
| 通知为 `delivery_unknown` | 是否实际送达、已有尝试记录 | 先人工核对，再按状态接口处理；状态接口本身不发送消息 |

邮件与销售的失败回放使用原事件、原输入及显式 `replay`，受服务端次数和状态限制，详见 [运行持久化](n8n-workflow-persistence.md) 与 [销售恢复说明](n8n-sales-followup-assistant.md)。不要删除运行记录来绕过去重。通知状态变为 `sent` 不会自动结束原先的 `failed` 工作流。

## 7. 日常运维与交付边界

- 应用日志在项目 `logs/app.log`，工作流事件日志在 `logs/workflow-events.jsonl`；规则与字段见 [Day 51](day51-workflow-logging.md)。排查时记录事件标识、平台运行 ID、n8n 执行 ID 和失败阶段。Dify 调用与运行完成事件的 Token 统计可能重叠，不要直接相加；缺失用量不能当作真实零用量。
- SQLite 与 Chroma 在项目 `data` 下，n8n 状态在 Compose 的 `n8n_data` 卷中。备份需覆盖业务数据、n8n 卷及其加密密钥；Dify 数据另行管理。详细路径见 [架构说明](architecture.md)。
- 日常停用可运行 `docker compose stop`，恢复可运行 `docker compose start` 并执行部署检查；更新代码或配置用 `start.ps1`。恢复启动不会构建新镜像。
- 当前是本机或可信网络的单机部署，业务 API/Webhook 尚无统一调用方认证、租户隔离和限流。没有统一全链路追踪，也未实现销售真实通知编排。

Day 54 整理操作入口与架构，不新增运行功能。真实模型、业务和通知的验收需要分别记录；文档示例和离线检查不能替代它们。
