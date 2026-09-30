# Evaluation Center：Agent 评测学习模块

Week 13 输入 Agent 描述和版本化测试集，逐步构建可追溯的评测报告。

- [Day 85 框架设计](design.md)：描述契约与未执行预检，旧示例保留。
- [Day 86 正式测试集](datasets/README.md)：12 个固定虚构销售场景和独立标准答案。
- [Day 87 自动执行教程](../experiments/day87/README.md)：固定 fixture Agent、真实本地 MCP、隔离目录、逐例运行与证据检查。
- [Day 88 延迟教程](../experiments/day88/README.md)：单例耗时、分组均值和 P50/P95，异常样本单列。
- [Day 89 Token 与成本](../experiments/day89/README.md)：usage 采集、显式价格、完整/部分账本与 fixture 计费边界。
- [Day 90 成功率](../experiments/day90/README.md)：独立规则判分、失败原因、分类统计及分母。
- [Evaluation Center v0.1.0 发布候选](v0.1/README.md)：版本范围、验收与正式发布操作。
- [Week 13 计划](../docs/week-13-plan.md)。

当前可以自动执行并保留结果。执行状态与业务状态分别记录；已增加单例延迟和 usage/成本核算；Day 90 已增加独立判分与成功率，真实模型评测尚未接入。Evaluation Center v0.1.0 已完成候选验收，正式标签和 GitHub Release 待维护者定版。

第一次使用先执行 Day 86 check / preview，再运行 Day 87 smoke 或 full。预检的 not_run、执行的 completed、Day 90 评分的 passed 分属三个不同阶段，不能混为“全部测试通过”。
