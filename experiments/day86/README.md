# Day 86：设计并预检正式测试集

本次补齐上次中断后尚未提交的 Day 86 工作，并与 Day 87 一起交付。先阅读[分类和独立答案](../../evaluation-center/datasets/README.md)。

## 1. 检查测试集

复用 Day 73 Python 环境，不增加依赖。新机器见 [Day 73](../day73/README.md)。

```powershell
Set-Location 'C:\Users\Administrator\Desktop\enterprise-ai-platform'
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
& .\experiments\day73\.venv\Scripts\python.exe -B .\experiments\day86\dataset_tool.py check
if ($LASTEXITCODE -ne 0) { throw '测试集预检失败' }
```

预期 `dataset_valid`、12 例、smoke 4 例。检查重复用例、分类、范围、严格类型、预期字段、7 个来源摘要，以及订单独立加总。这里只检查输入，没有执行 Agent。

## 2. 生成预检计划

```powershell
$day86Out = Join-Path '.\data\day86' ('plan-' + [Guid]::NewGuid().ToString('N'))
& .\experiments\day73\.venv\Scripts\python.exe -B .\experiments\day86\dataset_tool.py preview --suite full --output-dir $day86Out
if ($LASTEXITCODE -ne 0) { throw '计划生成失败' }
$day86Plan = Get-Content (Join-Path $day86Out 'report.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$day86Plan.summary | Format-List
```

`total_cases=12`、`not_run=12`、`success_rate=null`；每例 `not_evaluated`，所有指标为 null。换 `--suite smoke` 选择四例；每次使用新目录，不覆盖旧报告。

可用 `schemas --output-dir 新目录` 导出 dataset 与 plan-report JSON Schema。JSON Schema 只覆盖结构；来源摘要、独立金额和场景间约束还需要 CLI 预检。

本集不直接兼容 Day 85 的两个示例契约。下一步：[Day 87 自动执行](../day87/README.md)。
