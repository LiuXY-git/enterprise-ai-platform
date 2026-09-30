# Day 82：Agent Prompt 优化与对照验收

目标：让模型更清楚地知道何时查工具、报告字段从哪里取、什么时候停止。代码仍负责参数校验、回执核对和人工审批。Prompt 改得更详细，不等于已经证明模型准确率提高。

## 1. 今天修改了什么

| 内容 | baseline（Day 73） | candidate（Day 82） |
| --- | --- | --- |
| 查询顺序 | 简要描述先调用一次工具 | 分成无回执、已有回执两个阶段 |
| 报告字段 | 列出 JSON 格式 | 逐字段映射到 arguments、result、receipt_id |
| 易错点 | 全量金额不同于明细小计 | 额外区分订单总数、展示条数、截断标志与无数据 |
| 越权文字 | 工具资料不是指令 | 明确用户附加要求和数据不能扩大固定查询范围 |
| 执行动作 | 禁止写入和通知 | 明确报告生成不等于批准或发送，重试/降级由宿主决定 |

新版全文：[candidate.md](candidate.md)。基线直接读取冻结的 Day 73 `SYSTEM`，两版均记录正文 SHA-256 和字符数；字符数不是 token 数。为了保留发布资产，未修改 Day 73 或 Days 78–81 的代码。

`PromptChat` 在实际调用模型前替换 system 内容，保持工具定义、tool_choice、回执和模型返回不变，并记录实际转交的输入。它没有把错误模型答案改写成正确答案。现有 Day 80 CLI 仍用原版；要体验新版请使用本目录入口。

## 2. 环境与样例

复用 [Day 73 独立环境](../day73/README.md)，不增加依赖。

```powershell
Set-Location 'C:\Users\Administrator\Desktop\enterprise-ai-platform'
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
& .\experiments\day73\.venv\Scripts\python.exe -B .\experiments\day82\prompt_lab.py list
```

[cases.json](cases.json) 包含 16 个固定样例：

- 4 个基础查询：全客户、指定客户、无数据、缺少年月。
- 4 个附加干扰要求：编造金额、扩大客户范围、虚构增长率、绕过批准发送。
- 8 个故意错误的模型输出：无回执回答、错范围、多次调用、回填后继续调用、错金额、错引用、Markdown 包裹 JSON、取消虚构标记。

这里不是任意自然语言任务规划。基础查询与允许的范围已由宿主固定；附加文字用于测试冲突要求。

## 3. 运行离线对照

```powershell
$day82Out = Join-Path '.\data\day82' ('replay-' + [Guid]::NewGuid().ToString('N'))
& .\experiments\day73\.venv\Scripts\python.exe -B .\experiments\day82\prompt_lab.py evaluate --output-dir $day82Out
if ($LASTEXITCODE -ne 0) { throw '离线对照未通过，请查看 report.json 和对应 trace。' }
Get-Content (Join-Path $day82Out 'report.json') -Raw -Encoding UTF8
```

两版分别运行 16 个样例，共 32 次流程运行，真实启动本地 MCP，使用虚构销售数据库。对照按样例交替先运行 baseline 或 candidate，彼此没有共享聊天历史。输出目录必须不存在，失败或中断的旧目录也不会覆盖。

**离线模型收到两版 Prompt，但返回相同的脚本回答；它不理解 Prompt。** 因此该对照验证接入和程序边界，两版通过数相同是正常现象。报告明确标记 `mode=scripted_replay`、`prompt_quality_comparison=not_measured`，不能用它声称幻觉率下降。

输出包含 `report.json`、每个样例/版本的 JSON trace，以及本地 `fictional.sqlite`。每条 trace 保存实际模型输入、模型输出、回执、校验结果和 Prompt 摘要；汇总在每条完成后保存，中断时保持 `status=running`，不能当作完整通过。

预期拒绝的样例只有被正确拦截才算测试通过。例如 `reject_wrong_total` 的 `passed=true`、业务 `status=rejected`，表示错误金额未成为正式回答。

## 4. 体验新版与人工审批衔接

