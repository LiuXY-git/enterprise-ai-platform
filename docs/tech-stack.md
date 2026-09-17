# 技术选型

本页区分平台已使用技术与后续计划；Day 58 增加独立 LangGraph 实验，平台 API 依赖沿用原配置。系统调用关系见 [架构说明](architecture.md)，操作步骤见 [使用指南](user-guide.md)。

## 已使用

| 技术 | 当前用途 | 实现位置或边界 |
| --- | --- | --- |
| Python、FastAPI、Uvicorn | API 与业务服务 | 当前 Docker 基于 Python 3.14；[后端入口](../backend/app/main.py) |
| Pydantic | 请求、响应及业务数据校验 | [数据模型](../backend/app/models)；各历史模板严格程度不同 |
| SQLite | 文档元数据、运行账本、模拟 CRM | Python 标准库访问；当前单机持久化方案 |
| PyMuPDF、python-docx | PDF 与 DOCX 提取 | Markdown 由本地解析服务处理 |
| Chroma | 本地向量索引、相似度检索 | 默认本地 Embedding；与云端生成模型分开 |
| RAG | 基于知识片段生成带来源回答 | 检索、Prompt 和回答由平台服务实现 |
| OpenAI 兼容客户端 | 调用 DeepSeek 或 Qwen | 客户端协议兼容不表示项目已接入所有模型厂商 |
| Dify | 企业咨询工作流、外部知识库应用 | 独立部署，模型和应用发布由 Dify 管理 |
| n8n | Webhook、条件分支、HTTP 调用和原生模型编排 | Compose 固定 `2.36.8`，流程导出在 [workflows](../n8n/workflows) |
| 飞书、企业微信 HTTP API | 独立消息接口与企业集成 | 飞书有历史真实联调；企业微信真实发送仍待环境条件；销售仅预览 |
| python-dotenv、dataclasses | 显式环境加载与分组配置 | [settings.py](../backend/app/settings.py)，按需校验与脱敏自检 |
| Python logging、JSONL | 应用日志和工作流边界事件 | 文件轮转；没有统一分布式追踪 |
| Docker、Compose、PowerShell | 打包、部署、健康及挂载检查 | [Day 53 说明](day53-compose-deployment.md)；Dify 不由本项目 Compose 管理 |
| pytest、Ruff | 自动化测试与代码检查 | [测试目录](../tests)、[项目配置](../pyproject.toml) |
| Git、GitHub | 版本管理与协作 | 平台 API 和 Workflow Center 的发布范围分别记录 |

Python 依赖以 [requirements.txt](../requirements.txt) 和 [requirements-dev.txt](../requirements-dev.txt) 为准；镜像版本以 [Dockerfile](../docker/Dockerfile) 和 [compose.yaml](../compose.yaml) 为准。本页描述仓库采用的版本，不表示上游最新版本。

## 独立实验

[Day 58](day58-langgraph-basics.md)在独立 Python 3.14.2 环境运行 LangGraph `1.2.11`，使用固定计划与模拟节点。版本快照位于 [实验依赖](../experiments/day58/requirements-lock.txt)。实验 SDK 要求 `websockets < 17`，与 API 的 `17.0.1` 固定版本冲突，因此不合并进根目录依赖，也不加入当前容器。

## 后续候选与待实现模块

| 技术或能力 | 计划方向 | 当前状态 |
| --- | --- | --- |
| PostgreSQL | 数据规模或并发增长后的数据库方案 | 当前业务存储仍为 SQLite，未迁移 |
| Agent Center / LangGraph 集成 | 模型规划、任务状态与工具编排 | Day 58 独立状态图已验证；模型、持久化与平台接入待实施 |
| MCP | 标准化工具与企业系统连接 | 尚未作为本项目业务集成层采用 |
| Evaluation Center | Agent 评测与结果管理 | 尚未形成独立评测平台；现有 pytest 和 RAG 问题集不等同于此模块 |

后续选型需结合具体需求验证，不是当前运行的额外依赖。
