# Day 85：评测框架设计与契约预检

依据 16 周路线进入 Week 13，今天先定义 Agent + Test Dataset → Evaluation Report 的结构和职责。基线为正式定版提交 `87ceb012c8054fbd6d98b991e1f94445135bce06`。

## 交付

- [Evaluation Center 入口](../evaluation-center/README.md)和 [架构、判定口径与能力边界](../evaluation-center/design.md)。
- [严格契约](../experiments/day85/contracts.py)：Agent 描述、样例与断言、Dataset 和未执行的报告。
- [CLI](../experiments/day85/framework.py)：结构校验、本地源文件摘要预检、报告生成和 JSON Schema 导出。
- 两个最小契约示例及 [可复刻教程](../experiments/day85/README.md)。
- [Week 13 实施计划](week-13-plan.md)，把执行器、指标与评分留在对应日期实现。

## 验证

59 项新增契约测试、44 项 v1.0 发布保护回归，共 103 项通过，无失败、错误或跳过。包含重复/冲突输入、值类型、伪造完成状态、未知指标不能写成 0、来源哈希改变、目录保护、JSON Schema 结构检查及不执行 Agent 的测试。

额外生成一份可读的预检报告并导出 Schema；其两行状态均为 `not_run`，不计作 Agent 业务任务通过。证据见 [validation.json](evidence/day85/validation.json) 与 [预检报告](evidence/day85/preview/report.json)。

Agent Center v1.0 及父版本冻结资产完整性通过。旧 Agent、API、Docker 配置与发布资产均未修改；没有重新运行全部 721 项旧版发布测试。本次不调用模型、MCP 或发送服务。

## 能力边界

输入校验和预检成功不代表 Agent 执行成功。源码摘要检查仅针对描述中的四个固定本地文件，不解析声明提交、检查远端发布或证明整个依赖链行为正确。两个示例仅用于说明契约，不是覆盖完整业务的正式测试集。

无自动运行器、无实际评分、无延迟/Token/成本测量，也不计算成功率。输出中这些指标为 null，所有任务仍未执行。下一步 Day 86 在此结构上设计正式测试集。
