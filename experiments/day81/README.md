# Day 81：销售业务流程验收

将 Day 78 日志、Day 79 错误恢复与 Day 80 人工确认放到完整业务场景中验收：查询虚构销售数据 → 核对简报 → 等待审批 → 批准、拒绝、修改或过期 → 检查本地模拟执行记录。

本日提供固定场景清单、验收运行器和能检测错误结果的校验规则。没有新增任意目标规划、季度趋势分析或真实消息发送。默认模型为 fixture，真实执行 MCP stdio 与虚构销售查询。

## 1. 查看场景清单

在 PowerShell 执行：

```powershell
Set-Location 'C:\Users\Administrator\Desktop\enterprise-ai-platform'
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
& .\experiments\day73\.venv\Scripts\python.exe -B .\experiments\day81\sales_acceptance.py --list
```

复用 [Day 73 环境](../day73/README.md#1-安装独立环境)，不增加依赖。清单的 `goal` 是教学场景说明；实际执行仍由固定 `case` 和 `fault` 参数选择，不把说明当作任意自然语言 Agent 任务。

| 场景编号 | 验收重点 | 预期业务结果 |
| --- | --- | --- |
| `monthly_approve` | 全客户金额与审批 | 4 单、3000.00 元，模拟执行 1 次 |
| `customer_approve` | C001 范围隔离 | 2 单、1550.00 元，模拟执行 1 次 |
| `empty_approve` | 无数据不编造销售额 | 0 单、0.00 元，审批后模拟执行 1 次 |
| `clarification_stop` | 缺少年月 | 先澄清，不查工具、不创建审批 |
| `retry_approve` | 丢失首次回执 | 只读重试一次，审批后模拟执行 |
| `tool_exhausted` | 两次工具回执都丢失 | 任务失败，不创建审批 |
| `fallback_approve` | 最终模型持续超时 | 标记回执模板降级，仍需审批 |
| `invalid_arguments` | 模型提出越界年份 | 拒绝，不调用工具 |
| `invalid_report` | 模型声称错误金额 | 拒绝，不创建审批 |
| `human_reject` | 人工拒绝后尝试批准 | 保持拒绝，模拟执行 0 次 |
| `revision_approve` | 修改接收对象和备注 | 旧编号/旧内容摘要被拦截，新版本批准后执行 |
| `expired_approval` | 审批到期 | 不执行 |
| `duplicate_approval` | 重复批准 | 只有 1 条模拟记录 |
| `cross_task_approval` | 全客户和 C001 两项任务 | 不可混用审批摘要；批准客户任务不改变全客户待审批状态 |
| `parallel_approval` | 三个进程同时批准 | 只有 1 条模拟记录 |

批准/拒绝动作由验收程序在专用目录中模拟，目的是测试审批控制，不是声称发生了真实人工审核。需要自己逐步批准时，请使用 [Day 80 手动教程](../day80/README.md)。

## 2. 先运行一个场景

```powershell
$day81Out = Join-Path '.\data\day81' ('customer-' + [Guid]::NewGuid().ToString('N'))
& .\experiments\day73\.venv\Scripts\python.exe -B .\experiments\day81\sales_acceptance.py --scenario customer_approve --output-dir $day81Out
if ($LASTEXITCODE -ne 0) { throw '场景验收未通过，请查看报告和 trace.json。' }
```

输出目录必须是新目录。已存在时直接拒绝，不覆盖旧报告或修改旧任务。每个场景都在自己的子目录运行 Day 80 CLI，多次命令是独立进程。

## 3. 运行全部 15 个场景

```powershell
$day81Out = Join-Path '.\data\day81' ('all-' + [Guid]::NewGuid().ToString('N'))
& .\experiments\day73\.venv\Scripts\python.exe -B .\experiments\day81\sales_acceptance.py --output-dir $day81Out
if ($LASTEXITCODE -ne 0) { throw '部分场景未通过，请检查 report.json。' }
```

运行时逐项显示场景结果。涉及多个 MCP 子进程和审批命令，完整运行通常需要数分钟，具体取决于本机环境；每个子命令最多等待 60 秒。

`model_requests=0`、`real_messages_sent=0`。工具超时是 Day 79 明确标记的故障注入，不是本次观察到真实服务故障。审批“发送”只向本地 SQLite 写入记录。

## 4. 读懂报告

```powershell
$day81Report = Get-Content (Join-Path $day81Out 'report.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$day81Report.results | Format-Table id, status, generation_status, simulated_effects
```

这里有三个不同概念：

| 字段 | 含义 |
| --- | --- |
| `status` | 验收是否符合预期：`passed` / `failed` |
| `generation_status` | 业务生成结果：完成、无数据、澄清、失败或拒绝 |
| `simulated_effects` | 该场景最终应有且已核对的本地模拟发送记录数 |

例如 `tool_exhausted` 应当显示验收 `passed`、生成 `failed`、模拟执行 `0`。它证明失败时正确停止，不表示销售任务已成功完成。报告总体通过要求所有选定场景符合各自预期；任何不匹配都会返回非零退出码。

## 5. 查看完整证据

每次输出包含：

```text
report.json
customer_approve/
  trace.json
  data/tasks.sqlite
  data/approvals.sqlite
```

`trace.json` 保存该场景定义、独立进程命令及响应、生成结果、执行前审批数据库快照、执行后审批/日志/模拟记录快照和最终验收结果。失败场景可能没有审批数据库；这是预期的零审批路径。

查看客户场景的证据：

```powershell
Get-Content (Join-Path $day81Out 'customer_approve\trace.json') -Raw -Encoding UTF8
```

代码中的校验会核对以下内容：

- 金额和订单数与清单中的固定预期一致；全量合计不被截断明细的小计替代。
- 客户、月份、查询参数和来源引用对应当前任务。
- 审批正文与已校验回答一致，内容摘要覆盖当前待执行内容。
- 实际数据库在批准前没有模拟记录；终态与 CLI 返回一致。
- 每条模拟记录都有且只有一次对应批准，批准的内容摘要与实际记录一致。
- 重试次数在边界内；模板降级有明确标签，失败和澄清不会进入审批。

这些检查直接读取 CLI 输出和只读数据库快照，不调用生产代码的 `expected_report()` 或 `render()` 来生成期望答案。另有反向测试主动改错金额、订单、客户范围、引用、正文、批准记录等，确认验收能失败。

## 6. 复跑自动化测试

```powershell
& .\experiments\day73\.venv\Scripts\python.exe -B -m pytest .\experiments\day81 -q
& .\experiments\day73\.venv\Scripts\python.exe -B -m pytest .\experiments\day64 .\experiments\day65\test_sales_sql.py .\experiments\day72\test_sales_mcp.py .\experiments\day73 .\experiments\day78 .\experiments\day79 .\experiments\day80 -q
& .\experiments\day73\.venv\Scripts\python.exe -B -m ruff check .\experiments\day81
& .\experiments\day73\.venv\Scripts\python.exe -B .\scripts\day77\release_gate.py
```

两组 pytest 的测试不重叠：Day 81 新增验收检查与既有回归分开报告。新增测试中完整场景只运行一次，再检查不同场景与错误结果；不是每条反向测试都重新请求 MCP。pytest 临时目录不可用时，指定一个新的专用 `--basetemp` 目录。

## 7. 代码与能力边界

- [scenarios.json](scenarios.json)：版本化的场景、动作和独立业务预期。
- [sales_acceptance.py](sales_acceptance.py)：场景执行、业务结果校验、审批数据库核对及报告。
- [test_sales_acceptance.py](test_sales_acceptance.py)：15 个场景、反向校验、场景格式检查及输出保护。

今天的“复杂”体现为多阶段和多种失败/审批分支，并非任意销售目标的自动规划，也没有新增趋势预测、多工具商业分析或真实企业数据接入。没有优化生产 Prompt、没有真实 Qwen 验收、没有真实审批身份认证或对外发送；Day 82 将另行处理 Prompt 优化。本次保留 Days 78–80 和 v0.5 的实现不变。
