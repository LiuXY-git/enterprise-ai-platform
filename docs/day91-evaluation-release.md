# Day 91：Evaluation Center v0.1 发布准备

今天把 Day 85–90 的评测模块整理为可冻结、可重跑验收的版本。新增发布清单、完整性门禁、验收脚本、正式 Release 正文生成器和使用说明。当前为本地发布候选，不自动创建远端标签或 Release。

## 验收结果

- 383 项离线测试通过：342 项既有回归，41 项新发布测试；无失败、错误或跳过，跨组测试编号去重。
- 新运行 12 个 fixture 场景，全部符合独立预期；成功率 12/12。原始执行由真实本地 MCP/SQLite 完成，模型为固定模拟响应。
- 本轮 24 次 fixture 模型尝试、13 次 MCP 派发；真实模型请求、真实发送、模拟发送均为零。
- 清单与历史证据关联、Day 90 规则重新判分、Agent Center 历史资产完整性链、候选/正式两种状态测试、Ruff 与环境依赖检查通过。
- 未重新执行整套 721 项 Agent Center 历史发布测试。

文件：[发布清单](../evaluation-center/release-v0.1.0.json)、[门禁](../scripts/day91/release_gate.py)、[验收脚本](../scripts/day91/verify_release.py)、[正文生成器](../scripts/day91/release_notes.py)。

证据：[verification.json](evidence/day91/verification.json)、[本次评分](evidence/day91/scoring.json)、[回归测试 XML](evidence/day91/regression.xml)、[发布测试 XML](evidence/day91/release.xml)、[验收摘要](evidence/day91/validation.json)。本机完整验收目录为 `data/day91/candidate-20260930`。版本库只保存摘要，不假装包含所有 SQLite。

## 为什么有用

之后修改评测器或 Agent 适配器时，可以识别是否改变固定行为、破坏旧证据，或把失败与缺失错误地统计成高成功率。版本清单让代码、测试集、评分器、验收结果有明确对应关系；正式发布时需重新验收 released 清单，候选结果不能替代正式结果。

文件哈希与历史关联的双重检查，不等于不可篡改的外部审计。发布内容、规则和真实模式边界见 [版本说明](evaluation-center-v0.1.md)。[详细复刻与发布教程](../scripts/day91/README.md) 包括本地验收和后续手工创建标签/Release 的操作。
