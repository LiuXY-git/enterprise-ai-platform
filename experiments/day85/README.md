# Day 85：设计并预检评测框架

今天先确定“考谁、考什么、怎样判定、怎样保存结果”。代码负责检查配置并生成未执行的评测计划；不会启动 Agent、MCP 或模型，也不会创建审批。

完整设计：[Evaluation Center](../../evaluation-center/design.md)。后续顺序：[Week 13](../../docs/week-13-plan.md)。

## 1. 使用已有环境

复用 Day 73 环境中的 Pydantic；测试另使用已有 pytest/jsonschema，不增加依赖。新机器按 [Day 73 环境说明](../day73/README.md) 安装。

```powershell
Set-Location 'C:\Users\Administrator\Desktop\enterprise-ai-platform'
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
```

## 2. 阅读两个输入文件

- [agent.json](examples/agent.json)：声明评测对象为 Day 82 fixture 候选入口，带四个本地文件的摘要。
- [dataset.json](examples/dataset.json)：2 个最小契约示例，正常简报与缺少年月，不是 Day 86 的正式测试集。

正常样例期待业务状态 completed、4 单、3000.00 元、有引用、审批 pending，模拟发送记录为 0。这里的 `expected` 是出题时的预期，不能当成已经观察到的结果。

## 3. 单独检查输入结构

```powershell
& .\experiments\day73\.venv\Scripts\python.exe -B .\experiments\day85\framework.py check --kind agent --file .\experiments\day85\examples\agent.json
if ($LASTEXITCODE -ne 0) { throw 'Agent 描述不符合契约' }
& .\experiments\day73\.venv\Scripts\python.exe -B .\experiments\day85\framework.py check --kind dataset --file .\experiments\day85\examples\dataset.json
if ($LASTEXITCODE -ne 0) { throw '测试集不符合契约' }
```

`contract_valid` 表示结构和契约内跨字段约束有效；这一步不核对磁盘源文件，也不检查预期答案是否具有业务合理性。

## 4. 生成预检报告

```powershell
$day85Out = Join-Path '.\data\day85' ('plan-' + [Guid]::NewGuid().ToString('N'))
& .\experiments\day73\.venv\Scripts\python.exe -B .\experiments\day85\framework.py preview --output-dir $day85Out
if ($LASTEXITCODE -ne 0) { throw '预检失败，没有运行 Agent。' }
$day85Report = Get-Content (Join-Path $day85Out 'report.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$day85Report.summary | Format-List
$day85Report.rows | Format-Table case_id, execution_status, judgement
```

预期：

```text
total_cases: 2
not_run: 2
passed: 0
failed: 0
errors: 0
success_rate: null

monthly_report  not_run  not_evaluated
missing_period  not_run  not_evaluated
```

CLI 外层 `preflight_valid` 表示输入和四个声明文件的本地摘要已核对；报告的业务任务仍未执行。延迟、Token 和成本全部为 `null`，不是 0。源提交是声明信息，没有解析 Git 提交或联网核查标签。

输出目录必须不存在；即使里面只有上次失败的报告，也不会覆盖。使用自己的输入文件时传 `--agent` 与 `--dataset`，但仍只能选择当前契约支持的固定适配器和参数。

## 5. 校验报告与导出 Schema

```powershell
& .\experiments\day73\.venv\Scripts\python.exe -B .\experiments\day85\framework.py check --kind report --file (Join-Path $day85Out 'report.json')
if ($LASTEXITCODE -ne 0) { throw '报告契约校验失败' }

$day85Schemas = Join-Path '.\data\day85' ('schemas-' + [Guid]::NewGuid().ToString('N'))
& .\experiments\day73\.venv\Scripts\python.exe -B .\experiments\day85\framework.py schemas --output-dir $day85Schemas
```

导出 `agent.schema.json`、`dataset.schema.json`、`plan-report.schema.json`，便于后续编辑器或工具检查结构。唯一编号、来源摘要和跨字段语义仍由本 Python 校验器负责。

## 6. 理解三种“成功”

1. 命令退出码为 0：这次配置检查/预检操作完成。
2. Agent 业务任务完成：必须等后续 Runner 实际执行并产生证据。
3. 评测通过：还要把实际结果与全部预期条件比较。

本日只到第 1 步。不能把“报告文件生成成功”写成“Agent 成功率 100%”。预期拒绝也有可能是正确业务行为，Day 90 统计时需要明确分类与分母。

## 7. 自动化验证

```powershell
& .\experiments\day73\.venv\Scripts\python.exe -B -m pytest .\experiments\day85 -q
& .\experiments\day73\.venv\Scripts\python.exe -B -m pytest .\scripts\day84\test_v10_release.py -q
& .\experiments\day73\.venv\Scripts\python.exe -B -m ruff check .\experiments\day85
& .\experiments\day73\.venv\Scripts\python.exe -B .\scripts\day84\v10_gate.py
```

覆盖非法参数、重复编号、冲突断言、错误金额/布尔类型、输入大小、重复 JSON 键、输出保护、来源变化，以及不启动子进程或网络的保证。没有改动既有 Agent 实现；本日不重复执行此前发布时的全部 721 项测试，新增契约测试与发布保护回归分别记录。
