# Week 13：Agent 评测框架

路线范围：Day 85–91。本文件包含 7 个每日章节，保留完整步骤、命令、验收记录与能力边界。

本周内容按日期排列，各节保留对应日期的实施状态，当前进度以[项目首页](../README.md)为准。

[返回周目录](README.md#按周阅读) · [本周计划](week-13-plan.md) · [本周总结](week-13-summary.md)

## 本周目录

- [Day 85：评测框架设计与契约预检](#day85)
- [Day 86：正式测试集](#day86)
- [Day 87：自动运行 Agent 测试集](#day87)
- [Day 88：Latency 统计](#day88)
- [Day 89：Token 与成本统计](#day89)
- [Day 90：Success Rate](#day90)
- [Day 91：Evaluation Center v0.1 发布准备](#day91)

---

<a id="day85"></a>

## Day 85：评测框架设计与契约预检


依据 16 周路线进入 Week 13，今天先定义 Agent + Test Dataset → Evaluation Report 的结构和职责。基线为正式定版提交 `87ceb012c8054fbd6d98b991e1f94445135bce06`。

<a id="day85-交付"></a>

### 交付

- [Evaluation Center 入口](../evaluation-center/README.md)和 [架构、判定口径与能力边界](../evaluation-center/design.md)。
- [严格契约](../experiments/day85/contracts.py)：Agent 描述、样例与断言、Dataset 和未执行的报告。
- [CLI](../experiments/day85/framework.py)：结构校验、本地源文件摘要预检、报告生成和 JSON Schema 导出。
- 两个最小契约示例及 [可复刻教程](../experiments/day85/README.md)。
- [Week 13 实施计划](week-13-plan.md)，把执行器、指标与评分留在对应日期实现。

<a id="day85-验证"></a>

### 验证

59 项新增契约测试、44 项 v1.0 发布保护回归，共 103 项通过，无失败、错误或跳过。包含重复/冲突输入、值类型、伪造完成状态、未知指标不能写成 0、来源哈希改变、目录保护、JSON Schema 结构检查及不执行 Agent 的测试。

额外生成一份可读的预检报告并导出 Schema；其两行状态均为 `not_run`，不计作 Agent 业务任务通过。证据见 [validation.json](evidence/week-13.md#day85) 与 [预检报告](evidence/week-13.md#day85)。

Agent Center v1.0 及父版本冻结资产完整性通过。旧 Agent、API、Docker 配置与发布资产均未修改；没有重新运行全部 721 项旧版发布测试。本次不调用模型、MCP 或发送服务。

<a id="day85-能力边界"></a>

### 能力边界

输入校验和预检成功不代表 Agent 执行成功。源码摘要检查仅针对描述中的四个固定本地文件，不解析声明提交、检查远端发布或证明整个依赖链行为正确。两个示例仅用于说明契约，不是覆盖完整业务的正式测试集。

无自动运行器、无实际评分、无延迟/Token/成本测量，也不计算成功率。输出中这些指标为 null，所有任务仍未执行。下一步 Day 86 在此结构上设计正式测试集。

---

<a id="day86"></a>

## Day 86：正式测试集


补齐前次中断后未提交的测试集工作，与 Day 87 执行器一并交付。数据版本为 sales-prepare-fixture 1.0.0，范围固定为 Day 82 fixture prepare。

交付 12 个唯一场景、4 例 smoke 子集、独立订单金标准、重试/降级/拒绝预期、严格契约、源摘要校验及不执行 Agent 的预检 CLI。Day 85 示例与冻结源文件保持原样。

32 项测试验证类型、重复/遗漏场景、错误金额、来源变动、非法 JSON、伪造预检结果和证据不覆盖。该测试集验证代码不等于 Agent 已通过 12 例评测。

- [分类、金额核算与边界](../evaluation-center/datasets/README.md)
- [预检复刻教程](../experiments/day86/README.md)
- [数据文件](../evaluation-center/datasets/sales-prepare-v1.0.0.json)
- [Day 87 执行器](week-13-notes.md#day87)

---

<a id="day87"></a>

## Day 87：自动运行 Agent 测试集


将 Day 86 的固定测试集接到 Day 82 fixture 入口，逐例启动独立 Python 进程，使用真实本地 stdio MCP 查询独立虚构 SQLite，保留实际回答、事件、审批快照、数据库与文件哈希。

每例有 5–120 秒超时限额；普通单例错误继续后续用例；中断或无法确认子进程树清理时停止整批。报告逐例原子更新，已有运行目录不会覆盖。子进程不接收金标准，不开放任意脚本、真实模型或发送入口。

<a id="day87-本次验证"></a>

### 本次验证

2026-09-29：32 项 Day 86 测试、35 项 Day 87 测试、59 项 Day 85 回归与 44 项发布保护检查，共 **170 项测试**通过。此前受限会话拒绝 taskkill，随后在正常 Windows 权限下验证了父子进程树清理；权限拒绝分支也有测试，并明确中断整批。

最终代码完整执行 12 例，均取得有效执行记录。业务状态为 completed 7、no_data 1、needs_clarification 1、failed 1、rejected 2；与场景设计逐例核对。真实模型请求 0，模拟发送 0，真实消息发送 0。输入模型为 fixture，MCP 为真实本地子进程。

这里的 execution completed 不是评测 passed。所有 judgement 为 not_evaluated，成功率、延迟、Token、成本均为 null。自动判分与指标采集留给 Day 88–90。测试阶段另有一次开发版完整运行，记录留在工作区，不冒充新的独立场景。

Agent Center v1.0 及历史版本冻结资产完整性通过；本次未重跑全部 721 项历史验收。Day 83 视频仍延期，Day 82 真实模型质量改善仍未测量。

<a id="day87-文件入口"></a>

### 文件入口

- [逐步复刻教程](../experiments/day87/README.md)
- [执行器](../experiments/day87/runner.py)
- [固定 worker](../experiments/day87/worker.py)
- [执行报告契约](../experiments/day87/execution_contracts.py)
- [验证记录](evidence/week-13.md#day87)
- [本次完整执行报告快照](evidence/week-13.md#day87)
- [证据范围说明](evidence/week-13.md#day87)
- [Week 13 计划](week-13-plan.md)

---

<a id="day88"></a>

## Day 88：Latency 统计


在 Day 87 执行器外增加 perf_counter_ns 单调时钟，测量每例包含进程启动、所有尝试、退避等待、清理和基础证据落盘的总耗时。独立入口与新报告 schema 保留既有代码、测试集和历史证据。

提供执行状态和业务状态分组的样本数、最小值、均值、P50、P95、最大值。空组为 null；错误、超时与中断的部分观测单独统计；百分位使用 nearest-rank。汇总可由单例原始纳秒重新核对。

28 项新增测试和 170 项既有回归，共 **198 项测试通过**。最终代码完整运行 12 个场景并保存实际耗时；模型为 fixture，MCP 是真实本地 stdio，真实模型请求、模拟发送和真实发送均为 0。

本机观测值见验收 JSON；它不是线上模型基准或性能提升证明。完整执行样本可能包含业务失败和拒绝，不能视作答题正确率。Token、成本及成功率仍未测量。

Agent Center v1.0 与历史版本冻结完整性检查通过；未重跑全量 721 项历史验收。Day 83 视频延期和 Day 82 真实模型质量改善未测量状态保持不变。

- [操作教程与计时边界](../experiments/day88/README.md)
- [延迟契约与汇总](../experiments/day88/latency.py)
- [执行入口](../experiments/day88/runner.py)
- [验收记录](evidence/week-13.md#day88)
- [执行报告](evidence/week-13.md#day88)
- [证据范围](evidence/week-13.md#day88)

---

<a id="day89"></a>

## Day 89：Token 与成本统计


新增独立 UsageTransport，捕获旧 ChatTools 标准化时丢弃的 usage；输入、输出 Token 严格校验，每次尝试独立记账。支持显式价格快照与 Decimal 核算，缺失 usage、缺价、身份不匹配及不支持的计费细分不产生伪造总额。

Day 89 CLI 封装 Day 88 完整执行记录，明确 fixture 不具有供应商 Token 数据；已确认零 API 请求的场景，模型 API 费用记为 0，Token 保持 null。未知执行行不作零费用承诺。真实调用采集机制经离线 HTTP 测试验证，未接入评测器的真实模型模式。

**288 项测试通过**：34 项新增、198 项既有评测/版本保护回归、56 项旧模型客户端回归。完整执行 12 例，24 次 fixture 模型尝试、0 次真实模型请求。离线示例验证完整账本和超时部分账本：合成输入/输出为 150/50，假设价格下已知估算为 0.00070 CNY；超时后完整费用为 null。

旧 Day 64–88 源码和历史证据保持不变，Agent Center 冻结完整性通过；没有重跑全部 721 项历史验收。价格示例不代表官方价格，本次没有付费模型请求或真实消息发送。成功率、真实模型评测和生产计费仍未完成。

- [复刻教程](../experiments/day89/README.md)
- [usage 采集层](../experiments/day89/transport.py)
- [Token 与费用规则](../experiments/day89/usage.py)
- [显式示例价格](../experiments/day89/examples/illustrative-pricing.json)
- [验收记录](evidence/week-13.md#day89)
- [评测报告](evidence/week-13.md#day89)
- [证据范围说明](evidence/week-13.md#day89)

---

<a id="day90"></a>

## Day 90：Success Rate


Day 90 为固定销售评测补上逐例规则判分、分类汇总和明确的成功率分母。使用 Day 86 独立预期，读取 Day 87 执行证据，并保留 Day 88 延迟和 Day 89 消耗快照。

实现：[评分规则](../experiments/day90/scoring.py)、[执行/评分/复核入口](../experiments/day90/runner.py)、[详细复刻教程](../experiments/day90/README.md)。

<a id="day90-验收"></a>

### 验收

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

<a id="day90-规则与结果"></a>

### 规则与结果

完整批次的成功率为通过数/全部选中用例数。错误、超时、缺失证据均保留在分母中；存在未执行、运行中或中断用例时，不给出最终成功率。smoke 的 4 例通过不会被标记为完整 12 例通过。

除了业务状态、金额、范围、引用和重试策略，还检查最终回答、审批草案、发送边界和证据一致性。每条规则记录 expected/actual/passed，失败时提供 failed_rules。评分标准不调用 Agent 的报告渲染器，不使用待测 Agent 自己生成的答案作为金标准。

证据：[评分报告](evidence/week-13.md#day90)、[Schema](evidence/week-13.md#day90)、[测试结果](evidence/week-13.md#day90)、[验收摘要](evidence/week-13.md#day90)。完整原始运行保留在本机忽略目录 `data/day90/acceptance-20260929`，其中 `run/` 是输入证据，`evaluation/report.json` 是评分。版本库中的单例 generation/events 用于阅读，不能代替 SQLite 复核材料。

<a id="day90-能力边界"></a>

### 能力边界

这是固定 fixture 规则符合率，不是真实模型或生产任务成功率。真实模型评测入口尚未接入；无 LLM-as-judge、自由文本语义评分、任意 Agent 插件或统计泛化结论。本次保留既有冻结源文件和历史证据，旧报告不追写评分。Day 91 再按实际交付范围准备 Evaluation Center v0.1。

---

<a id="day91"></a>

## Day 91：Evaluation Center v0.1 发布准备


今天把 Day 85–90 的评测模块整理为可冻结、可重跑验收的版本。新增发布清单、完整性门禁、验收脚本、正式 Release 正文生成器和使用说明。当前为本地发布候选，不自动创建远端标签或 Release。

<a id="day91-验收结果"></a>

### 验收结果

- 383 项离线测试通过：342 项既有回归，41 项新发布测试；无失败、错误或跳过，跨组测试编号去重。
- 新运行 12 个 fixture 场景，全部符合独立预期；成功率 12/12。原始执行由真实本地 MCP/SQLite 完成，模型为固定模拟响应。
- 本轮 24 次 fixture 模型尝试、13 次 MCP 派发；真实模型请求、真实发送、模拟发送均为零。
- 清单与历史证据关联、Day 90 规则重新判分、Agent Center 历史资产完整性链、候选/正式两种状态测试、Ruff 与环境依赖检查通过。
- 未重新执行整套 721 项 Agent Center 历史发布测试。

文件：[发布清单](../evaluation-center/release-v0.1.0.json)、[门禁](../scripts/day91/release_gate.py)、[验收脚本](../scripts/day91/verify_release.py)、[正文生成器](../scripts/day91/release_notes.py)。

证据：[verification.json](evidence/week-13.md#day91)、[本次评分](evidence/week-13.md#day91)、[回归测试 XML](evidence/week-13.md#day91)、[发布测试 XML](evidence/week-13.md#day91)、[验收摘要](evidence/week-13.md#day91)。本机完整验收目录为 `data/day91/candidate-20260930`。版本库只保存摘要，不假装包含所有 SQLite。

<a id="day91-为什么有用"></a>

### 为什么有用

之后修改评测器或 Agent 适配器时，可以识别是否改变固定行为、破坏旧证据，或把失败与缺失错误地统计成高成功率。版本清单让代码、测试集、评分器、验收结果有明确对应关系；正式发布时需重新验收 released 清单，候选结果不能替代正式结果。

文件哈希与历史关联的双重检查，不等于不可篡改的外部审计。发布内容、规则和真实模式边界见 [版本说明](evaluation-center-v0.1.md)。[详细复刻与发布教程](../scripts/day91/README.md) 包括本地验收和后续手工创建标签/Release 的操作。
