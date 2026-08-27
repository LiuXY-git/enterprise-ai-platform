# Day 30：Dify 接入 Knowledge Hub

## 今日目标

- 让 Dify 复用现有 Knowledge Hub 检索能力
- 实现符合 Dify 协议的外部知识库接口
- 使用 API Key 保护检索接口
- 将外部知识库接入“企业客服助手”

## 系统调用链路

    用户提问
        ↓
    Dify 企业客服助手
        ↓
    Enterprise Knowledge Hub 外部知识库
        ↓
    POST /retrieval
        ↓
    FastAPI Retrieval Service
        ↓
    Chroma 向量数据库
        ↓
    返回相关知识片段
        ↓
    qwen3.7-plus 生成回答

Dify 负责应用编排、对话界面和模型调用，Enterprise AI Platform 继续负责文档索引与向量检索。

## 配置项

`.env.example` 增加：

    DIFY_EXTERNAL_KNOWLEDGE_API_KEY=
    DIFY_EXTERNAL_KNOWLEDGE_ID=enterprise-knowledge-hub

真实 API Key 只保存在本地 `.env`，不能提交到 Git。

## 外部知识库接口

接口地址：

    POST /retrieval

Dify 容器访问地址：

    http://host.docker.internal:8000/retrieval

接口使用 Bearer Token 鉴权。

请求示例：

    {
      "knowledge_id": "enterprise-knowledge-hub",
      "query": "系统支持哪些文档格式？",
      "retrieval_setting": {
        "top_k": 3,
        "score_threshold": 0.0
      }
    }

响应示例：

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

## 实现内容

- 新增 Dify 外部知识库请求与响应模型
- 新增外部知识库配置读取服务
- 新增 `POST /retrieval` 接口
- 使用 Bearer Token 验证 API Key
- 验证外部知识库 ID
- 调用现有 `search_chunks` 检索服务
- 将 Chroma 距离转换为相关性分数
- 根据 Score 阈值过滤结果
- 返回符合 Dify 协议的知识片段
- 增加接口自动化测试

## Docker 网络配置

Dify 运行在独立 Docker Compose 环境中，使用以下地址访问宿主机上的 Knowledge Hub：

    http://host.docker.internal:8000

Dify 的 `docker/.env` 允许 SSRF Proxy 访问：

    SSRF_PROXY_ALLOW_PRIVATE_DOMAINS=marketplace.dify.ai,host.docker.internal

## Dify 配置

外部知识库配置：

- 名称：Enterprise Knowledge Hub
- 外部知识库 ID：`enterprise-knowledge-hub`
- Top K：3
- Score 阈值：关闭
- 模型：`qwen3.7-plus`

“企业客服助手”已关联该知识库，并要求涉及项目、架构、API、部署和学习进度的问题优先依据知识库回答。

## 验收结果

### 网络连通性

Dify API 容器访问 Knowledge Hub 健康检查成功：

    200 {"status":"ok"}

### 外部知识库接口

直接调用 `/retrieval` 成功返回：

- 知识片段内容
- 相关性分数
- 来源文档名称
- Chunk 元数据

### Dify 召回测试

问题：

    当前项目版本是多少？

Dify 成功显示召回片段、来源文档和相关性分数。

### 企业客服助手测试

问题：

    系统支持哪些文档格式？

回答正确包含：

- PDF
- DOCX
- Markdown

问题：

    当前项目完成了哪些 RAG 能力？

回答正确说明了文档切分、Embedding、Chroma 检索、受约束回答和来源引用等能力。

## 安全设计

- API Key 只保存在服务端环境变量
- 使用 Bearer Token 传递认证信息
- 使用安全比较方式验证 Token
- 无效 API Key 返回 `401`
- 未知知识库 ID 返回 `404`
- 服务配置不完整返回 `503`

## 当前限制

- Chroma 中部分索引来源于旧版文档，可能返回 `v0.3.0` 等历史内容
- 文档更新后需要重新建立向量索引
- `metadata_condition` 当前只接收参数，尚未执行元数据过滤
- 距离到相关性分数目前使用简单归一化算法

## 今日成果

Dify 已成功复用 Enterprise AI Platform 的 Knowledge Hub。系统完成了从 Dify 对话应用、外部知识库 API、FastAPI 检索服务到 Chroma 向量数据库的完整集成链路。