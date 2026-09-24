# Week 11 总结：MCP、Memory 与 Planning

原路线目标是 MCP 服务可复用，并理解 Memory 和 Planning 的职责边界。本周成果整理为 [Agent Center v0.5.0 候选](../agent-center/v0.5/README.md)。

| 日期 | 成果 | 验证方式 |
| --- | --- | --- |
| Day 71 | 理解 MCP 的 Host、Client、Server 与职责 | 概念讨论与材料 |
| Day 72 | 将既有虚构 SQL 查询包装为 MCP Server | 官方 SDK、标准库 JSON-RPC 客户端与测试 |
| Day 73 | Agent 通过 MCP 调用工具、回填并核对报告 | 离线测试与 4 次历史 Qwen 请求 |
| Day 74 | 短期/长期记忆、检查点和上下文的区别 | 文档、代码阅读和自测题 |
| Day 75 | SQLite Conversation Memory | 进程恢复、隔离、更新、清除、重放；2 次历史 Qwen 请求 |
| Day 76 | 复杂任务拆解与依赖、完成标准 | 原有规划器离线观察与两份人工计划 |
| Day 77 | 统一入口、版本清单和发布候选验收 | 456 项离线测试要求、历史与旧版资产核验 |

本周新增可运行能力是 MCP 与独立会话记忆。Day 59 的模型规划和 Day 60 的模拟进度恢复继续保留，不能把 Day 76 学习描述成新的自动执行能力。学习材料交付也不等于学习者已经通过所有自测。

用户可以分别复刻“模型 → MCP → 销售回执”和“会话保存 → 新进程恢复 → 模板回答”。尚未完成的包括统一 Memory/MCP/Planning 接口、任意季度分析执行、生产认证、远程 MCP、多用户线上服务以及跨会话长期记忆。

下一周按路线学习任务日志、恢复、人工介入与复杂任务 Demo，具体实施以每日范围为准。Day 55 视频、Workflow Center v1.0 Release 和企业微信真实发送继续单独跟踪。
