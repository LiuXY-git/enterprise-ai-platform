# Day 87：自动运行 Agent 测试集

将 Day 86 的固定测试集接到 Day 82 fixture 入口，逐例启动独立 Python 进程，使用真实本地 stdio MCP 查询独立虚构 SQLite，保留实际回答、事件、审批快照、数据库与文件哈希。

每例有 5–120 秒超时限额；普通单例错误继续后续用例；中断或无法确认子进程树清理时停止整批。报告逐例原子更新，已有运行目录不会覆盖。子进程不接收金标准，不开放任意脚本、真实模型或发送入口。

## 本次验证

2026-09-29：32 项 Day 86 测试、35 项 Day 87 测试、59 项 Day 85 回归与 44 项发布保护检查，共 **170 项测试**通过。此前受限会话拒绝 taskkill，随后在正常 Windows 权限下验证了父子进程树清理；权限拒绝分支也有测试，并明确中断整批。

最终代码完整执行 12 例，均取得有效执行记录。业务状态为 completed 7、no_data 1、needs_clarification 1、failed 1、rejected 2；与场景设计逐例核对。真实模型请求 0，模拟发送 0，真实消息发送 0。输入模型为 fixture，MCP 为真实本地子进程。

这里的 execution completed 不是评测 passed。所有 judgement 为 not_evaluated，成功率、延迟、Token、成本均为 null。自动判分与指标采集留给 Day 88–90。测试阶段另有一次开发版完整运行，记录留在工作区，不冒充新的独立场景。

Agent Center v1.0 及历史版本冻结资产完整性通过；本次未重跑全部 721 项历史验收。Day 83 视频仍延期，Day 82 真实模型质量改善仍未测量。

## 文件入口

- [逐步复刻教程](../experiments/day87/README.md)
- [执行器](../experiments/day87/runner.py)
- [固定 worker](../experiments/day87/worker.py)
- [执行报告契约](../experiments/day87/execution_contracts.py)
- [验证记录](evidence/day87/validation.json)
- [本次完整执行报告快照](evidence/day87/execution.json)
- [证据范围说明](evidence/day87/README.md)
- [Week 13 计划](week-13-plan.md)
