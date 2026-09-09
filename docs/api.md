# API 文档

Enterprise AI Platform 当前版本为 v1.0.0，提供文档上传、向量检索、带来源回答和工作流运行管理接口。

## 访问地址

本地运行和 Docker 运行默认使用以下地址：

```text
http://127.0.0.1:8000
```

交互式接口文档：

- Swagger UI：`http://127.0.0.1:8000/docs`
- ReDoc：`http://127.0.0.1:8000/redoc`
- OpenAPI JSON：`http://127.0.0.1:8000/openapi.json`

## 身份验证

`/health`、`/chat`、`/dify/workflow`、`/upload`、`/rag/query`、`/rag/answer` 和 `/workflow-runs` 当前未启用调用方身份验证。

`/retrieval` 是供 Dify 调用的外部知识库接口，需要通过请求头传递专用 Bearer Token：

    Authorization: Bearer <DIFY_EXTERNAL_KNOWLEDGE_API_KEY>

DeepSeek、通义千问、Dify 应用以及 Dify 外部知识库的 API Key 均只保存在服务端 `.env` 文件中，不能提交到 Git。

## 接口总览

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| GET | `/health` | 检查服务运行状态 |
| POST | `/chat` | 发送基础聊天消息 |
| POST | `/dify/workflow` | 调用 Dify 企业咨询工作流 |
| POST | `/upload` | 上传、解析并索引文档 |
| POST | `/rag/query` | 检索相关文档片段 |
| POST | `/rag/answer` | 生成带来源引用的回答 |
| POST | `/retrieval` | 为 Dify 检索外部知识库内容 |
| POST | `/workflow-runs/start` | 登记工作流运行、拦截重复事件或开始回放 |
| PATCH | `/workflow-runs/{run_id}/result` | 保存成功或人工审核结果 |
| PATCH | `/workflow-runs/executions/{execution_id}/failure` | 按 n8n 执行号保存失败 |
| GET | `/workflow-runs` | 按报告日期查询运行记录 |
| GET | `/workflow-runs/{run_id}` | 查询单条运行记录 |

## GET `/health`

检查 FastAPI 服务是否正常运行。Docker 也使用该接口执行容器健康检查。

### 成功响应

状态码：`200 OK`

```json
{
  "status": "ok"
}
```

## POST `/chat`

发送一条基础聊天消息并返回平台回复。

该接口用于验证聊天请求和响应流程，不执行知识库检索。

### 请求体

```json
{
  "message": "你好，请介绍一下这个平台。"
}
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `message` | string | 是 | 用户消息，长度为 1～2000 个字符 |

### 成功响应

状态码：`200 OK`

```json
{
  "reply": "你好，这是 Enterprise AI Platform。"
}
```

### 错误响应

- `422 Unprocessable Entity`：消息为空、过长或请求格式错误

## POST `/dify/workflow`

由 FastAPI 调用已经发布的 Dify 企业咨询工作流，并以阻塞模式返回最终回答、输出变量和运行元数据。

Dify 应用 API Key 只由 FastAPI 从服务端环境变量读取，不会暴露给接口调用方。

### 服务端配置

Docker Compose 运行时，在 `.env` 中配置：

```properties
DIFY_API_BASE_URL=http://host.docker.internal/v1
DIFY_WORKFLOW_API_KEY=<DIFY_APP_API_KEY>
DIFY_WORKFLOW_TIMEOUT_SECONDS=120
```

`DIFY_WORKFLOW_API_KEY` 必须是“企业咨询分流工作流”的应用 API Key，不能与外部知识库 Key 混用。

### 请求体

```json
{
  "question": "系统支持哪些文档格式？",
  "user": "day34-demo-user"
}
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `question` | string | 是 | 提交给 Dify `user_query` 输入变量的问题，长度为 1～2000 个字符 |
| `user` | string | 是 | 调用方定义的稳定终端用户标识，长度为 1～128 个字符 |

### 成功响应

状态码：`200 OK`

```json
{
  "task_id": "task-id",
  "workflow_run_id": "workflow-run-id",
  "status": "succeeded",
  "answer": "系统支持 PDF、DOCX 和 Markdown。",
  "outputs": {
    "answer": "系统支持 PDF、DOCX 和 Markdown。"
  },
  "elapsed_time": 5.5,
  "total_tokens": 1626,
  "total_steps": 6
}
```

### 错误响应

- `422 Unprocessable Entity`：问题为空、过长，或 `user` 格式不正确
- `503 Service Unavailable`：Dify 配置错误、网络不可用、API Key 无效或工作流执行失败

## POST `/upload`

上传 PDF、DOCX 或 Markdown 文件。

接口会依次完成：

1. 读取上传文件
2. 提取文档文本
3. 保存文档元数据
4. 切分文本 Chunk
5. 生成 Embedding
6. 写入 Chroma 向量数据库
7. 将文档状态更新为 `indexed`

接口成功返回后，上传文档可以直接参与 RAG 检索。

### 请求格式

内容类型：

```text
multipart/form-data
```

