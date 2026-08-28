# API 文档

Enterprise AI Platform 当前版本为 v1.0.0，提供文档上传、向量检索和带来源回答等接口。

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

`/health`、`/chat`、`/dify/workflow`、`/upload`、`/rag/query` 和 `/rag/answer` 当前未启用调用方身份验证。

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

- 除 Dify 外部知识库 `/retrieval` 外，其他业务接口暂未增加用户登录和 API Key 鉴权
- `/dify/workflow` 使用固定服务端 Dify 应用 Key，尚未增加调用方级别的认证和限流
- 文档上传后同步执行解析和索引，大文件可能需要较长时间
- 上传接口会将提取后的完整文本返回给调用方
- 当前没有配置单个上传文件的大小上限
- 修改 LLM Provider 或模型配置后需要重启服务
- 检索质量依赖知识库内容、Chunk 参数和 Embedding 模型
- `/retrieval` 暂未增加调用频率限制和 IP 白名单
- `metadata_condition` 当前尚未用于实际过滤
- 文档内容更新后需要重新建立 Chroma 向量索引
