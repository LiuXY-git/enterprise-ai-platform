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
docker compose up --build
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

## 技术栈

- Python
- FastAPI
- Ruff
- Docker
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
| POST | `/upload` | 上传并解析 PDF、DOCX 或 Markdown 文档 |
| POST | `/rag/query` | 检索与问题相关的文档 Chunk |
| POST | `/rag/answer` | 根据知识库生成带来源的回答 |

## 开发状态

已完成 Week 3：RAG v1 闭环，当前版本为 v0.3.0。

系统已经支持文档切分、Embedding、Chroma 检索、受约束回答和来源引用。

下一阶段进入 Week 4：Knowledge Hub 产品化。
