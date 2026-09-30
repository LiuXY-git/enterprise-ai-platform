# Week 11 MCP 与高级 Agent

本周按原 16 周路线采用“协议最小实现 + 跨客户端验证”，逐步学习 MCP、Memory 和 Planning。MCP 处理应用与工具服务通信；Memory 保存可使用的上下文；Planning 形成步骤；流程执行和权限检查另有职责。

起点：Agent Center v0.2.0 已于 2026-09-24 定版，正式标签提交为 `2e4e3e6337dd2c91840070971b2ed21335acc70d`，维护者已提供 [GitHub Release](https://github.com/LiuXY-git/enterprise-ai-platform/releases/tag/agent-center-v0.2.0) 截图确认。保留旧版冻结内容，新实验在独立目录实施。

| 日期 | 原主题 | 本项目范围与状态 |
| --- | --- | --- |
| Day 71 | 学习 MCP，理解为什么需要 | [已完成概念讨论](week-11-notes.md#day71)；不将讨论记作代码验收 |
| Day 72 | 搭建第一个 MCP Server | [只读虚构 SQL Tool](week-11-notes.md#day72)；99 项测试，两个独立客户端，真实 stdio 通信 |
| Day 73 | Agent 接入 MCP | [Agent 接入 MCP](week-11-notes.md#day73)；319 项离线测试、两组真实 Qwen 场景，共 4 次模型请求 |
| Day 74 | 学习 Agent Memory | [学习材料已交付](week-11-notes.md#day74)：上下文、长期记忆、检查点与代码阅读练习；理解自测待学习者完成 |
| Day 75 | 增加 Conversation Memory | [已实现会话记忆](week-11-notes.md#day75)：SQLite 保存与恢复、更新及清除；191 项离线测试、2 次真实模型请求 |
| Day 76 | 学习 Planning | [学习材料已交付](week-11-notes.md#day76)：季度分析拆解、依赖与执行边界；复用 Day 59 离线观察，理解自测待学习者完成 |
| Day 77 | 发布 Agent Center v0.5 | [准备记录](week-11-notes.md#day77)：独立实验集合；2026-09-24 正式定版，456 项离线验收通过，维护者截图确认 v0.5.0 标签与 Release 已发布 |

Day 72 两个客户端分别是官方 Python SDK 和标准库 JSON-RPC 探针；Day 73 补充了模型实际调用，但尚未验证桌面宿主、多语言 SDK 或远程认证。后续每日成果需要单独验收，不能因为工具能被发现就宣称整个 Agent 已接入。

Day 55 视频、Workflow Center v1.0 Release、企业微信真实发送仍为独立待办，不随 Agent 学习进度自动完成。
