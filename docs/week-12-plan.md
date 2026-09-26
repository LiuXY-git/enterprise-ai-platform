# Week 12：Agent 企业化

按照 16 周路线，本周以“回放日志 + 人工门禁”为学习方法，逐步补齐日志、错误恢复、HITL、复杂任务测试、Prompt 优化和 Demo。目标是学习生产系统需要的控制机制，每项能力仍按实际验证范围说明。

起点：Agent Center v0.5.0 于 2026-09-24 正式定版，提交 `583ecd073e1e45aa6f29a7ef822f02cbbb094153`，维护者已提供 [Release 页面](https://github.com/LiuXY-git/enterprise-ai-platform/releases/tag/agent-center-v0.5.0) 和 `verification.json` 附件截图确认。该版本是宿主机 CLI 独立实验集合，Memory、MCP、Planning 尚未自动串联。

| 日期 | 原路线目标 | 当前范围与状态 |
| --- | --- | --- |
| Day 78 | 增加任务日志 | [已实现](day78-task-logging.md)：现有 MCP 查询的持久化事件、失败记录和只读回放 |
| Day 79 | 增加错误恢复 | 待实施：结合失败类型设计有边界的重试与替代方案 |
| Day 80 | Human in the Loop | 待实施：执行前人工确认及拒绝路径 |
| Day 81 | 测试复杂业务任务 | 待实施：销售场景，覆盖成功与失败分支 |
| Day 82 | 优化 Agent Prompt | 待实施：用可重复样例评估幻觉与错误调用 |
| Day 83 | 制作 Agent Demo | 待实施：完整流程演示与录制 |
| Day 84 | 总结与发布 v1.0 | 待实施：按实际能力验收、形成版本清单并发布 |

每日增加的代码使用独立目录或明确扩展点，保留 v0.5 冻结资产；后续集成要有独立证据。Day 55 视频、Workflow Center v1.0 Release 和企业微信真实发送仍是独立待办。
