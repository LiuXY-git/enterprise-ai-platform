# Enterprise AI Platform

一个面向企业场景的 AI 平台学习项目。

当前平台 API 版本为 `1.0.0`。Workflow Center `0.5.0` 已完成业务验收，版本内容于 2026-09-14 定版，组件标签为 `workflow-center-v0.5.0`。GitHub 发布状态以远端标签和 Release 页面为准。销售助手通知为预览模式。

Day 55–56 成果已合并到 `main`；[Workflow Center v1.0.0](docs/workflow-center-v1.0.md)仍为发布候选，标签与 GitHub Release 待发布。维护者于 2026-09-17 确认 Day 55 视频之后补录。Week 9 已完成 [Day 58 LangGraph 实验](docs/day58-langgraph-basics.md)和 [Day 59 任务规划 Agent](docs/day59-task-planner.md)：模型生成计划，本地校验，业务步骤尚未执行。[Day 60](docs/day60-task-state.md)已加入 SQLite 任务检查点，支持模拟进度保存和进程重启恢复。[Day 61](docs/day61-sales-agent-scenario.md)已完成销售跟进分析场景、输入输出契约与离线规则验收。[Day 62](docs/day62-agent-prompt.md)已加入销售报告 Prompt、模型输出核对，并通过 5 个 Qwen 真实请求验证。[Day 63](docs/day63-agent-center-release.md)成果已合并到 main；[Agent Center v0.1.0](docs/agent-center-v0.1.md)于 2026-09-21 完成内容定版，维护者已提供 [GitHub Release](https://github.com/LiuXY-git/enterprise-ai-platform/releases/tag/agent-center-v0.1.0) 页面截图确认正式发布。

[Week 10](docs/week-10-plan.md)开始学习 Tool Calling。[Day 64](docs/day64-function-calling.md)已完成工具 schema、严格参数校验与本地金额纯函数的调用闭环，通过 141 项测试、3 个离线 fixture 和单个虚构订单的 Qwen 真实复验；首次真实失败保留记录，离线与真实证据分别计数。[Day 65](docs/day65-sql-tool.md)已实现只读 SQL Tool，通过 96 项新增测试及两个 Qwen 虚构查询场景；[Day 66](docs/day66-knowledge-tool.md)已接入 Knowledge Hub 检索与引用校验，通过 120 项新增测试及两个 Qwen 虚构知识库场景；[Day 67](docs/day67-api-tool.md)已完成天气 API Tool，包含固定接口、响应校验、错误处理和两个真实 Qwen 天气查询场景。[Day 68](docs/day68-multi-tool.md)已组合 SQL、知识库、天气三个工具，支持条件分支、部分完成和跨工具引用，完成一次真实 Qwen 全链路验收。[Day 69](docs/day69-complex-task-tests.md)已完成 18 个复杂场景验收、独立会话重跑验证及确定性简报，补齐虚构背景、来源和未完成项。[Day 70](docs/day70-agent-v02-release.md)已完成 Agent Center v0.2.0 发布准备；2026-09-24 正式定版，维护者已提供 [GitHub Release](https://github.com/LiuXY-git/enterprise-ai-platform/releases/tag/agent-center-v0.2.0) 截图确认。旧版候选文档保留为历史记录。

[Week 11](docs/week-11-plan.md)进入 MCP 与高级 Agent。[Day 71](docs/day71-mcp-basics.md)完成概念学习；[Day 72](docs/day72-mcp-server.md)将虚构销售查询包装为 MCP Server，通过 99 项测试和两个独立客户端验证。[Day 73](docs/day73-agent-mcp.md)已完成 Agent 通过 MCP 查询与结果回填：319 项离线测试通过、两组真实 Qwen 场景通过；复刻入口见 [Day 73 实验说明](experiments/day73/README.md)。

[Day 74](docs/day74-agent-memory.md)提供 Agent Memory 学习材料与代码阅读练习，区分会话上下文、长期记忆和任务检查点；[Day 75 Conversation Memory](docs/day75-conversation-memory.md)已实现 SQLite 会话保存、跨进程恢复、部门更新与清除；191 项离线测试通过，真实 Qwen 两次模板调用通过，[复刻入口](experiments/day75/README.md)。

[Day 76](docs/day76-planning.md)提供 Planning 学习材料，以季度销售分析说明任务拆解、依赖与完成标准；复用 Day 59 做离线观察，尚未把 Memory、MCP 与季度计划自动集成。[操作入口](experiments/day76/README.md)。

[Day 77](docs/day77-agent-v05-release.md)汇总 MCP、独立会话记忆与 Planning 学习成果；Agent Center v0.5.0 于 2026-09-24 正式定版，456 项离线验收全部通过。维护者已提供 [GitHub Release](https://github.com/LiuXY-git/enterprise-ai-platform/releases/tag/agent-center-v0.5.0) 页面和验收附件截图确认发布，旧版候选文档保留为历史记录。

[Week 12](docs/week-12-plan.md)开始学习 Agent 企业化。[Day 78](docs/day78-task-logging.md)为现有 MCP 查询增加 SQLite 任务日志：请求、决策、调用、结果和最终回答逐条保存，可按任务编号跨进程查看；[操作入口](experiments/day78/README.md)。

首次使用请从 [平台使用指南](docs/user-guide.md) 开始；理解服务关系请看 [系统架构](docs/architecture.md)，完整导航见 [文档目录](docs/README.md)。

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
- [x] 完成 n8n 2.36.8 本地部署、最小工作流导出和持久化验收
- [x] 完成 n8n Webhook 测试与生产触发、请求字段整理和 JSON 响应闭环
- [x] 完成 n8n 调用 FastAPI/Dify AI 工作流、响应整理和测试与生产验收
- [x] 完成 n8n AI 邮件分类、人工复核分支和低风险回复草稿生成
- [x] 完成 n8n 原生 LLM 日报统计、无数据防幻觉约束和日期校验
- [x] 完成 n8n 工作流运行持久化、幂等拦截、失败记录和回放
- [x] 发布 Workflow Center v0.1.0
- [x] 完成 Day 43 飞书开放平台基础接入（Bot、Webhook、API 与应用鉴权）
- [x] 完成 Day 44 飞书机器人文本消息发送与真实联调
- [x] 完成 Day 45 企业微信通知本地实现、Mock 测试与 Docker 接口验收
- [ ] 完成 Day 45 企业微信真实发送（等待符合后台要求的可管理域名）
- [x] 完成 Day 46 销售线索跟进助手业务流程、数据契约、CRM 草案和验收方案设计
- [x] 完成 Day 47 模拟 CRM、销售工作流与通知预览
- [x] 完成 Day 48 AI/CRM 故障分类、检查点恢复与通知状态保护
- [x] 完成 Day 49 发布清单、可重复验收、文档和 Week 7 总结
- [x] 发布 Workflow Center v0.5.0（GitHub Release 已确认）
- [x] 完成 Day 50 客服、邮件、销售工作流模板整理
- [x] 实现 Day 51 工作流结构化事件日志、输入输出快照与用量来源标记
- [x] 完成 Day 52 统一配置入口、按需校验与离线脱敏自检
- [x] 完成 Day 53 一键启动、部署检查、日志轮转与隔离容器重建验收
- [x] 完成 Day 54 使用指南、系统架构与文档导航整理
- [x] 准备 Day 55 业务 Demo 讲稿、请求包与逐步执行工具
- [ ] 完成 Day 55 本轮真实业务演示、视频录制与验收（已确认延期补录）
- [x] 完成 Day 56 Week 8 总结与 Workflow Center v1.0.0 发布候选准备
- [ ] 完成 Workflow Center v1.0.0 标签与 GitHub Release 发布
- [x] 完成 Day 57 Agent 架构、任务生命周期与静态推演设计
- [x] 完成 Day 58 LangGraph State、Node、Edge 最小实验与模拟分支验证
- [x] 完成 Day 59 模型任务规划、结构校验与 Qwen 真实适配验证
- [x] 完成 Day 60 SQLite 任务状态、模拟进度保存与异常退出恢复
- [x] 完成 Day 61 销售跟进分析场景、数据契约与虚构样例校验
- [x] 完成 Day 62 销售 Agent Prompt、输出证据校验与 Qwen 虚构场景真实验证
- [x] 完成 Day 63 Agent Center v0.1.0 候选清单、离线验收与 Week 9 总结
- [x] 完成 Agent Center v0.1.0 组件标签与 GitHub Release 发布（维护者已提供页面截图确认）
- [x] 完成 Day 64 Function Calling 最小闭环、离线验收与 Qwen 单个虚构订单真实验证
- [x] 完成 Day 65 只读 SQL Tool、数据库保护与独立验收
- [x] 完成 Day 66 Knowledge Tool、来源引用校验与虚构知识库真实检索验收
- [x] 完成 Day 67 天气 API Tool、受控 HTTP 请求与真实模型调用验收
- [x] 完成 Day 68 多工具组合、执行预算、状态与引用关联验收
- [x] 完成 Day 69 复杂任务测试、失败恢复边界与稳定简报验收
- [x] 完成 Day 70 Agent Center v0.2.0 候选清单、复刻入口与离线发布验收
- [x] 完成 Agent Center v0.2.0 正式定版、组件标签与 GitHub Release 发布（维护者截图确认）
- [x] 完成 Day 71 MCP 概念学习与职责边界讨论
- [x] 完成 Day 72 首个 MCP Server、只读 SQL 工具与真实 stdio 双客户端验证
- [x] 完成 Day 73 Agent 接入 MCP、回执与报告校验及真实模型验证

模板入口：[客服、邮件与销售模板目录](n8n/templates/README.md)。
日志说明：[Day 51 工作流日志](docs/day51-workflow-logging.md)。
配置说明：[Day 52 配置中心与离线自检](docs/day52-configuration-center.md)。
部署说明：[Day 53 一键启动与持久化验收](docs/day53-compose-deployment.md)。
文档交付：[Day 54 使用与架构文档](docs/day54-documentation.md)。
演示准备：[Day 55 业务 Demo](docs/day55-workflow-demo.md)；视频与现场业务结果延期补齐。
阶段交付：[Week 8 总结](docs/week-8-summary.md)、[Workflow Center v1.0.0 候选说明](docs/workflow-center-v1.0.md)。
Agent 起点：[Day 57 架构](docs/day57-agent-architecture.md)、[静态推演](demo/agent-center/README.md)、[Week 9 计划](docs/week-9-plan.md)。
状态图实验：[Day 58 说明与运行命令](docs/day58-langgraph-basics.md)、[实验代码](experiments/day58/README.md)。
模型规划：[Day 59 说明与运行命令](docs/day59-task-planner.md)、[规划实验代码](experiments/day59/README.md)。
任务状态：[Day 60 保存与恢复操作](docs/day60-task-state.md)、[持久化实验代码](experiments/day60/README.md)。
业务场景：[Day 61 销售跟进分析设计](docs/day61-sales-agent-scenario.md)、[契约与样例代码](experiments/day61/README.md)。
Agent Prompt：[Day 62 提示词与模型验证](docs/day62-agent-prompt.md)、[运行入口](experiments/day62/README.md)。
Week 9 交付：[Agent Center 入口](agent-center/README.md)、[v0.1 版本说明](docs/agent-center-v0.1.md)、[Week 9 总结](docs/week-9-summary.md)。
工具调用：[Week 10 计划](docs/week-10-plan.md)、[Day 64 操作流程](docs/day64-function-calling.md)、[实验入口](experiments/day64/README.md)。
SQL 工具：[Day 65 只读查询](docs/day65-sql-tool.md)、[运行入口](experiments/day65/README.md)；已通过虚构销售数据的离线与 Qwen 真实查询验收。
知识工具：[Day 66 检索与引用](docs/day66-knowledge-tool.md)、[运行入口](experiments/day66/README.md)；支持 fixture、隔离的真实向量检索与 Qwen 闭环。
API 工具：[Day 67 天气查询](docs/day67-api-tool.md)、[运行入口](experiments/day67/README.md)；支持三个预设城市、1–3 天预报及异常停止。
工具组合：[Day 68 多工具简报](docs/day68-multi-tool.md)、[运行入口](experiments/day68/README.md)；整合 SQL、知识库、天气，保留结果来源和部分完成状态。
复杂验收：[Day 69 场景与恢复边界](docs/day69-complex-task-tests.md)、[运行入口](experiments/day69/README.md)；18 个场景与回执生成的完整说明。

## 项目结构

```text
enterprise-ai-platform/
├── backend/     # Python 和 FastAPI 后端
├── docs/        # 架构、学习和接口文档
├── docker/      # Docker 配置
├── n8n/
│   └── workflows/  # 纳入版本控制的 n8n 工作流
├── tests/       # 自动化测试
└── README.md
```

## 快速启动

以下命令在仓库根目录执行。首次配置 `.env`、Python 环境及 n8n 凭据，请先阅读 [使用指南](docs/user-guide.md)。Docker API 与本地 API 默认使用同一端口，选择一种运行方式。

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
& .\scripts\start.ps1
```

Docker 启动后的服务地址：

```text
FastAPI 文档：http://127.0.0.1:8000/docs
n8n 编辑器：http://127.0.0.1:5678
```

日常停止服务：

```powershell
docker compose stop
```

## 项目文档

- [平台使用指南](docs/user-guide.md)
- [Day 54 使用与架构文档](docs/day54-documentation.md)
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
- [n8n 基础与本地部署](docs/n8n-foundation.md)
- [n8n Webhook 触发与请求响应](docs/n8n-webhook-trigger.md)
- [n8n 连接 AI 工作流](docs/n8n-ai-integration.md)
- [n8n AI 邮件助手](docs/n8n-ai-email-assistant.md)
- [n8n AI 工作流日报](docs/n8n-daily-workflow-report.md)
- [n8n 工作流数据库持久化](docs/n8n-workflow-persistence.md)
- [Workflow Center v0.1.0 发布说明](docs/workflow-center-v0.1.md)
- [Week 6 总结：Workflow Center v0.1.0](docs/week-6-summary.md)
- [飞书开放平台接入基础](docs/feishu-open-platform.md)
- [企业微信自建应用通知](docs/wecom-notifications.md)
- [销售线索跟进助手设计](docs/sales-followup-design.md)
- [销售线索跟进助手验收方案](docs/sales-followup-acceptance.md)
- [n8n 销售线索跟进助手](docs/n8n-sales-followup-assistant.md)
- [Workflow Center v0.5.0 发布说明](docs/workflow-center-v0.5.md)
- [Day 49 发布验收记录](docs/day49-release-acceptance.md)
- [Week 7 总结](docs/week-7-summary.md)

## 技术栈

- Python
- FastAPI
- Ruff
- Docker
- n8n
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
| POST | `/workflow-runs/start` | 登记工作流运行、拦截重复事件或开始失败回放 |
| PATCH | `/workflow-runs/{run_id}/result` | 保存工作流成功或人工审核结果 |
| PATCH | `/workflow-runs/executions/{execution_id}/failure` | 按 n8n 执行号保存失败记录 |
| GET | `/workflow-runs` | 按报告日期查询工作流运行 |
| GET | `/workflow-runs/{run_id}` | 查询单条工作流运行 |
| POST | `/integrations/feishu/messages` | 通过飞书机器人发送文本消息 |
| POST | `/integrations/wecom/messages` | 通过企业微信自建应用发送文本消息 |
| PATCH | `/workflow-runs/{run_id}/checkpoint` | 保存 AI 分析检查点 |
| PATCH | `/workflow-runs/{run_id}/failure` | 按运行 ID 记录阶段失败 |
| GET | `/workflow-runs/{run_id}/recovery` | 查询恢复起点和人工处理要求 |
| PUT | `/crm/customers/{customer_id}` | 新增或更新模拟客户 |
| GET | `/crm/customers/{customer_id}` | 查询客户 |
| POST | `/crm/followups` | 在单一事务中保存客户与跟进记录 |
| GET | `/crm/followups/{followup_id}` | 查询跟进记录 |
| GET | `/crm/customers/{customer_id}/followups` | 查询客户跟进列表 |
| GET | `/crm/workflow-runs/{run_id}/followup` | 按运行查询跟进记录 |
| POST | `/crm/followups/{followup_id}/notification-attempts` | 登记通知尝试，不发送消息 |
| PATCH | `/crm/followups/{followup_id}/notification` | 保存通知结果，不发送消息 |
| PATCH | `/crm/followups/{followup_id}/notification-resolution` | 保存人工核对结果，不发送消息 |

## 开发状态

Week 4 产品化阶段进度：

- Day 22：多文档自动索引
- Day 23：RAG 检索参数优化
- Day 24：DeepSeek 和通义千问模型切换
- Day 25：Docker 部署和容器级验收
- Day 26：完善 OpenAPI 与 API 使用文档
- Day 27：已准备 Demo 数据、跨文档问题和录制脚本，视频录制暂缓
- Day 28：已完成 Knowledge Hub v1.0.0 发布候选版本准备与验收

平台 v1.0.0 历史版本的代码、文档和 Demo 已完成最终验收。自动化测试、Ruff、Docker、OpenAPI 和 FastAPI / Dify 双向真实接口均已通过，正式版本使用 `v1.0.0` Git 标签标记。

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

### Week 6：n8n 工作流自动化

- Day 36：完成 n8n 2.36.8 Docker Compose 部署、健康检查、最小工作流、JSON 导出、安全隔离和命名卷持久化验收
- Day 37：完成 n8n Webhook 测试与生产触发、请求字段标准化、显式 JSON 响应和版本化导出验收
- Day 38：完成 n8n 调用 FastAPI/Dify AI 工作流、请求映射、19 字段响应整理及测试与生产触发验收
- Day 39：完成邮件事件规范化、规则分类、人工复核分支、低风险 AI 回复草稿和 21 字段统一响应验收
- Day 40：完成每日调度与手动回放、指标聚合、原生 LLM 日报生成及正常、无数据和非法日期验收
- Day 41：完成工作流输入输出落库、重复事件拦截、Error Trigger 失败记录和失败回放验收
- Day 42：冻结 Workflow Center v0.1.0 发布范围、清单、文档、安全检查和质量门禁

Day 36 产出：可重复部署的 n8n 基础环境，以及版本化工作流 `n8n/workflows/w6d36-foundation-check.json`。

Day 37 产出：可由外部 HTTP 请求触发的客户请求接入闭环，以及版本化工作流 `n8n/workflows/w6d37-customer-request-webhook.json`。

Day 38 产出：可将客户请求交给真实 AI 工作流处理并返回结构化结果的自动化闭环，以及版本化工作流 `n8n/workflows/w6d38-ai-customer-request.json`。

Day 39 产出：具有明确人机协作边界的 AI 邮件助手，以及版本化工作流 `n8n/workflows/w6d39-ai-email-assistant.json` 和自动化结构测试。

Day 40 产出：使用 n8n 原生 LLM Chain 与通义千问生成受约束运营日报的自动化流程，以及版本化工作流 `n8n/workflows/w6d40-daily-workflow-report.json`、安全配置文档和自动化结构测试。

Day 41 产出：SQLite 工作流运行账本、FastAPI 运行管理接口、可持久化邮件助手和错误处理工作流，以及成功、人工审核、重复、失败和回放场景验收。

Day 42 产出：包含 7 个版本化工作流的 Workflow Center v0.1.0 发布候选、机器可读清单、发布说明、Week 6 总结和自动化发布门禁。

### Week 7：企业平台集成

- Day 43：完成飞书企业自建应用、机器人能力、最小权限、测试范围、应用发布和服务端鉴权接入
- Day 44：完成飞书文本消息模型、发送服务、重试、路由、OpenAPI 和真实测试群联调
- Day 45：完成企业微信自建应用通知的本地实现、Token 缓存、错误语义、Mock 测试和 Docker 接口验收；真实发送等待满足域名准入条件
- Day 46：完成销售线索跟进助手的业务流程、输入与 AI 输出契约、CRM 数据草案、通知状态和 15 个验收场景设计

Day 43 产出：可从环境变量安全读取飞书应用凭证、调用飞书开放平台获取 `tenant_access_token` 的异步服务、成功与异常路径自动化测试，以及 Bot、Webhook 和 API 的职责边界文档。

Day 44 产出：`POST /integrations/feishu/messages`、接收者配置、确定性消息 UUID、受限重试、安全错误信息，以及飞书测试群真实消息验收。

Day 45 产出：`POST /integrations/wecom/messages`、单成员通知契约、进程内 Token 缓存、明确 Token 失效后最多补发一次、`delivery_unknown` 安全语义和完整 Mock 测试。企业微信后台要求先配置符合主体及归属验证条件的域名，当前未满足，因此真实发送保持为待联调项。

Day 46 产出：销售线索跟进助手设计与验收方案，以及覆盖正常处理、重复事件、Prompt 注入、AI 异常、CRM 失败和通知异常的 15 个虚构验收样例。这些设计已在 Day 47 和 Day 48 实现，当前验收结论见 Day 49 发布验收记录。


- Day 47：实现客户与跟进记录、事务写入、运行去重、销售工作流及通知预览。
- Day 48：加入 AI 故障分类、分析检查点、CRM 故障恢复、通知状态与人工核对接口，以及 CRM 保存后的整条回放保护。
- Day 49：将 8 条工作流纳入 v0.5.0 清单，完成新数据回放保护、人工通知核对、Production URL 正常和重复事件验收，整理发布文档。

本周交付范围与限制：飞书独立发送接口已有真实联调；企业微信接口已有 Mock/本地验收，真实发送仍待域名条件满足。销售流程当前固定为 preview，通知异常及人工核对通过本地状态 API 模拟。通知恢复为 sent 不会自动把原 failed 工作流改成 succeeded。

已通过且未受本次改动影响的验收沿用已有证据，不重复执行。后续发布状态、证据及待办统一见 [v0.5.0 发布说明](docs/workflow-center-v0.5.md)。
