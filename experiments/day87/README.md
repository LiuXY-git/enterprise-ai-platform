# Day 87：自动执行测试集并保存证据

当前项目使用[统一评测入口](../../evaluation-center/README.md#运行评测)读取按周资料。下面运行命令已切换到该入口，阶段编号保持不变。

今天把 **测试集 → 固定 Agent 入口 → 执行记录** 接起来。先预检 Day 86 的 12 例数据，再逐例启动独立 Python 子进程；每例运行 Day 82 的 fixture 模型、真实本地 stdio MCP 和虚构 SQLite。不会请求 Qwen，不会批准或发送消息。

## 1. 准备环境

```powershell
Set-Location 'C:\Users\Administrator\Desktop\enterprise-ai-platform'
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
& .\experiments\day73\.venv\Scripts\python.exe -B .\experiments\day86\dataset_tool.py check
if ($LASTEXITCODE -ne 0) { throw '先修复测试集预检' }
```

使用 [Day 73 环境](../day73/README.md)。无需 Docker、API 密钥或启动平台 API。执行前还会检查 Agent Center v1.0 与历史冻结资产，失败时不启动 Agent。

## 2. 先运行四例 smoke

```powershell
$day87Smoke = Join-Path '.\data\day87' ('smoke-' + [Guid]::NewGuid().ToString('N'))
& .\experiments\day73\.venv\Scripts\python.exe -B .\scripts/evaluate.py --stage 87 run --suite smoke --timeout-seconds 60 --output-dir $day87Smoke
if ($LASTEXITCODE -ne 0) { throw '执行有异常；保留目录并查看 report.json' }
```

预期执行完成 4 例；业务状态为 completed 2 例、no_data 1 例、needs_clarification 1 例。

## 3. 运行全部十二例

```powershell
$day87Full = Join-Path '.\data\day87' ('full-' + [Guid]::NewGuid().ToString('N'))
& .\experiments\day73\.venv\Scripts\python.exe -B .\scripts/evaluate.py --stage 87 run --suite full --timeout-seconds 60 --output-dir $day87Full
$day87Exit = $LASTEXITCODE
$day87Report = Get-Content (Join-Path $day87Full 'report.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$day87Report.summary | Format-List
$day87Report.rows | Select-Object case_id, execution_status, @{Name='business_status';Expression={$_.observed.business_status}}, error | Format-Table
if ($day87Exit -ne 0) { Write-Warning '执行存在异常；按下方说明检查证据，不要覆盖或自动重跑原目录。' }
```

本次验收观察到 completed 业务状态 7 例、no_data 1 例、needs_clarification 1 例、failed 1 例、rejected 2 例。12 例的 **execution_status** 均为 completed，表示调用已结束并取得有效记录，不表示所有业务任务成功，也不是测试成功率 100%。

| 字段 | 含义 |
| --- | --- |
| execution_status | 是否成功取得这次执行记录；可为 completed/error/timeout/interrupted 等 |
| observed.business_status | Agent 实际返回的业务状态，保留失败、拒绝和澄清 |
| judgement | 固定为 not_evaluated；Day 90 才实现逐例判分 |
| metrics | 延迟、Token、成本目前均为 null；不能当成零消耗 |
| summary.success_rate | 目前为 null，不计算成功率 |

每例 worker 只收到 case_id、固定 case/scenario 和输出路径，**不会收到预期答案**。描述文件也不能指定命令、Python 文件或任意工具。`--agent` / `--dataset` 只能传入当前受限契约允许的描述。

## 4. 查看并核对证据

```powershell
& .\experiments\day73\.venv\Scripts\python.exe -B .\scripts/evaluate.py --stage 87 inspect --output-dir $day87Full
if ($LASTEXITCODE -ne 0) { throw '报告或证据不一致' }
Get-Content (Join-Path $day87Full 'cases\monthly_normal\artifacts\generation.json') -Raw -Encoding UTF8
Get-Content (Join-Path $day87Full 'cases\tool_exhausted\artifacts\events.json') -Raw -Encoding UTF8
```

目录结构：

```text
report.json                           # 输入快照、来源哈希、汇总、逐例状态
cases/<case_id>/result.json            # 本例执行记录与文件摘要
cases/<case_id>/worker-result.json     # 子进程实际观察，不含金标准
cases/<case_id>/stdout.log
cases/<case_id>/stderr.log
cases/<case_id>/artifacts/generation.json  # 回答、审批与实际模型输入
cases/<case_id>/artifacts/events.json      # 有序任务事件，含失败与重试
cases/<case_id>/artifacts/fictional.sqlite
cases/<case_id>/artifacts/tasks.sqlite
cases/<case_id>/artifacts/approvals.sqlite # 仅报告成功/空数据时存在
```

`inspect` 检查结构、快照摘要、逐例记录及文件哈希；不运行 Agent、不恢复任务、不判分。哈希属于本地完整性校验，不是数字签名，也不证明模型答案正确。整体输入快照位于 `plan`：它保留执行前的 not_run 状态；实际状态在外层 `rows`，不要误读内层计划。

## 5. 出错如何处理

- 单例进程退出异常、输出缺失或超时，记录 error/timeout，保留已写文件，随后处理下一例。
- 每例超时默认 60 秒，可设 5–120 秒。这是执行保护限额，不是 Day 88 的延迟指标。
- Windows 超时使用 taskkill 清理本例进程树；若权限拒绝，尝试停止直接子进程，记录 cleanup_failed 并中止整批，不宣称后代进程已清理。应先核对自己的残留进程，再在正常 PowerShell 中重试新目录。
- Ctrl+C 尽量清理子进程并记录 interrupted，后续保留 not_run。直接强杀控制进程可能留下 running 快照和部分文件；这表示未完成，不代表进程仍存活，也不触发自动恢复。
- 输出目录必须全新；输入有误不创建运行目录，运行中 I/O 故障保留最近快照。修复后新建目录；没有 resume 或自动重复执行功能。
- 退出码 0 表示整批拿到有效执行记录，1 表示配置/执行错误，130 表示中断。failed/rejected 的业务状态本身不会使 worker 退出非零。

## 6. 开发验证

```powershell
& .\experiments\day73\.venv\Scripts\python.exe -B scripts/evaluate.py --stage 87 test
if ($LASTEXITCODE -ne 0) { throw '回归测试未通过' }
```

超时清理测试仅终止测试自身创建的子进程树，需在允许 taskkill 的普通本地会话中执行。[交付与实测记录](../../docs/week-13.md#day87)。
