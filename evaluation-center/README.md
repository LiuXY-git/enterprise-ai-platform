# Evaluation Center：评测框架设计

Week 13 从 Day 85 开始：输入 **Agent 描述 + 测试集**，最终输出可追溯的 **Evaluation Report**。

当前是 `0.1-design` 设计阶段，已实现契约校验和不执行任务的预检报告。自动运行、结果判分、延迟、Token、成本和成功率尚未实现。本阶段不等于 Evaluation Center v0.1 已发布。

- [框架设计与数据流](design.md)
- [Day 85 复刻教程](../experiments/day85/README.md)
- [Week 13 实施顺序](../docs/week-13-plan.md)
- [Day 85 交付与验证](../docs/day85-evaluation-framework.md)

第一次运行按教程使用 `preview`。看到 `preflight_valid` 表示输入与本地声明文件通过预检；报告内每个任务仍是 `not_run`、`not_evaluated`，不是 Agent 测试通过。
