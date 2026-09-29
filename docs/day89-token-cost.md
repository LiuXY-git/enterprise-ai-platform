# Day 89：Token 与成本统计

新增独立 UsageTransport，捕获旧 ChatTools 标准化时丢弃的 usage；输入、输出 Token 严格校验，每次尝试独立记账。支持显式价格快照与 Decimal 核算，缺失 usage、缺价、身份不匹配及不支持的计费细分不产生伪造总额。

Day 89 CLI 封装 Day 88 完整执行记录，明确 fixture 不具有供应商 Token 数据；已确认零 API 请求的场景，模型 API 费用记为 0，Token 保持 null。未知执行行不作零费用承诺。真实调用采集机制经离线 HTTP 测试验证，未接入评测器的真实模型模式。

**288 项测试通过**：34 项新增、198 项既有评测/版本保护回归、56 项旧模型客户端回归。完整执行 12 例，24 次 fixture 模型尝试、0 次真实模型请求。离线示例验证完整账本和超时部分账本：合成输入/输出为 150/50，假设价格下已知估算为 0.00070 CNY；超时后完整费用为 null。

旧 Day 64–88 源码和历史证据保持不变，Agent Center 冻结完整性通过；没有重跑全部 721 项历史验收。价格示例不代表官方价格，本次没有付费模型请求或真实消息发送。成功率、真实模型评测和生产计费仍未完成。

- [复刻教程](../experiments/day89/README.md)
- [usage 采集层](../experiments/day89/transport.py)
- [Token 与费用规则](../experiments/day89/usage.py)
- [显式示例价格](../experiments/day89/examples/illustrative-pricing.json)
- [验收记录](evidence/day89/validation.json)
- [评测报告](evidence/day89/execution.json)
- [证据范围说明](evidence/day89/README.md)
