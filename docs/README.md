# Documentation

该目录用于存放 Enterprise AI Platform 项目文档。

## 从这里开始

- 首次启动与日常操作：[平台使用指南](user-guide.md)。
- 理解调用关系与数据存放：[系统架构](architecture.md)、[技术选型](tech-stack.md)。
- 导入业务流程：[客服、邮件、销售模板目录](../n8n/templates/README.md)。
- 核对接口或开发后端：[API 文档](api.md)、[后端说明](../backend/README.md)。
- 本次文档交付范围与验证：[Day 54 使用与架构文档](day54-documentation.md)。
- Week 8 阶段交付：[Week 8 总结](week-8-summary.md)、[Workflow Center v1.0.0 发布候选](workflow-center-v1.0.md)；Day 55 视频已安排延期补录。
- Week 9 学习入口：[Day 57 架构](day57-agent-architecture.md)、[Day 58 状态图](day58-langgraph-basics.md)、[Day 59 模型规划](day59-task-planner.md)、[Day 60 状态保存](day60-task-state.md)、[Day 61 销售场景](day61-sales-agent-scenario.md)、[Day 62 Prompt](day62-agent-prompt.md)、[实施计划](week-9-plan.md)；已验证 Qwen 规划与模拟进度持久化，真实业务工具执行待实施。

以使用指南和架构页了解功能状态；各 Day、Week 文档保留对应阶段的实施和验收记录。API `1.0.0`、Workflow Center 已发布基线 `0.5.0` 和待发布目标 `1.0.0` 分别记录，候选文档不等于线上新版本已经发布。

## 项目设计

- [系统架构](architecture.md)
- [技术选型](tech-stack.md)
- [数据库设计](database.md)

## API 接口

- [API 文档](api.md)

## 文档接入与 RAG

- [Embedding 学习笔记](embedding.md)
- [Chunk 文本切分](chunking.md)
- [Chroma 向量数据库](vector-database.md)
- [文档 Embedding 流程](document-embedding.md)
- [RAG Query 检索](rag-query.md)
- [RAG Prompt 与来源引用](rag-prompt.md)
- [RAG 黄金问题集](rag-golden-questions.md)
- [多文档自动索引](multi-document-indexing.md)
- [RAG 检索参数优化](retrieval-optimization.md)
- [LLM 模型切换](llm-switching.md)

## 部署与运行

- [Docker 部署](docker-deployment.md)
- [Day 53 一键启动与持久化验收](day53-compose-deployment.md)
- [Day 52 配置中心与离线自检](day52-configuration-center.md)

## 工作流中心

- [Day 51 工作流日志](day51-workflow-logging.md)
- [Day 50 工作流模板整理](day50-workflow-templates.md)
- [客服、邮件、销售模板目录](../n8n/templates/README.md)
- [Dify 基础与首个 AI 应用](dify-basics.md)
- [Dify 接入 Knowledge Hub](dify-knowledge-hub.md)
- [Dify Workflow 基础与企业咨询分流](dify-workflow-basics.md)
- [Dify 企业客服场景](dify-customer-service-scenario.md)
- [Dify 企业场景 Prompt 优化](dify-enterprise-prompt-optimization.md)
- [FastAPI 调用 Dify 工作流](dify-fastapi-integration.md)
- [Week 5 总结：AI 客服助手 v1.0](week-5-summary.md)
- [n8n 基础与本地部署](n8n-foundation.md)
- [n8n Webhook 触发与请求响应](n8n-webhook-trigger.md)
- [n8n 连接 AI 工作流](n8n-ai-integration.md)
- [n8n AI 邮件助手](n8n-ai-email-assistant.md)
- [n8n AI 工作流日报](n8n-daily-workflow-report.md)
- [n8n 工作流数据库持久化](n8n-workflow-persistence.md)
- [Week 6 总结：Workflow Center v0.1.0](week-6-summary.md)

## Agent Center

- [Day 57 Agent 架构、状态与停止条件](day57-agent-architecture.md)
- [静态任务推演与字段说明](../demo/agent-center/README.md)
- [Day 58 LangGraph State、Node、Edge](day58-langgraph-basics.md)
- [Day 58 可运行实验](../experiments/day58/README.md)
- [Day 59 模型任务规划与结构校验](day59-task-planner.md)
- [Day 59 可运行实验](../experiments/day59/README.md)
- [Day 60 任务状态与重启恢复](day60-task-state.md)
- [Day 60 可运行实验](../experiments/day60/README.md)
- [Day 61 销售跟进分析场景与验收](day61-sales-agent-scenario.md)
- [Day 61 可运行契约检查](../experiments/day61/README.md)
- [Day 62 Agent Prompt 与模型输出验收](day62-agent-prompt.md)
- [Day 62 可运行入口](../experiments/day62/README.md)
- [Week 9：Agent 基础计划](week-9-plan.md)

Day 58 验证独立状态图与模拟节点；Day 59 验证当前 Qwen 模型的规划和澄清。Day 60 已验证 SQLite 检查点、模拟步骤进度与独立进程恢复；Day 61 已完成销售跟进场景和固定规则验收；Day 62 已验证 Qwen 依据虚构快照生成报告并通过证据核对。真实业务工具执行尚未验收。

## 企业协作平台集成

- [飞书开放平台接入基础](feishu-open-platform.md)
- [企业微信自建应用通知](wecom-notifications.md)

## 销售线索跟进助手

- [销售线索跟进助手设计](sales-followup-design.md)
- [销售线索跟进助手验收方案](sales-followup-acceptance.md)
- [n8n 销售线索跟进助手](n8n-sales-followup-assistant.md)
- [销售线索跟进助手验收样例](../demo/sales-followup-cases.json)

## 演示与验收

- [Day 55 业务 Demo：执行步骤与录制讲稿](day55-workflow-demo.md)
- [Day 55 录制验收表](../demo/day55-recording-checklist.md)
- [Day 55 演示工具](../scripts/day55/README.md)
- [Demo 演示数据与说明](../demo/README.md)
- [Demo 录制脚本](demo-script.md)
- [Demo 最终验收记录](demo-acceptance.md)
- [Day 48 故障恢复验收记录](day48-failure-recovery-results.md)
- [Day 49 发布验收记录](day49-release-acceptance.md)
- [Day 49 可重复验收脚本](../scripts/day49/README.md)

## 版本与发布

- [Workflow Center v1.0.0 发布候选说明](workflow-center-v1.0.md)
- [Workflow Center v1.0.0 候选清单](../n8n/workflow-center-v1.0.0.json)
- [Knowledge Hub v1.0.0 发布说明](release-v1.0.md)
- [Workflow Center v0.1.0 发布说明](workflow-center-v0.1.md)
- [Workflow Center v0.5.0 发布说明](workflow-center-v0.5.md)
- [Workflow Center v0.5.0 短演示讲解稿](workflow-center-v0.5-demo.md)
- [版本变更记录](../CHANGELOG.md)

## 阶段总结

- [Week 1 总结](week-1-summary.md)
- [Week 2 总结](week-2-summary.md)
- [Week 3 总结](week-3-summary.md)
- [Week 4 总结](week-4-summary.md)
- [Week 7 总结](week-7-summary.md)
- [Week 8 总结](week-8-summary.md)
