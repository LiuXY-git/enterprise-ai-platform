# Week 13：Agent Evaluation Center

学习方法：先定评判标准，再实现执行器。目标是构建企业评测工具的学习版本，不做 AgentBoard 论文复现。周验收目标为自动运行测试集，输出成功率、延迟、Token 与成本，并保留失败证据。

起点：Agent Center v1.0.0 于 2026-09-28 正式定版，提交 `87ceb012c8054fbd6d98b991e1f94445135bce06`，标签 `agent-center-v1.0.0` 已推送。维护者提供了 Release 正文与 verification.json 附件截图；此前截图未覆盖页面顶部，因此不将其描述为本次重新联网核对了完整 Release 身份。

| 日期 | 路线目标 | 实施范围与状态 |
| --- | --- | --- |
| Day 85 | 设计评测框架 | [已实现设计与预检](week-13-notes.md#day85)：Agent/Dataset/未执行报告契约、来源摘要、CLI、2 个结构示例 |
| Day 86 | 设计测试集 | [已完成](week-13-notes.md#day86)：12 例测试集、独立预期、覆盖约束及版本（与 Day 87 一并交付） |
| Day 87 | 自动运行测试 | [已实现](week-13-notes.md#day87)：固定 fixture 入口、独立进程、超时与逐例证据，12 例执行完成，尚未判分 |
| Day 88 | Latency | [已实现](week-13-notes.md#day88)：单调时钟、完整单例耗时、重试等待纳入总量、异常分组及 P50/P95 |
| Day 89 | Token 与成本 | [已实现](week-13-notes.md#day89)：usage 采集层、未知/模拟区分、显式价格与估算；真实模式尚未接入 |
| Day 90 | Success Rate | [已实现](week-13-notes.md#day90)：逐例独立规则判分、分类统计、完整性与分母；12/12 固定场景通过 |
| Day 91 | 发布 Evaluation Center v0.1 | [已完成发布候选](week-13-notes.md#day91)：383 项测试、12 例新运行；冻结清单与正文生成，正式标签/Release 待维护者定版 |

Day 83 视频仍待补录；Day 82 Prompt 真实模型改善仍未测量。Agent Center v1.0 冻结资产保持不变，本周以新目录承载评测代码，不因为版本名称含 v1.0 就假定其适配器、身份认证或真实发送已齐备。
