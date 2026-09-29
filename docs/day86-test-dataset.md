# Day 86：正式测试集

补齐前次中断后未提交的测试集工作，与 Day 87 执行器一并交付。数据版本为 sales-prepare-fixture 1.0.0，范围固定为 Day 82 fixture prepare。

交付 12 个唯一场景、4 例 smoke 子集、独立订单金标准、重试/降级/拒绝预期、严格契约、源摘要校验及不执行 Agent 的预检 CLI。Day 85 示例与冻结源文件保持原样。

32 项测试验证类型、重复/遗漏场景、错误金额、来源变动、非法 JSON、伪造预检结果和证据不覆盖。该测试集验证代码不等于 Agent 已通过 12 例评测。

- [分类、金额核算与边界](../evaluation-center/datasets/README.md)
- [预检复刻教程](../experiments/day86/README.md)
- [数据文件](../evaluation-center/datasets/sales-prepare-v1.0.0.json)
- [Day 87 执行器](day87-evaluation-runner.md)
