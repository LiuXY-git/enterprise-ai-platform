# Enterprise AI Platform

一个面向企业场景的 AI 平台学习项目。

## 项目目标

通过 16 周持续开发，完成以下核心模块：

- Knowledge Hub：企业知识库与 RAG
- Workflow Center：企业 AI 自动化工作流
- Agent Center：企业智能体平台
- Evaluation Center：Agent 评测平台

## 当前进度

- [x] 初始化项目目录
- [x] 配置 VS Code
- [x] 配置 Ruff
- [x] 创建 FastAPI 服务
- [x] 添加健康检查接口
- [x] 添加聊天接口
- [x] Docker 化
- [x] 支持 PDF、DOCX 和 Markdown 上传
- [x] 提取文档文本
- [x] 使用 SQLite 保存文档元数据
- [x] 增加异常处理
- [x] 增加运行日志
- [x] 发布 Knowledge Hub v0.2.0
- [x] 实现文本切分和 Embedding
- [x] 接入 Chroma 向量数据库
- [x] 建立文档索引流程
- [x] 实现 RAG Query 检索
- [x] 实现受约束的 RAG Prompt
- [x] 返回自然语言回答和引用来源
- [x] 增加 RAG 自动化测试
- [x] 完成 RAG 黄金问题验收
- [x] 发布 Knowledge Hub v0.3.0
- [x] 上传文档后自动建立向量索引
- [x] 支持跨多个文档进行 RAG 检索
- [x] 完成 RAG 检索参数优化
- [x] 支持 DeepSeek 和通义千问模型切换
- [x] 完成 Docker 部署和容器级验收
- [x] 完善 OpenAPI 与 API 使用文档
- [x] 准备 Demo 数据和录制脚本
- [x] 准备 Knowledge Hub v1.0.0 代码和发布文档
- [x] 完成 Knowledge Hub v1.0.0 发布候选验收
- [x] 完成 Dify 1.16.1 本地部署
- [x] 配置通义千问 `qwen3.7-plus`
- [x] 创建并发布“企业客服助手”
- [x] 将现有 Knowledge Hub 接入 Dify 外部知识库
- [x] 创建并发布“企业咨询分流工作流”
- [x] 完成企业客服知识检索、受约束回答和日志留痕
- [x] 完成企业场景 Prompt 的角色、输出格式和安全约束优化
- [x] 完成 FastAPI 调用 Dify 企业咨询工作流
- [x] 完成 Week 5 总结和 AI 客服助手 v1.0 验收
- [x] 录制并验收 AI 客服助手 v1.0 Demo
- [x] 正式发布 Enterprise AI Platform v1.0.0

## 项目结构

```text
enterprise-ai-platform/
├── backend/     # Python 和 FastAPI 后端
├── docs/        # 架构、学习和接口文档
├── docker/      # Docker 配置
├── tests/       # 自动化测试
└── README.md
```
## 快速启动

### 本地运行

```powershell
.\.venv\Scripts\Activate.ps1
fastapi dev backend/app/main.py
```

访问接口文档：

```text
http://127.0.0.1:8000/docs
```

### Docker 运行

```powershell
docker compose up -d --build
```

停止并清理容器：

```powershell
docker compose down
```

## 项目文档

