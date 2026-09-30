# Day 88：测量每例执行延迟

在 Day 87 执行器外增加单调时钟计时，继续使用 Day 86 的固定测试集、Day 82 fixture 模型和真实本地 stdio MCP。旧版代码与历史报告保持不变，新入口生成 `day88-latency-v1` 报告。

## 1. 运行

沿用 [Day 73 环境](../day73/README.md)，不增加依赖，无需 API 密钥或启动 Docker。

```powershell
Set-Location 'C:\Users\Administrator\Desktop\enterprise-ai-platform'
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$day88Out = Join-Path '.\data\day88' ('full-' + [Guid]::NewGuid().ToString('N'))
& .\experiments\day73\.venv\Scripts\python.exe -B .\experiments\day88\runner.py run --suite full --timeout-seconds 60 --output-dir $day88Out
$day88Exit = $LASTEXITCODE
if ($day88Exit -ne 0) { Write-Warning '本次有执行异常，保留输出并检查 report.json。' }
```

`--suite smoke` 只运行四例；full 运行十二例。每次使用新目录，已有目录不会覆盖。执行前核对数据、来源摘要与冻结资产；真实模型请求为 0，没有批准或发送入口。

## 2. 看懂单例耗时

```powershell
$day88Report = Get-Content (Join-Path $day88Out 'report.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$day88Report.rows | Select-Object case_id, execution_status, @{Name='business_status';Expression={$_.observed.business_status}}, @{Name='latency_ms';Expression={$_.metrics.latency_ms}}, @{Name='measurement';Expression={$_.metrics.measurement}} | Format-Table
```

`metrics.elapsed_ns` 保存整数纳秒，`latency_ms` 换算成毫秒并保留三位小数。使用 `time.perf_counter_ns()` 计算同一父进程中的开始/结束差值，不使用系统日期相减，系统时钟校正不会改变持续时间。

计时从调用 Day 87 `execute_case` 前开始，到它返回后结束：

- 包含本例目录创建、子进程启动及导入、虚构数据库准备、MCP 连接/查询、fixture 回答、全部尝试、重试退避、审批准备、子进程退出。
- 包含原执行器的 stdout/stderr、证据读取、哈希和基础 result.json 写入。
- 超时/中断时包含已发生的等待和清理时间。因此观测耗时可能超过 `--timeout-seconds`，后者限制的是子进程等待，不是精确耗时上限。
- 不含整批预检、等待前面的用例、汇总报告更新，也不含 Day 88 补写计时字段的第二次 result.json 写入。

这是**父进程观察到的单例总耗时**，不是纯模型响应时间、网络延迟或 API TTFT。不单独推算某次重试的耗时；已有 tool_retries/model_retries 说明发生了几次重试，总计时自然覆盖所有尝试和等待。

## 3. 查看统计

```powershell
$day88Report.latency_summary.by_execution_status.completed | Format-List
$day88Report.latency_summary.by_execution_status.timeout | Format-List
$day88Report.latency_summary.by_business_status | ConvertTo-Json -Depth 5
```

每组包含 samples、min_ms、mean_ms、p50_ms、p95_ms、max_ms。按 execution_status 分组，只有取得完整执行记录的用例进入 completed 组；error、timeout、interrupted 各自成组，绝不混入完整样本的均值。

completed 组仍包含业务 failed/rejected：这些 Agent 已经正常结束并留下有效记录。另按 business_status 分组，便于区分正常报告与快速拒绝。当前没有评分器，不能将 completed 组称为“答对题目的平均耗时”。

百分位使用 nearest-rank：排序后取第 `ceil(p × n)` 项，序号从 1 开始。12 个样本的 P95 就是最大值，小样本不能用于服务 SLA 或性能稳定性结论。

`sum_case_elapsed_ms` 是已观测单例耗时之和，不是整批墙钟时间；`measured_cases` 和 `unmeasured_cases` 说明样本覆盖。

| 状态 | 计时表现 |
| --- | --- |
| completed | complete_case，完整单例耗时 |
| error/timeout | partial_case，截止失败处理结束的观测时间，不是任务完成时间 |
| interrupted | 能取得时钟差时为 partial_case；在计时区间外中断可为 null |
| not_run/running | not_measured，耗时为 null，不能补成 0 |
| 没有样本的统计组 | samples=0，均值/百分位等均为 null |

## 4. 检查证据

```powershell
& .\experiments\day73\.venv\Scripts\python.exe -B .\experiments\day88\runner.py inspect --output-dir $day88Out
if ($LASTEXITCODE -ne 0) { throw '执行记录、计时统计或证据哈希不一致' }
```

inspect 只读：重新核对纳秒/毫秒换算、统计分组、百分位、输入快照、逐例记录与证据文件摘要，不执行或恢复 Agent。目录结构沿用 [Day 87](../day87/README.md)，每例增加计时字段。旧版 Day 87 报告继续使用旧 inspector；没有对旧日志补造延迟。

超时、清理权限、中断、输出目录保护和退出码沿用 Day 87。直接强杀宿主或磁盘写入失败可能留下 running 快照；它既不是完成记录，也不表示进程仍存活。修复后使用新目录。

## 5. 如何利用结果

可以先找出本轮最慢的场景，再对照事件日志查看工具重试、模型重试或审批准备。比较代码版本时应保持测试集、解释器、机器、后台负载和计时范围一致，并重复多轮；本次单轮结果只是一份本机观测，不证明优化收益。

Token、成本和成功率仍为 null，分别留给 Day 89、Day 90。模型为 fixture，本地 MCP 和进程启动占有实际耗时，不代表 Qwen 的线上速度。

开发验证：

```powershell
& .\experiments\day73\.venv\Scripts\python.exe -B -m pytest .\experiments\day88\test_latency.py -q -p no:cacheprovider
if ($LASTEXITCODE -ne 0) { throw '延迟测试未通过' }
```

[交付与验收](../../docs/week-13-notes.md#day88)。
