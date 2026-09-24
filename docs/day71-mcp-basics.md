# Day 71 理解 MCP

本日按学习路线讨论为什么需要 MCP，并以 Day 65–69 的工具实验解释其用途。完成的是概念学习，没有新增 MCP 运行时或真实调用记录。

现有 Agent 可以直接调用项目里的 SQL、知识检索和天气实现。另一个 AI 应用复用这些能力时，需要理解项目内部接口。MCP（Model Context Protocol）提供共同的发现、调用和结果返回规则，让兼容的应用更容易复用服务端能力。

| 概念 | 在本项目中的分工 |
| --- | --- |
| Planning | 将目标拆成步骤，形成任务计划 |
| LangGraph | 组织步骤、状态、条件分支和循环；Planning 可以是其中一个节点 |
| Function Calling | 模型表达工具名称和参数，应用决定是否执行 |
| MCP | 应用与工具服务之间的标准通信协议 |

Host 是管理模型与对话的应用，Client 是其中负责 MCP 通信的组件，Server 是提供工具等能力的程序。Server 可以在本机运行，不必部署到云服务器。SQL 如何查询、哪些参数合法、哪些权限允许，仍需业务实现负责。

后续示意：用户提出需求 → 模型建议工具调用 → 应用检查 → MCP Client → MCP Server → 原 SQL Tool → 返回数据。该图是学习设计，不代表 Day 71 已将这条链路实现。

MCP 的服务端还可以提供资源和提示模板；本周先从单个查询工具开始。Day 72 搭建服务端并用确定性的测试客户端验证，Day 73 再由 Agent 接入。

参考：[MCP 架构](https://modelcontextprotocol.io/docs/learn/architecture)、[服务端能力](https://modelcontextprotocol.io/docs/learn/server-concepts)。查阅日期：2026-09-24。
