# Day 90：Success Rate

Day 90 为固定销售评测补上逐例规则判分、分类汇总和明确的成功率分母。使用 Day 86 独立预期，读取 Day 87 执行证据，并保留 Day 88 延迟和 Day 89 消耗快照。

实现：[评分规则](../experiments/day90/scoring.py)、[执行/评分/复核入口](../experiments/day90/runner.py)、[详细复刻教程](../experiments/day90/README.md)。

## 验收

- 342 项离线测试通过：54 项新增评分测试，288 项既有评测、传输与冻结发布保护测试；无失败、错误或跳过。
- 新运行 12 个固定 fixture 场景，真实本地 MCP，全部获得逐例判定，12/12 passed，成功率 100%。预期失败 1 例、预期拒绝 2 例和澄清 1 例按正确保护行为计为通过。
- 24 次 fixture 模型尝试、13 次本地 MCP 派发；真实模型请求、真实发送、模拟发送均为零。
- JSON Schema、评分只读复核、冻结资产检查与代码格式检查通过。未重新执行整套历史 721 项发布测试。

| 分类 | 用例数 | 通过数 |
| --- | --- | --- |
| normal | 2 | 2 |
| no_data | 1 | 1 |
| clarification | 1 | 1 |
| recovery | 3 | 3 |
| fallback | 2 | 2 |
| expected_failure | 1 | 1 |
| expected_rejection | 2 | 2 |

## 规则与结果

完整批次的成功率为通过数/全部选中用例数。错误、超时、缺失证据均保留在分母中；存在未执行、运行中或中断用例时，不给出最终成功率。smoke 的 4 例通过不会被标记为完整 12 例通过。

除了业务状态、金额、范围、引用和重试策略，还检查最终回答、审批草案、发送边界和证据一致性。每条规则记录 expected/actual/passed，失败时提供 failed_rules。评分标准不调用 Agent 的报告渲染器，不使用待测 Agent 自己生成的答案作为金标准。

证据：[评分报告](evidence/day90/scoring.json)、[Schema](evidence/day90/scoring.schema.json)、[测试结果](evidence/day90/regression.xml)、[验收摘要](evidence/day90/validation.json)。完整原始运行保留在本机忽略目录 `data/day90/acceptance-20260929`，其中 `run/` 是输入证据，`evaluation/report.json` 是评分。版本库中的单例 generation/events 用于阅读，不能代替 SQLite 复核材料。

## 能力边界

这是固定 fixture 规则符合率，不是真实模型或生产任务成功率。真实模型评测入口尚未接入；无 LLM-as-judge、自由文本语义评分、任意 Agent 插件或统计泛化结论。本次保留既有冻结源文件和历史证据，旧报告不追写评分。Day 91 再按实际交付范围准备 Evaluation Center v0.1。
