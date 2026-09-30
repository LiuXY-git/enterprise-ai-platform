# 文档目录

首次使用看[平台使用指南](user-guide.md)，理解服务关系看[系统架构](architecture.md)，开发接口看[API 文档](api.md)和[后端说明](../backend/README.md)。

## 按周阅读

Week 7–14 的 `week-*-notes.md` 按天收录完整内容，包含操作步骤、代码命令、验证结果与限制。从下表选择周次，再按各周目录跳转到当天章节。

| 周次 | 阅读入口 | 覆盖内容 | 计划与总结 |
| --- | --- | --- | --- |
| Week 1 | [阶段总结](week-1-summary.md) | 沿用既有周记录 | — |
| Week 2 | [阶段总结](week-2-summary.md) | 沿用既有周记录 | — |
| Week 3 | [阶段总结](week-3-summary.md) | 沿用既有周记录 | — |
| Week 4 | [阶段总结](week-4-summary.md) | 沿用既有周记录 | — |
| Week 5 | [阶段总结](week-5-summary.md) | 沿用既有周记录 | — |
| Week 6 | [阶段总结](week-6-summary.md) | 沿用既有周记录 | — |
| Week 7 | [企业平台集成与销售流程验收](week-7-notes.md) | Day 48–49 | [总结](week-7-summary.md) |
| Week 8 | [工作流整理、配置与部署](week-8-notes.md) | Day 50–55 | [总结](week-8-summary.md) |
| Week 9 | [Agent 基础与状态管理](week-9-notes.md) | Day 57–63 | [计划](week-9-plan.md) · [总结](week-9-summary.md) |
| Week 10 | [Function Calling 与多工具调用](week-10-notes.md) | Day 64–70 | [计划](week-10-plan.md) · [总结](week-10-summary.md) |
| Week 11 | [MCP、Memory 与 Planning](week-11-notes.md) | Day 71–77，含 Day 75 草案与实现 | [计划](week-11-plan.md) · [总结](week-11-summary.md) |
| Week 12 | [Agent 企业化与人工确认](week-12-notes.md) | Day 78–84 | [计划](week-12-plan.md) · [总结](week-12-summary.md) |
| Week 13 | [Agent 评测框架](week-13-notes.md) | Day 85–91 | [计划](week-13-plan.md) · [总结](week-13-summary.md) |
| Week 14 | [企业生产化优化](week-14-notes.md) | Day 92 | [计划](week-14-plan.md) |

Week 7/8 的收录范围见表格，其他日期可查看对应周总结；Week 14 目前仅完成 Day 92。原计划和总结保留各阶段的历史状态，最新发布进度以[项目首页](../README.md)为准。

后续学习内容直接追加到当周 `week-*-notes.md`，并更新该文件的目录。

## 专题与操作入口

### 项目设计

- [系统架构](architecture.md)
- [技术选型](tech-stack.md)
- [数据库设计](database.md)

### API 接口

- [API 文档](api.md)

### 文档接入与 RAG

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

### 部署与运行

- [Docker 部署](docker-deployment.md)

### 工作流中心

- [客服、邮件、销售模板目录](../n8n/templates/README.md)
- [Dify 基础与首个 AI 应用](dify-basics.md)
- [Dify 接入 Knowledge Hub](dify-knowledge-hub.md)
- [Dify Workflow 基础与企业咨询分流](dify-workflow-basics.md)
- [Dify 企业客服场景](dify-customer-service-scenario.md)
- [Dify 企业场景 Prompt 优化](dify-enterprise-prompt-optimization.md)
- [FastAPI 调用 Dify 工作流](dify-fastapi-integration.md)
- [n8n 基础与本地部署](n8n-foundation.md)
- [n8n Webhook 触发与请求响应](n8n-webhook-trigger.md)
- [n8n 连接 AI 工作流](n8n-ai-integration.md)
- [n8n AI 邮件助手](n8n-ai-email-assistant.md)
- [n8n AI 工作流日报](n8n-daily-workflow-report.md)
- [n8n 工作流数据库持久化](n8n-workflow-persistence.md)

### 企业协作平台集成

- [飞书开放平台接入基础](feishu-open-platform.md)
- [企业微信自建应用通知](wecom-notifications.md)

### 销售线索跟进助手

- [销售线索跟进助手设计](sales-followup-design.md)
- [销售线索跟进助手验收方案](sales-followup-acceptance.md)
- [n8n 销售线索跟进助手](n8n-sales-followup-assistant.md)
- [销售线索跟进助手验收样例](../demo/sales-followup-cases.json)

### 演示与验收

- [Day 55 录制验收表](../demo/day55-recording-checklist.md)
- [Day 55 演示工具](../scripts/day55/README.md)
- [Demo 演示数据与说明](../demo/README.md)
- [Demo 录制脚本](demo-script.md)
- [Demo 最终验收记录](demo-acceptance.md)
- [Day 49 可重复验收脚本](../scripts/day49/README.md)

### 版本与发布

- [Agent Center v0.1.0 版本说明](agent-center-v0.1.md)
- [Agent Center v0.1.0 版本清单](../agent-center/release-v0.1.0.json)
- [Workflow Center v1.0.0 发布候选说明](workflow-center-v1.0.md)
- [Workflow Center v1.0.0 候选清单](../n8n/workflow-center-v1.0.0.json)
- [Knowledge Hub v1.0.0 发布说明](release-v1.0.md)
- [Workflow Center v0.1.0 发布说明](workflow-center-v0.1.md)
- [Workflow Center v0.5.0 发布说明](workflow-center-v0.5.md)
- [Workflow Center v0.5.0 短演示讲解稿](workflow-center-v0.5-demo.md)
- [版本变更记录](../CHANGELOG.md)

### Agent 与 Evaluation

- [Agent Center](../agent-center/README.md)：独立实验、操作说明与版本入口。
- [Evaluation Center](../evaluation-center/README.md)：固定测试集、自动执行与评分入口。
- [测试运行说明](../tests/README.md)：后端与独立实验的环境划分。
- [Evaluation Center v0.1 版本说明](evaluation-center-v0.1.md)。
