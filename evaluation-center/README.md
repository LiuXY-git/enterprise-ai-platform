# Evaluation Center：Agent 评测学习模块

Week 13 输入 Agent 描述和版本化测试集，逐步构建可追溯的评测报告。

- [Day 85 框架设计](design.md)：描述契约与未执行预检，旧示例保留。
- [Day 86 正式测试集](datasets/README.md)：12 个固定虚构销售场景和独立标准答案。
- [Day 87 自动执行教程](../experiments/day87/README.md)：固定 fixture Agent、真实本地 MCP、隔离目录、逐例运行与证据检查。
- [Day 88 延迟教程](../experiments/day88/README.md)：单例耗时、分组均值和 P50/P95，异常样本单列。
- [Week 13 计划](../docs/week-13-plan.md)。

当前可以自动执行并保留结果。执行状态与业务状态分别记录；已增加单例延迟；自动判分、成功率、Token 和成本采集仍待 Day 89–90 实现。Evaluation Center v0.1 尚未发布。

第一次使用先执行 Day 86 check / preview，再运行 Day 87 smoke 或 full。预检的 not_run、执行的 completed、未来评分的 passed 分属三个不同阶段，不能混为“全部测试通过”。