- [系统架构](docs/architecture.md)
- [技术选型](docs/tech-stack.md)
- [数据库设计](docs/database.md)
- [Week 1 总结](docs/week-1-summary.md)
- [Week 2 总结](docs/week-2-summary.md)
- [Embedding 学习笔记](docs/embedding.md)
- [RAG 黄金问题集](docs/rag-golden-questions.md)
- [Chunk 文本切分学习笔记](docs/chunking.md)
- [Chroma 向量数据库](docs/vector-database.md)
- [文档 Embedding 流程](docs/document-embedding.md)
- [RAG Query 检索](docs/rag-query.md)
- [RAG Prompt 与来源引用](docs/rag-prompt.md)
- [Week 3 总结](docs/week-3-summary.md)
- [多文档自动索引](docs/multi-document-indexing.md)
- [RAG 检索参数优化](docs/retrieval-optimization.md)
- [LLM 模型切换](docs/llm-switching.md)
- [Docker 部署](docs/docker-deployment.md)
- [API 文档](docs/api.md)
- [Demo 演示数据与说明](demo/README.md)
- [Demo 录制脚本](docs/demo-script.md)
- [Demo 最终验收记录](docs/demo-acceptance.md)
- [Enterprise AI Platform v1.0.0 发布说明](docs/release-v1.0.md)
- [Week 4 总结](docs/week-4-summary.md)
- [版本变更记录](CHANGELOG.md)
- [Dify 基础与首个 AI 应用](docs/dify-basics.md)
- [Dify 接入 Knowledge Hub](docs/dify-knowledge-hub.md)
- [Dify Workflow 基础与企业咨询分流](docs/dify-workflow-basics.md)
- [Dify 企业客服场景](docs/dify-customer-service-scenario.md)
- [Dify 企业场景 Prompt 优化](docs/dify-enterprise-prompt-optimization.md)
- [FastAPI 调用 Dify 工作流](docs/dify-fastapi-integration.md)
- [Week 5 总结：AI 客服助手 v1.0](docs/week-5-summary.md)

## 技术栈

- Python
- FastAPI
- Ruff
- Docker
- Dify
- SQL
- LLM API
- RAG
- LangGraph
- MCP

## API 接口

| 请求方法 | 地址 | 作用 |
| --- | --- | --- |
| GET | `/health` | 检查服务运行状态 |
| POST | `/chat` | 发送聊天消息 |
| POST | `/dify/workflow` | 调用 Dify 企业咨询工作流 |
| POST | `/upload` | 上传并解析 PDF、DOCX 或 Markdown 文档 |
| POST | `/rag/query` | 检索与问题相关的文档 Chunk |
| POST | `/rag/answer` | 根据知识库生成带来源的回答 |
| POST | `/retrieval` | 为 Dify 提供外部知识库检索 |

## 开发状态

Week 4 产品化阶段进度：

- Day 22：多文档自动索引
- Day 23：RAG 检索参数优化
- Day 24：DeepSeek 和通义千问模型切换
- Day 25：Docker 部署和容器级验收
- Day 26：完善 OpenAPI 与 API 使用文档
- Day 27：已准备 Demo 数据、跨文档问题和录制脚本，视频录制暂缓
- Day 28：已完成 Knowledge Hub v1.0.0 发布候选版本准备与验收

当前代码、文档和 Demo 已完成 v1.0.0 最终验收。自动化测试、Ruff、Docker、OpenAPI 和 FastAPI / Dify 双向真实接口均已通过，正式版本使用 `v1.0.0` Git 标签标记。

Demo 视频作为独立交付资产保存，不直接纳入 Git 仓库；详细验收结果见 [Demo 最终验收记录](docs/demo-acceptance.md)。GitHub Release 可在需要公开发布时基于 `v1.0.0` 标签创建。

### Week 5：企业工作流中心

- Day 29：完成 Dify 1.16.1 部署、通义千问配置和首个聊天应用发布
- Day 30：完成 Dify 外部知识库接口、API Key 鉴权以及企业客服助手知识库接入
- Day 31：完成企业咨询分流工作流、条件与 HTTP 节点、变量聚合以及四类场景验收
- Day 32：完成企业客服知识检索、知识约束回答、模糊问题处理和日志留痕
- Day 33：完成企业场景 Prompt 的角色定义、输出格式、事实边界和越权防护优化
- Day 34：完成 FastAPI 调用 Dify Workflow API、服务端密钥配置和真实接口验收
- Day 35：完成 Week 5 总结、质量验收和 AI 客服助手 v1.0 能力整理

Week 5 产出：AI 客服助手 v1.0，已完成问题分流、知识检索、受约束回答、日志追踪和 FastAPI / Dify 双向 API 集成。