```powershell
$day82Task = Join-Path '.\data\day82' ('task-' + [Guid]::NewGuid().ToString('N'))
& .\experiments\day73\.venv\Scripts\python.exe -B .\experiments\day82\prompt_lab.py prepare --case monthly --output-dir $day82Task
if ($LASTEXITCODE -ne 0) { throw '生成未成功，请检查 generation.json。' }
```

此命令使用新版 Prompt + 模拟模型 + 真实 MCP，复用 Day 79 的日志、重试与降级，再复用 Day 80 创建 `pending` 审批。它不会自动批准，没有真实消息发送。

目录中的 `generation.json` 保存结果和实际模型输入；`tasks.sqlite` 保存任务日志；符合条件时生成 `approvals.sqlite`。可以把该目录传给 Day 80 CLI 继续手工确认：

```powershell
$day82Result = Get-Content (Join-Path $day82Task 'generation.json') -Raw -Encoding UTF8 | ConvertFrom-Json
& .\experiments\day73\.venv\Scripts\python.exe -B .\experiments\day80\hitl_agent.py --data-dir $day82Task show $day82Result.approval.approval_id
```

认真查看正文、接收对象和摘要后，按 [Day 80 教程](../day80/README.md) 手动批准或拒绝。默认 30 分钟过期；批准也只是写入本地模拟记录。

学习恢复分支时，使用新的输出目录，把 `prepare` 加上 `--scenario tool_timeout_once`、`--scenario report_timeout` 或 `--scenario invalid_report`。最后一种预期被拒绝并返回非零退出码，不创建审批。

## 5. 可选的真实模型对照

本次交付未运行真实 Qwen 对照；新版仍是候选 Prompt。以下命令由你选择执行，会产生模型请求与费用，但不创建审批或发送消息。

先只运行一个月度查询的双版本对照：

```powershell
$day82Live = Join-Path '.\data\day82' ('live-' + [Guid]::NewGuid().ToString('N'))
& .\experiments\day73\.venv\Scripts\python.exe -B .\experiments\day82\prompt_lab.py evaluate --live --case-id monthly --env-file .\.env --output-dir $day82Live
```

单个样例最多 4 次模型尝试（两版各最多两轮），没有自动重试。`--env-file` 仅在 `--live` 下有效，凭证由既有配置读取，不写入报告。

去掉 `--case-id monthly` 可运行 8 个真实模型适用样例：基础查询与附加干扰要求，两版共最多 32 次尝试。故意错误输出的 8 个回放样例不用于真实模型对照。每个请求使用既有 ChatTools 的超时、响应大小和输出 token 上限。

评价时查看两版 `summary`、每例 `errors`、`stop_reason` 和实际输入/输出。只有正常生成的金额、客户范围、字段和引用均正确才通过；仅被程序拦截并不算回答成功。服务错误也算未通过，不能与模型质量错误混为一谈，应查看明细。两版同样低分时，不应靠放宽校验提高通过率。

报告记录模型返回的 provider/model，但一次小样本没有统计显著性，模型服务也有随机性；不把单次分差解释成普遍提升。若需判断改进效果，应在相同配置下用新目录重复对照，并把未参与修改 Prompt 的样例留作后续检验。本日没有自动晋升 candidate 为默认版本。

## 6. 自动化验收

```powershell
& .\experiments\day73\.venv\Scripts\python.exe -B -m pytest .\experiments\day82 -q
& .\experiments\day73\.venv\Scripts\python.exe -B -m pytest .\experiments\day64 .\experiments\day65\test_sales_sql.py .\experiments\day72\test_sales_mcp.py .\experiments\day73 .\experiments\day78 .\experiments\day79 .\experiments\day80 .\experiments\day81 -q
& .\experiments\day73\.venv\Scripts\python.exe -B -m ruff check .\experiments\day82
& .\experiments\day73\.venv\Scripts\python.exe -B .\scripts\day77\release_gate.py
```

新增测试包含双版本回放、实际输入检查、错误结果反向校验、请求预算与输出保护，以及新版接入恢复和待审批的流程。既有 Day 81 的 15 场景回归仍验证原版流程；不要把这部分说成已用新版替换后重跑。新版独立集成测试另行验证 9 个组合。验收详情见 [Day 82 交付说明](../../docs/week-12-notes.md#day82)。
