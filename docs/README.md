# 文档目录

每周一个文件，按学习路线 Day 1–98 编排。周文件内集中计划、每日步骤、专题资料和阶段总结；目前进度为 Day 95，Week 14 尚未完成。

快速使用：[平台使用指南](week-8.md#user-guide) · [当前部署步骤](week-14.md#day93) · [环境变量管理](week-14.md#day94) · [日志排障](week-14.md#day95) · [API 参考](week-4.md#api) · [架构资料](week-1.md#architecture) · [Day 92 后端目录](week-14.md#day92)。

专题资料按首次引入的周次归档，并标注后续修订范围。历史记录中的成功率、版本与限制只适用于相应阶段；计划不是已完成功能。

## 按周阅读

| 周次 | 学习范围 | 内容 |
| --- | --- | --- |
| [Week 1](week-1.md) | Day 1–7 | 项目初始化与 FastAPI 基础 |
| [Week 2](week-2.md) | Day 8–14 | Knowledge Hub 文档接入 |
| [Week 3](week-3.md) | Day 15–21 | RAG：切分、向量检索与来源回答 |
| [Week 4](week-4.md) | Day 22–28 | Knowledge Hub 产品化 |
| [Week 5](week-5.md) | Day 29–35 | Dify 企业客服工作流 |
| [Week 6](week-6.md) | Day 36–42 | n8n 自动化与工作流持久化 |
| [Week 7](week-7.md) | Day 43–49 | 企业协作集成与销售跟进 |
| [Week 8](week-8.md) | Day 50–56 | 工作流整理、配置与部署 |
| [Week 9](week-9.md) | Day 57–63 | Agent 基础与状态管理 |
| [Week 10](week-10.md) | Day 64–70 | Function Calling 与多工具调用 |
| [Week 11](week-11.md) | Day 71–77 | MCP、Memory 与 Planning |
| [Week 12](week-12.md) | Day 78–84 | Agent 企业化与人工确认 |
| [Week 13](week-13.md) | Day 85–91 | Agent 评测框架 |
| [Week 14](week-14.md) | Day 92–98 | 企业生产化优化；Day 92 重构、Day 93 Compose 部署、Day 94 环境变量管理、Day 95 日志追踪 |

## 专题与操作入口

| 查找内容 | 阅读位置 |
| --- | --- |
| 使用、配置与部署 | [使用指南](week-8.md#user-guide) · [配置中心](week-8.md#day52) · [环境文件管理](week-14.md#day94) · [启动与检查](week-14.md#day93) |
| 架构、技术与数据库 | [系统架构](week-1.md#architecture) · [技术选型](week-1.md#tech-stack) · [SQLite 表结构](week-2.md#database) · [后端重构](week-14.md#day92) |
| API | [接口参考](week-4.md#api) · [后端说明](../backend/README.md) |
| 知识库与 RAG | [Week 3](week-3.md) · [黄金问题](week-3.md#rag-golden-questions) · [检索优化](week-4.md#retrieval-optimization) |
| Dify 与 n8n | [Dify 工作流](week-5.md) · [n8n 部署和自动化](week-6.md) · [模板目录](../n8n/templates/README.md) |
| 企业协作与销售 | [飞书](week-7.md#feishu-open-platform) · [企业微信](week-7.md#wecom-notifications) · [销售设计](week-7.md#sales-followup-design) · [验收方案](week-7.md#sales-followup-acceptance) |
| Agent 基础与工具 | [LangGraph](week-9.md#day58) · [状态恢复](week-9.md#day60) · [Function Calling](week-10.md#day64) · [多工具组合](week-10.md#day68) |
| MCP、记忆与人工确认 | [MCP 调用](week-11.md#day73) · [会话记忆](week-11.md#day75) · [人工确认](week-12.md#day80) · [Agent 入口](../agent-center/README.md) |
| 日志与排障 | [请求追踪与 ELK 学习](week-14.md#day95) · [隔离日志验收](../scripts/verify_logging.py) |
| 评测与测试 | [评测学习记录](week-13.md) · [运行评测](../evaluation-center/README.md#运行评测) · [测试说明](../tests/README.md) |
| 演示 | [Knowledge Hub 讲稿](week-4.md#demo-script) · [Day 55 操作稿](week-8.md#day55) · [Day 83 演示材料](week-12.md#day83) |
| 版本说明 | [Knowledge Hub](week-4.md#release-v1.0) · [Workflow v0.1](week-6.md#workflow-center-v0.1) · [Workflow v0.5](week-7.md#workflow-center-v0.5) · [Workflow v1.0 候选](week-8.md#workflow-center-v1.0) |
| Agent / Evaluation 版本 | [Agent v0.1](week-9.md#agent-center-v0.1) · [v0.2](week-10.md#agent-center-v0.2) · [v0.5](week-11.md#agent-center-v0.5) · [v1.0](week-12.md#agent-center-v1.0) · [Evaluation v0.1](week-13.md#evaluation-center-v0.1) |

## 结果与资料维护

- 测试结果看 [每周结果摘要](evidence/README.md)，原始记录保留在对应周数据包中。
- 后续内容追加到 `week-N.md` 的对应 Day 或专题章节，并更新本周目录；不再新增独立 Day、plan、notes、summary 文件。
- 修改章节标题时保留显式锚点，避免已有链接失效。不同专题保留独立锚点，即使标题相同也能准确跳转。
- 先前已导入 Chroma 的文档和来源不会随文件改名自动更新。需比较新文档的检索效果时重新建立对应索引；本次整理不修改已有向量库。
- 原来的检索成绩和输出仍作为阶段记录保留；当前黄金问题和实验读取路径已经使用 Week 文件。
