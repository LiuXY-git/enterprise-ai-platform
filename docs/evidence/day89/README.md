# Day 89 证据

regression.xml 记录 288 项测试；execution.json 是包含 Day 88 执行快照及 fixture usage 的主报告；cases/ 保存本轮实际回答和事件；demo/ 保存合成 HTTP 账本、假设价格快照和核算结果。validation.json 分别记录真实本地 MCP 集成与合成 usage 验证，两者不混计为真实模型调用。

完整运行数据库和进程输出位于本机 data/day89/acceptance-20260929，受 Git 忽略。可用 Day 89 inspect 检查此完整目录；Git 中的 JSON/XML 摘录不含数据库，不应直接传给 inspect。其他机器按教程重新生成自己的运行目录。

demo 中 synthetic_response 的 usage 和 illustrative 价格仅用于算术与协议验证。不能把示例的 200 Token 或 0.00070 CNY 计入真实 Agent 消耗或供应商账单。
