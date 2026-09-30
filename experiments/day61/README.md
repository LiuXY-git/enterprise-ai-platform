# Day 61：销售跟进分析场景契约

本目录将业务设计变成可以离线校验的字段、规则和样例。使用人工构造的虚构 CRM 快照，输出确定性建议类别，不调用模型或 CRM，不运行 LangGraph Agent。

在仓库根目录执行：

```powershell
& .\.venv\Scripts\python.exe .\experiments\day61\check_scenario.py --list
& .\.venv\Scripts\python.exe .\experiments\day61\check_scenario.py --case normal
& .\.venv\Scripts\python.exe .\experiments\day61\check_scenario.py --check-all
& .\.venv\Scripts\python.exe -m pytest .\experiments\day61\test_sales_scenario.py -q
```

使用现有 API 环境中的 Pydantic 和 pytest，无新增依赖。Windows PowerShell 处理中文输出时可设置 `$env:PYTHONIOENCODING='utf-8'` 和 `[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false)`。

| 文件 | 作用 |
| --- | --- |
| `sales_contract.py` | 输入快照与报告的 Pydantic 模型 |
| `scenario_rules.py` | 确定性业务规则与跨字段、跨来源验收 |
| `check_scenario.py` | 检查内置样例的 CLI |
| [cases.json](cases.json) | 13 个独立规定预期结果的虚构样例 |
| [input-schema.json](input-schema.json) / [output-schema.json](output-schema.json) | 从模型导出的 JSON Schema |
| [plan-example.json](plan-example.json) | 人工编写、符合 Day 59 格式的三步计划 |
| `test_sales_scenario.py` | 输入边界、资料缺口与伪造报告测试 |

JSON Schema 描述字段结构，不能表达所有跨记录业务约束；消费方仍需运行 Pydantic 校验和 `validate_report(source, report)`。CLI 的 `validation=passed` 表示样例符合契约，即使样例的业务状态是 `failed`，退出码也为 0。未知样例或验收不匹配退出码为 1。

完整业务定义、类别说明和实施边界见 [Day 61 说明](../../docs/week-9-notes.md#day61)。