表单字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `file` | binary | 是 | PDF、DOCX、MD 或 Markdown 文件 |

### 支持的文件类型

| 文件类型 | 扩展名 |
| --- | --- |
| PDF | `.pdf` |
| Word | `.docx` |
| Markdown | `.md`、`.markdown` |

### 成功响应

状态码：`200 OK`

```json
{
  "document_id": 12,
  "filename": "architecture.md",
  "content_type": "text/markdown",
  "size": 340,
  "file_type": "markdown",
  "status": "indexed",
  "text": "# 系统架构\n\n当前系统使用 FastAPI。",
  "chunk_count": 2,
  "page_count": null,
  "paragraph_count": null,
  "line_count": 13
}
```

统计字段说明：

- PDF 使用 `page_count`
- DOCX 使用 `paragraph_count`
- Markdown 使用 `line_count`
- 不适用于当前文件类型的统计字段返回 `null`

### 错误响应

- `400 Bad Request`：文件为空、读取失败或文档解析失败
- `415 Unsupported Media Type`：文件类型不受支持
- `422 Unprocessable Entity`：请求中缺少 `file` 字段
- `500 Internal Server Error`：数据库或向量索引处理失败

错误示例：

```json
{
  "detail": "只支持 PDF、DOCX 和 Markdown 文件"
}
```

## POST `/rag/query`

从 Chroma 向量数据库中检索与问题最相关的文档片段。

该接口只执行检索，不调用大语言模型。

### 请求体

```json
{
  "question": "当前项目版本是多少？",
  "top_k": 3
}
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `question` | string | 是 | 知识库问题，长度为 1～500 个字符 |
| `top_k` | integer | 否 | 返回结果数量，范围为 1～10，默认值为 3 |

### 成功响应

状态码：`200 OK`

```json
{
  "question": "当前项目版本是多少？",
  "results": [
    {
      "id": "readme-chunk-13",
      "text": "当前项目版本为 v1.0.0。",
      "source": "README.md",
      "chunk_index": 13,
      "distance": 0.82
    }
  ]
}
```

`distance` 是问题向量与文档向量之间的距离，数值越小通常表示相关性越高。

### 错误响应

- `422 Unprocessable Entity`：问题为空或 `top_k` 超出范围
- `500 Internal Server Error`：Embedding 模型或向量数据库处理失败

## POST `/rag/answer`

检索知识库并调用当前配置的大语言模型生成自然语言回答。

回答中的 `[来源N]` 标签与 `sources` 列表中的 `label` 字段一一对应。

### 请求体

```json
{
  "question": "当前项目版本是多少？",
  "top_k": 3
}
```

### 成功响应

状态码：`200 OK`

```json
{
  "question": "当前项目版本是多少？",
  "answer": "当前项目版本为 v1.0.0。[来源1]",
  "sources": [
    {
      "label": "[来源1]",
      "id": "readme-chunk-13",
      "source": "README.md",
      "chunk_index": 13,
      "text": "当前项目版本为 v1.0.0。",
      "distance": 0.82
    }
  ]
}
```

### 错误响应

- `422 Unprocessable Entity`：问题为空或 `top_k` 超出范围
- `503 Service Unavailable`：模型配置错误或模型服务暂时不可用

错误示例：

```json
{
  "detail": "LLM 调用失败"
}
```

## POST `/retrieval`

按照 Dify 外部知识库协议检索 Knowledge Hub 中的文档片段。

该接口只执行向量检索，不直接调用大语言模型。

### 身份验证

请求头必须包含：

    Authorization: Bearer <DIFY_EXTERNAL_KNOWLEDGE_API_KEY>

### 请求体

```json
{
  "knowledge_id": "enterprise-knowledge-hub",
  "query": "系统支持哪些文档格式？",
  "retrieval_setting": {
    "top_k": 3,
    "score_threshold": 0.0
  }
}
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `knowledge_id` | string | 是 | Dify 中配置的外部知识库 ID |
| `query` | string | 是 | 检索问题，长度为 1～500 个字符 |
| `retrieval_setting.top_k` | integer | 是 | 返回数量，范围为 1～10 |
| `retrieval_setting.score_threshold` | number | 是 | 最低相关性分数，范围为 0～1 |
| `metadata_condition` | object | 否 | 可选元数据过滤条件，当前尚未执行过滤 |

### 成功响应

状态码：`200 OK`

返回内容示例：

    {
      "records": [
        {
          "content": "系统支持 PDF、DOCX 和 Markdown 文档。",
          "score": 0.8,
          "title": "README.md",
          "metadata": {
            "chunk_id": "readme-chunk-1",
            "chunk_index": 1,
            "source": "README.md",
            "distance": 0.25
          }
        }
      ]
    }

字段说明：

| 字段 | 说明 |
| --- | --- |
| `content` | 检索到的文档片段 |
| `score` | 转换后的相关性分数，越大表示越相关 |
| `title` | 来源文档名称 |
| `metadata` | Chunk ID、序号、来源和原始向量距离 |

### 错误响应

