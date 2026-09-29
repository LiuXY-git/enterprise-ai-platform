# Day 88：Latency 统计

在 Day 87 执行器外增加 perf_counter_ns 单调时钟，测量每例包含进程启动、所有尝试、退避等待、清理和基础证据落盘的总耗时。独立入口与新报告 schema 保留既有代码、测试集和历史证据。

提供执行状态和业务状态分组的样本数、最小值、均值、P50、P95、最大值。空组为 null；错误、超时与中断的部分观测单独统计；百分位使用 nearest-rank。汇总可由单例原始纳秒重新核对。

28 项新增测试和 170 项既有回归，共 **198 项测试通过**。最终代码完整运行 12 个场景并保存实际耗时；模型为 fixture，MCP 是真实本地 stdio，真实模型请求、模拟发送和真实发送均为 0。

本机观测值见验收 JSON；它不是线上模型基准或性能提升证明。完整执行样本可能包含业务失败和拒绝，不能视作答题正确率。Token、成本及成功率仍未测量。

Agent Center v1.0 与历史版本冻结完整性检查通过；未重跑全量 721 项历史验收。Day 83 视频延期和 Day 82 真实模型质量改善未测量状态保持不变。

- [操作教程与计时边界](../experiments/day88/README.md)
- [延迟契约与汇总](../experiments/day88/latency.py)
- [执行入口](../experiments/day88/runner.py)
- [验收记录](evidence/day88/validation.json)
- [执行报告](evidence/day88/execution.json)
- [证据范围](evidence/day88/README.md)
