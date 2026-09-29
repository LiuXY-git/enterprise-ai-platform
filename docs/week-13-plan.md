# Week 13：Agent Evaluation Center

学习方法：先定评判标准，再实现执行器。目标是构建企业评测工具的学习版本，不做 AgentBoard 论文复现。周验收目标为自动运行测试集，输出成功率、延迟、Token 与成本，并保留失败证据。

起点：Agent Center v1.0.0 于 2026-09-28 正式定版，提交 `87ceb012c8054fbd6d98b991e1f94445135bce06`，标签 `agent-center-v1.0.0` 已推送。维护者提供了 Release 正文与 verification.json 附件截图；此前截图未覆盖页面顶部，因此不将其描述为本次重新联网核对了完整 Release 身份。

| 日期 | 路线目标 | 实施范围与状态 |
| --- | --- | --- |
| Day 85 | 设计评测框架 | [已实现设计与预检](day85-evaluation-framework.md)：Agent/Dataset/未执行报告契约、来源摘要、CLI、2 个结构示例 |
| Day 86 | 设计测试集 | [已完成](day86-test-dataset.md)：12 例测试集、独立预期、覆盖约束及版本（与 Day 87 一并交付） |
| Day 87 | 自动运行测试 | [已实现](day87-evaluation-runner.md)：固定 fixture 入口、独立进程、超时与逐例证据，12 例执行完成，尚未判分 |
| Day 88 | Latency | [已实现](day88-latency.md)：单调时钟、完整单例耗时、重试等待纳入总量、异常分组及 P50/P95 |
| Day 89 | Token 与成本 | [已实现](day89-token-cost.md)：usage 采集层、未知/模拟区分、显式价格与估算；真实模式尚未接入 |
| Day 90 | Success Rate | 待实施：逐例规则判分、分类计数、完整性与分母 |
| Day 91 | 发布 Evaluation Center v0.1 | 待实施：按已实现能力冻结清单与验收 |

Day 83 视频仍待补录；Day 82 Prompt 真实模型改善仍未测量。Agent Center v1.0 冻结资产保持不变，本周以新目录承载评测代码，不因为版本名称含 v1.0 就假定其适配器、身份认证或真实发送已齐备。
