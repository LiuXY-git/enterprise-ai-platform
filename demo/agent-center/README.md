# Agent Center 教学材料

[Day 57 静态任务推演](day57-task-walkthrough.json)用于阅读和讨论架构，没有可执行 Agent，也不是模型输出或线上验收记录。架构说明见 [Day 57 文档](../../docs/day57-agent-architecture.md)，后续安排见 [Week 9 计划](../../docs/week-9-plan.md)。

## 如何阅读

1. `execution` 明确标记模型、工具和检索均未执行。
2. `task.plan` 给出两个子任务的完成条件。
3. `simulated_decisions` 展示一次查询 IT 制度、一次查询报销制度、最后结束的选择。`tool_call_id` 只用于连接本案例中的请求和观察。
4. `fixture_evidence` 摘自两份本地虚构制度；所有 `source` 都相对于仓库根目录，`evidence_id` 是案例标识，不是 Chroma chunk ID。
5. `simulated_observations` 关联行动与证据；`expected_outcome` 给出应覆盖的结论、引用及模拟用量。

本案例不规定正式工具协议或状态存储结构。`simulated_usage` 中的次数是纸面推演次数，不是实际 API 用量；没有生成 Token 或耗时数据。`expected_outcome.status = succeeded` 仅表示预期的模拟终态，不能当成真实执行成功。

## 原始材料

- [星云科技 IT 支持制度](../nebula-it-policy.md)：P1 响应、恢复、报障与升级。
- [星云科技差旅报销制度](../nebula-expense-policy.md)：金额区间与审批人。

两个制度与企业名称都是项目演示素材。问题可由现有 RAG 处理，这里拆分查询用于解释观察结果如何影响下一步。

可人工核对：是否把 30 分钟升级误写成无条件升级，是否把 8000 元误归入超过 10000 元的审批档位，以及最后回答是否同时覆盖两个问题。空结果、超时和非法工具等其他分支的预期行为见 Day 57 文档，今天没有执行这些分支。
