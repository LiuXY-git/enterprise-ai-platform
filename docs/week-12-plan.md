# Week 12：Agent 企业化

按照 16 周路线，本周以“回放日志 + 人工门禁”为学习方法，逐步补齐日志、错误恢复、HITL、复杂任务测试、Prompt 优化和 Demo。目标是学习生产系统需要的控制机制，每项能力仍按实际验证范围说明。

起点：Agent Center v0.5.0 于 2026-09-24 正式定版，提交 `583ecd073e1e45aa6f29a7ef822f02cbbb094153`，维护者已提供 [Release 页面](https://github.com/LiuXY-git/enterprise-ai-platform/releases/tag/agent-center-v0.5.0) 和 `verification.json` 附件截图确认。该版本是宿主机 CLI 独立实验集合，Memory、MCP、Planning 尚未自动串联。

| 日期 | 原路线目标 | 当前范围与状态 |
| --- | --- | --- |
| Day 78 | 增加任务日志 | [已实现](day78-task-logging.md)：现有 MCP 查询的持久化事件、失败记录和只读回放 |
| Day 79 | 增加错误恢复 | [已实现](day79-error-recovery.md)：固定只读工具与模型的有限重试、有效回执模板降级、失败停止；424 项离线测试通过 |
| Day 80 | Human in the Loop | [已实现](day80-human-in-the-loop.md)：持久化审批、内容绑定、过期/拒绝、原子本地模拟执行；479 项离线测试通过 |
| Day 81 | 测试复杂业务任务 | [已验收](day81-complex-business-tests.md)：15 个销售全流程场景；39 项新增与 479 项既有回归共 518 项测试通过 |
| Day 82 | 优化 Agent Prompt | [已实现候选与离线验收](day82-prompt-optimization.md)：16 样例双版本回放、9 个新版集成组合，60 项新增与 518 项回归通过；真实模型质量改善尚未测量 |
| Day 83 | 制作 Agent Demo | [讲稿和命令已准备](day83-agent-demo.md)；2026-09-28 按维护者要求先推进后续，视频与观看验收待补录 |
| Day 84 | 总结与发布 v1.0 | [v1.0 候选准备](day84-agent-v1-release.md)：721 项离线验收要求；正式定版、合并推送、标签/Release 后续独立执行 |

每日增加的代码使用独立目录或明确扩展点，保留 v0.5 冻结资产；后续集成要有独立证据。Day 55 视频、Workflow Center v1.0 Release 和企业微信真实发送仍是独立待办。