- `401 Unauthorized`：缺少 Bearer Token 或 API Key 无效
- `404 Not Found`：外部知识库 ID 不存在
- `422 Unprocessable Entity`：请求格式错误或参数超出范围
- `503 Service Unavailable`：外部知识库配置不完整
- `500 Internal Server Error`：Embedding 或 Chroma 检索失败

## Workflow Runs 工作流运行接口

Workflow Center v0.1.0 使用这些接口保存 n8n 工作流的输入、输出、状态、
请求者、耗时、Token、重复次数和失败回放次数。

### POST `/workflow-runs/start`

每次 n8n 执行开始时登记运行。`workflow_name` 和 `event_id` 组成业务唯一键。

```json
{
  "event_id": "mail-20260903-001",
  "workflow_name": "w6d41_ai_email_assistant",
  "source": "email",
  "requester": "customer-001",
  "report_date": "2026-09-03",
  "input_data": {
    "subject": "文档格式咨询",
    "body": "系统支持哪些文档格式？"
  },
  "n8n_execution_id": "42",
  "replay": false
}
```

首次运行返回 `should_process: true`。相同事件再次请求时返回
`duplicate: true` 和 `should_process: false`，不会再次执行 AI。失败记录只有在
`replay: true` 时才会重新运行，并复用首次保存的 `input_data`。

```json
{
  "run_id": "35ea68ad-99d9-4a53-b59e-cc51da785f31",
  "status": "running",
  "should_process": true,
  "duplicate": false,
  "replayed": false,
  "retry_count": 0,
  "duplicate_count": 0,
  "input_data": {
    "subject": "文档格式咨询",
    "body": "系统支持哪些文档格式？"
  }
}
```

### PATCH `/workflow-runs/{run_id}/result`

保存成功或人工审核结果。`status` 只能是 `succeeded` 或
`needs_human_review`。

```json
{
  "status": "succeeded",
  "output_data": {
    "answer": "系统支持 PDF、DOCX 和 Markdown。"
  },
  "category": "product",
  "priority": "normal",
  "elapsed_time": 2.4,
  "total_tokens": 180
}
```

### PATCH `/workflow-runs/executions/{execution_id}/failure`

供 n8n Error Trigger 根据执行 ID 保存自动失败。

```json
{
  "error_type": "n8n_execution_error",
  "error_message": "The resource could not be found"
}
```

重复提交同一个已失败执行是幂等操作。只有 `running` 状态可以转为
`failed`。

### GET `/workflow-runs`

`report_date` 是必填查询参数：

```text
GET /workflow-runs?report_date=2026-09-03
```

响应包含 `report_date`、`count` 和 `runs`。日报工作流可以直接消费该列表。

### GET `/workflow-runs/{run_id}`

返回单条完整运行记录，包括原始输入、最终输出、状态、n8n 执行 ID、错误信息
和时间指标。

工作流接口可能返回：

- `404 Not Found`：运行 ID 或 n8n 执行 ID 不存在
- `409 Conflict`：状态转换不合法、非失败记录请求回放或超过 3 次回放
- `422 Unprocessable Entity`：日期、标识符或请求字段格式错误


## 企业微信通知

### POST `/integrations/wecom/messages`

通过服务端配置的企业微信自建应用向一个内部测试成员发送文本通知。调用方不能指定接收者或传入凭据。

```json
{
  "text": "Day 45 企业微信测试消息",
  "request_id": "day45-smoke-001"
}
```

`text` 去除首尾空白后不能为空，UTF-8 编码最多 2048 字节。`request_id` 只用于追踪，不提供持久化幂等保证。

成功返回 `200`；请求校验失败返回 `422`；配置、鉴权或发送失败返回 `503`。当 `detail.code` 为 `delivery_unknown` 时，消息可能已经送达，应先核对实际接收情况，不得直接自动重发。完整说明见 [企业微信自建应用通知](wecom-notifications.md)。

## 推荐调用流程

知识库的典型调用顺序为：

```text
上传文档
   ↓
POST /upload
   ↓
自动解析并建立向量索引
   ↓
POST /rag/query
   ↓
验证检索结果
   ↓
POST /rag/answer
   ↓
获得带来源引用的回答
```

## 当前限制

- 除 Dify 外部知识库 `/retrieval` 外，其他业务接口暂未增加用户登录和 API Key 鉴权；`/workflow-runs` 只适用于当前本地可信网络
- `/dify/workflow` 使用固定服务端 Dify 应用 Key，尚未增加调用方级别的认证和限流
- 文档上传后同步执行解析和索引，大文件可能需要较长时间
- 上传接口会将提取后的完整文本返回给调用方
- 当前没有配置单个上传文件的大小上限
- 修改 LLM Provider 或模型配置后需要重启服务
- 检索质量依赖知识库内容、Chunk 参数和 Embedding 模型
- `/retrieval` 暂未增加调用频率限制和 IP 白名单
- `metadata_condition` 当前尚未用于实际过滤
- 文档内容更新后需要重新建立 Chroma 向量索引
