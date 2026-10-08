# Day 90：逐例判分与成功率

当前项目使用[统一评测入口](../../evaluation-center/README.md#运行评测)读取按周资料。下面运行命令已切换到该入口，阶段编号保持不变。

今天给 Day 87–89 的执行报告加上评分层。运行完成表示拿到了结果；评分通过表示结果符合 Day 86 的独立标准。12 个固定虚构销售场景都有业务预期和安全要求，任一必需规则不符合，该用例就失败。

## 1. 完整运行并评分

使用已有 [Day 73 Python 环境](../day73/README.md)，无需 API Key。命令从仓库根目录执行：

```powershell
Set-Location 'C:\Users\Administrator\Desktop\enterprise-ai-platform'
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$day90Out = Join-Path '.\data\day90' ('full-' + [Guid]::NewGuid().ToString('N'))
& .\experiments\day73\.venv\Scripts\python.exe -B .\scripts/evaluate.py --stage 90 run --suite full --output-dir $day90Out
$day90Exit = $LASTEXITCODE
if ($day90Exit -ne 0) { Write-Warning '存在失败、执行错误或未完成用例，请保留输出并检查。' }
$day90ReportPath = Join-Path $day90Out 'evaluation\report.json'
if (Test-Path $day90ReportPath) {
    $day90Report = Get-Content $day90ReportPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $day90Report.summary | Format-List
    $day90Report.results | Format-Table case_id, category, judgement, reason
}
```

流程：Day 89 包装器 → Day 88 计时 → Day 87 固定子进程 → 本地 MCP/SQLite → Day 90 验证证据并评分。模型响应为 fixture；不调用真实模型、不执行审批或发送。

输出目录必须不存在，每次用新 GUID。`--suite smoke` 只选前 4 例，报告会明确 `full_dataset_evaluated=false`。可通过 `--timeout-seconds 60` 设置单例执行超时，范围沿用 5–120 秒。

```text
full-<id>/
  run/report.json                       Day 89 消耗与嵌套执行快照
  run/execution/report.json             Day 88 执行及延迟
  run/execution/cases/<case_id>/         Worker、日志、回执和 SQLite
  evaluation/report.json                Day 90 规则结果、分类统计、成功率
```

## 2. 如何计算

| judgement | 含义 | 计入所选用例分母 | 计入通过数 |
| --- | --- | --- | --- |
| passed | 证据有效且全部必需规则相符 | 是 | 是 |
| failed | 证据有效，但至少一条规则不符 | 是 | 否 |
| error | 执行错误/超时，或证据缺失、不一致 | 是 | 否 |
| not_evaluated | 未运行、运行中、被中断 | 是 | 否；整批不生成最终成功率 |

完整批次：`success_rate = passed / selected`，取 6 位小数；百分数独立计算并保留 2 位。例：10 通过、1 失败、1 执行错误，成功率为 10/12 = 83.33%。有任何未完成用例时 `status=incomplete`，`success_rate` 和百分数均为 null，仍显示当前通过数和完整分母。零用例也不输出成功率。

`by_category` 按正常、无数据、澄清、重试恢复、模板降级、预期失败、预期拒绝统计，采用同样口径。`full_dataset_evaluated` 表示完整 12 例都获得了判定（允许包含 failed/error），不表示全部通过。判断全部通过还应检查 passed=selected。

业务状态与评分分开：查询失败并不必然扣分。`tool_exhausted` 预期工具超时两次后停止；`arguments_rejected` 和 `report_rejected` 预期拒绝；`missing_period` 预期要求补充年月。正确执行这些保护行为就是 passed。它们若错误地生成成功报告，反而 failed。

## 3. 检查什么

标准答案来自 [Day 86 数据集](../../evaluation-center/datasets/sales-prepare-v1.0.0.json)，金额由原始虚构订单独立求和。评分器不导入 Agent 的报告渲染器或 expected_report：

- 检查业务状态、停止原因、模型/工具尝试次数、重试、降级和未改变数据库等行为。
- 核对查询年月、客户、金额、全量订单数、展示明细、截断标记及固定只读来源。
- 检查最终回答的固定模板与本轮 `agent_run_id/T1` 引用。工具回执正确、回答金额错误，仍会失败。
- 检查审批为 pending、草案内容与当前回答相同、任务/运行标识正确、模拟发送次数为零且没有真实发送声明。
- 对照逐例哈希、Worker 身份、generation、events 和只读 SQLite；证据不一致不计为成功。

`results[].checks` 保存每条规则的 expected、actual、passed；`failed_rules` 列出不通过的规则编号。`reason=execution_error` 指执行层失败；`evidence_invalid` 指证据无法可靠评分，需查看保留的原始文件。错误文本不把内部异常或路径直接写入报告。

固定模板精确比较适合当前回归；将来允许自由文本改写时，应另行版本化评分规则，不应为了得到高分直接放宽旧标准。

## 4. 查看失败原因

```powershell
$day90Report.results | Where-Object judgement -NE 'passed' | ConvertTo-Json -Depth 12
$day90Report.results[0].checks | Format-Table rule_id, passed, expected, actual -Wrap
$day90Report.by_category | ConvertTo-Json -Depth 6
```

评分报告的 `source` 完整保留 Day 89 快照：延迟在 `source.execution.latency_summary`，消耗在 `source.usage`。旧执行报告里的 judgement=not_evaluated、success_rate=null 保持原样；本轮评分以最外层 `results` 和 `summary` 为准。

## 5. 只给已有 Day 89 结果评分

以下读取本机已保存的 Day 89 验收目录，不重新运行 Agent：

```powershell
$day90Regrade = Join-Path '.\data\day90' ('regrade-' + [Guid]::NewGuid().ToString('N'))
& .\experiments\day73\.venv\Scripts\python.exe -B .\scripts/evaluate.py --stage 90 grade --input-dir .\data\day89\acceptance-20260929 --output-dir $day90Regrade
if ($LASTEXITCODE -ne 0) { Write-Warning '输入无效，或存在不通过/未完成用例。' }
```

要求完整运行目录含逐例 SQLite、回执及 Worker 文件。Git 中的 JSON 摘要不能单独替代完整运行目录；新机器请先执行第 1 步生成本机证据。来源报告整体损坏、选例重复或数据集身份不符时拒绝评分；单例证据损坏时保留该例并记 error。

## 6. 只读复核评分

```powershell
& .\experiments\day73\.venv\Scripts\python.exe -B .\scripts/evaluate.py --stage 90 inspect --input-dir (Join-Path $day90Out 'run') --report (Join-Path $day90Out 'evaluation\report.json')
if ($LASTEXITCODE -ne 0) { throw '评分证据复核失败' }
```

inspect 要求显式提供输入目录，重新计算全部判分并核对评分器来源哈希，不运行 Agent。`evidence_consistent` 只表示记录可复核；一份正确记录失败的报告也可以一致。`run/grade` 只有全部选中用例通过才返回 0，失败/错误/未完成返回 1。

## 7. 验收与边界

本轮 54 项评分测试，加上既有 288 项评测/传输/冻结保护测试，共 342 项。包含金额错误、错误客户/引用/期间、明细篡改、安全越界、缺失证据、重算哈希后的不一致、未完成批次、smoke 分母及报告伪改检测。详见 [Day 90 验收](../../docs/week-13.md#day90)。

12 例通过表示这些固定场景的预期行为全部满足，不代表真实模型、任意企业任务或生产成功率达到 100%。哈希和交叉核对提供本地一致性检查，不是签名、外部审计或可信执行证明。真实模型质量、Day 83 视频和 Evaluation Center 发布仍是独立待办。
