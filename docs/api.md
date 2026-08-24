# API 文档

Enterprise AI Platform 当前版本为 v0.3.0，提供文档上传、向量检索和带来源回答等接口。

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

当前业务接口暂未启用用户身份验证。

DeepSeek 或通义千问的 API Key 只配置在服务端 `.env` 文件中，调用本平台接口时不需要传递模型密钥。

## 接口总览

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| GET | `/health` | 检查服务运行状态 |
| POST | `/chat` | 发送基础聊天消息 |
| POST | `/upload` | 上传、解析并索引文档 |
| POST | `/rag/query` | 检索相关文档片段 |
| POST | `/rag/answer` | 生成带来源引用的回答 |

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
      "text": "当前项目版本为 v0.3.0。",
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
  "answer": "当前项目版本为 v0.3.0。[来源1]",
  "sources": [
    {
      "label": "[来源1]",
      "id": "readme-chunk-13",
      "source": "README.md",
      "chunk_index": 13,
      "text": "当前项目版本为 v0.3.0。",
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

- 当前接口暂未增加用户登录和 API Key 鉴权
- 文档上传后同步执行解析和索引，大文件可能需要较长时间
- 上传接口会将提取后的完整文本返回给调用方
- 当前没有配置单个上传文件的大小上限
- 修改 LLM Provider 或模型配置后需要重启服务
- 检索质量依赖知识库内容、Chunk 参数和 Embedding 模型