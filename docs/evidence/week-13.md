# Week 13：测试与运行结果

本周收录 Day 85、86、87、88、89、90、91，共 136 份原始记录。日常阅读本页即可，详细 JSON、XML 和运行记录收在[本周数据包](week-13.zip)。

[返回周目录](README.md) · [学习与操作记录](../week-13-notes.md)

## 一览

| 日期 | 验证内容 | 当次测试统计 |
| --- | --- | --- |
| [Day 85](#day85) | Agent、数据集与报告契约 | 103 项 |
| [Day 86](#day86) | 12 个固定用例与预检 | 12 例预检，未执行 Agent |
| [Day 87](#day87) | 逐例执行与证据保存 | 170 项 |
| [Day 88](#day88) | 延迟统计 | 198 项 |
| [Day 89](#day89) | Token、成本与缺失处理 | 288 项 |
| [Day 90](#day90) | 独立评分与成功率 | 342 项 |
| [Day 91](#day91) | Evaluation Center v0.1 阶段验收 | 383 项 |

各日测试范围可能重叠，不将这些数字累加为本周独立测试总数。记录描述当时运行结果，不能代替修改后的重新测试。

<a id="day85"></a>

## Day 85：Agent、数据集与报告契约

- 主要结果：`validation.json`；共 7 份记录。
- 操作说明：[Week 13 对应章节](../week-13-notes.md#day85)。

<a id="day86"></a>

## Day 86：12 个固定用例与预检

- 主要结果：`full-preflight.json`；共 4 份记录。
- 操作说明：[Week 13 测试集章节](../week-13-notes.md#day86)。

<a id="day87"></a>

## Day 87：逐例执行与证据保存

- 主要结果：`execution.json`、`validation.json`；共 28 份记录。
- 使用固定虚构场景和 fixture 模型结果；涉及真实本地 MCP 执行，未调用真实模型。
- 操作说明：[Week 13 对应章节](../week-13-notes.md#day87)。

<a id="day88"></a>

## Day 88：延迟统计

- 主要结果：`execution.json`、`validation.json`；共 29 份记录。
- 使用固定虚构场景和 fixture 模型结果；涉及真实本地 MCP 执行，未调用真实模型。
- 操作说明：[Week 13 对应章节](../week-13-notes.md#day88)。

<a id="day89"></a>

## Day 89：Token、成本与缺失处理

- 主要结果：`execution.json`、`validation.json`；共 34 份记录。
- 使用固定虚构场景和 fixture 模型结果；涉及真实本地 MCP 执行，未调用真实模型。
- fixture Token 保留未知；模型 API 成本为零不表示所有计算免费。
- 操作说明：[Week 13 对应章节](../week-13-notes.md#day89)。

<a id="day90"></a>

## Day 90：独立评分与成功率

- 主要结果：`scoring.json`、`validation.json`；共 28 份记录。
- 使用固定虚构场景和 fixture 模型结果；涉及真实本地 MCP 执行，未调用真实模型。
- 12 个固定场景均符合预期；该结果仅代表这批场景的规则符合情况。
- 操作说明：[Week 13 对应章节](../week-13-notes.md#day90)。

<a id="day91"></a>

## Day 91：Evaluation Center v0.1 阶段验收

- 主要结果：`scoring.json`、`validation.json`、`verification.json`；共 6 份记录。
- 使用固定虚构场景和 fixture 模型结果；涉及真实本地 MCP 执行，未调用真实模型。
- 12 个固定场景均符合预期；该结果仅代表这批场景的规则符合情况。
- 操作说明：[Week 13 对应章节](../week-13-notes.md#day91)。
