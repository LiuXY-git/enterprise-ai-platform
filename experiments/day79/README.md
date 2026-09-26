# Day 79：有边界的错误恢复

在 Day 73 的固定只读 MCP 查询流程上加入重试和回答降级，继续使用 Day 78 SQLite 任务日志。代码复用既有校验与日志，不修改 v0.5 冻结代码，也不修改 Day 78 代码。

## 1. 先复现“第一次失败、第二次成功”

使用已经安装的 Day 73 环境，在 PowerShell 执行：

```powershell
Set-Location 'C:\Users\Administrator\Desktop\enterprise-ai-platform'
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'

$day79Run = & .\experiments\day73\.venv\Scripts\python.exe -B .\experiments\day79\recovery_agent.py run --case monthly --scenario tool_timeout_once | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) { throw '场景未按预期完成，请查看任务日志。' }
$day79Run | ConvertTo-Json -Depth 8
```

预期：`status=completed`，销售额 `3000.00` 元，`logical_tool_calls=1`、`tool_attempts=2`、`mcp_dispatches=2`、`tool_retries=1`、`model_requests=0`。

这是明确标记的故障注入：第一次真实 MCP 只读查询已经完成，但测试入口丢弃它的有效回执，模拟超时后的未知结果；随后重新连接 MCP，以相同参数再查一次。这里不是制造真实网络故障，也不能推断第一次没有执行。

默认模型为 fixture，不请求 Qwen；MCP stdio 与虚构 SQLite 查询均真实执行。每次运行创建临时虚构销售库；日志保存在项目下 `data/day79/tasks.sqlite` 并保留，已被 Git 忽略。

若还没有 Day 73 环境，先按 [原安装步骤](../day73/README.md#1-安装独立环境)安装，无需新增依赖或更新容器。

## 2. 查看恢复过程

```powershell
& .\experiments\day73\.venv\Scripts\python.exe -B .\experiments\day79\recovery_agent.py show $day79Run.task_id
```

重点找以下事件：

1. `agent_decision` 的 `phase=policy`：本次采用的场景、次数上限和降级条件。
2. `tool_call` 的 `phase=attempt, attempt=1`：首次尝试。
3. `stage_error` 的 `stage=fault_injection`：丢弃已验证回执的教学注入。
4. `agent_decision` 的 `phase=recovery, action=retry`：允许重试，等待 200 毫秒。
5. `tool_call` 的 `attempt=2`：第二次尝试，相同 `T1` 逻辑调用和相同参数。
6. `tool_result`、`tool_feedback` 和 `final_answer`：取得有效结果后正常核对回答。

Day 78 的 `tool_call` 表示整个逻辑调用；Day 79 额外记录 `phase=attempt` 的实际尝试，不能把所有 `tool_call` 行简单相加当作工具执行次数。模型同样区分外层逻辑轮次与 `phase=attempt`。实际计数以最终事件的各字段为准；`mcp_dispatches` 表示主机发起调用的次数，并非每次服务端执行成功的证明。

新终端中可列出最近 100 个任务，再传入实际任务编号查看：

```powershell
& .\experiments\day73\.venv\Scripts\python.exe -B .\experiments\day79\recovery_agent.py list
& .\experiments\day73\.venv\Scripts\python.exe -B .\experiments\day79\recovery_agent.py show '替换成实际任务编号'
```

读取不会发起模型或 MCP 请求。自定义路径时将 `--log-db` 放在子命令前，运行和读取保持同一路径。

## 3. 观察“更换方案”

```powershell
& .\experiments\day73\.venv\Scripts\python.exe -B .\experiments\day79\recovery_agent.py run --case monthly --scenario report_timeout
```

这一场景先正常查询工具，然后模拟模型生成回答连续超时。最多尝试两次生成回答，仍失败时使用本次任务已通过校验的回执生成本地模板：

- `status=completed`，`degraded=true`。
- `stop_reason=receipt_template_fallback`，`recovery_reason=provider_timeout`。
- `answer_source=validated_receipt_fallback`。
- 回答前缀明确说明模型回答服务不可用、当前为本地模板结果。
- 只调用一次销售工具，不重新查询，不重新规划。

这里的完成仅指固定销售查询可以依据有效回执交付结果，不代表模型服务已经恢复。如果工具始终没有有效回执，就没有这种降级回答；不会生成假金额，也不会绕过 MCP 直接读取 SQL。

## 4. 对比其他场景

替换 `--scenario` 即可；这些教学故障只能与默认模拟模型一起使用。

| 场景 | 预期状态 | 作用 |
| --- | --- | --- |
| `normal` | `completed` | 正常查询，无重试、无降级 |
| `tool_timeout_once` | `completed` | 首次丢失回执，只读重试一次后成功 |
| `tool_timeout_always` | `failed` | 两次回执都丢失，停止，无金额答案 |
| `model_timeout_once` | `completed` | 首次模型调用超时，重试后正常执行 |
| `report_timeout` | `completed`，降级 | 回执有效，最终模型持续超时，改用本地模板 |
| `invalid_report` | `rejected` | 模型声称 9999.00 元，核对不一致，拒绝且不降级 |
| `invalid_arguments` | `rejected` | 模型提出越界年份，拒绝且不执行工具 |

以上状态以 `--case monthly` 为例。还有 `customer`、`empty`、`clarification` 三个 Day 73 场景：`empty + report_timeout` 降级后仍为 `no_data`；`clarification + normal` 为 `needs_clarification`，不调用工具。

例如观察次数耗尽：

```powershell
& .\experiments\day73\.venv\Scripts\python.exe -B .\experiments\day79\recovery_agent.py run --scenario tool_timeout_always
$LASTEXITCODE
```

预期退出码 `1`，这是该故障场景正确的停止结果。成功、无数据或澄清的退出码为 `0`；非法 CLI 参数为 `2`。查看失败任务的日志仍返回 `0`，代表读取成功。

## 5. 恢复策略与限制

| 错误 | 自动行动 |
| --- | --- |
| 固定只读工具的 `mcp_call_timeout` / `mcp_transport_error` | 等待 200 毫秒，重新连接并重新发现校验同一工具，最多重试一次 |
| 模型超时、网络错误、HTTP 502/503/504 | 保持输入不变，每个模型逻辑轮次最多重试一次 |
| 最终模型的上述错误两次耗尽，且有本次任务有效回执 | 切换本地结果模板，明确标记降级 |
| 参数越界、输出协议/回执异常、金额不一致、鉴权/配置错误、HTTP 429 | 停止，不自动重试或用模板掩盖错误 |
| MCP 连接、发现或关闭失败 | 停止；不将所有异常都判为瞬时错误 |
| 数据库快照变化 | 停止并丢弃答案，禁止降级 |
| 日志写失败 | 停止后续调用，保留先前日志供检查 |

整次任务最多两个模型逻辑轮次、每轮两次尝试，即最多四次模型请求尝试；最多一个逻辑销售查询、两次实际工具尝试。模拟模式的模型网络请求始终是 0。数据库在每次 MCP 交换前后以及完成前检查哈希，以约束同一份虚构数据。每次工具尝试使用新的连接和新的单次调用适配器，不通过重置旧适配器的计数绕过上限。

沿用 Day 73 的单次网络/工具超时；200 毫秒是教学用固定退避，没有总任务硬时限、指数退避、抖动或生产级限流策略。

## 6. 复跑验证和可选真实模型

```powershell
& .\experiments\day73\.venv\Scripts\python.exe -B -m pytest .\experiments\day64 .\experiments\day65\test_sales_sql.py .\experiments\day72\test_sales_mcp.py .\experiments\day73 .\experiments\day78 .\experiments\day79 -q
& .\experiments\day73\.venv\Scripts\python.exe -B -m ruff check .\experiments\day79
& .\experiments\day73\.venv\Scripts\python.exe -B .\scripts\day77\release_gate.py
```

如果 pytest 默认临时目录不可访问，可追加 `--basetemp` 指向一个全新的专用测试目录，不要使用个人文件目录。

只有显式指定 `--live` 才请求真实模型；本日验收没有运行下列命令：

```powershell
& .\experiments\day73\.venv\Scripts\python.exe -B .\experiments\day79\recovery_agent.py run --case monthly --live --env-file .\.env
```

`--live` 只能搭配 `--scenario normal`，避免把教学故障注入真实模型请求。发生真实瞬时模型错误时会按上限重试，可能产生额外模型费用；`model_requests` 报告客户端记录的实际请求次数，不代表服务端计费确认。

## 代码阅读顺序

1. [recovery_agent.py](recovery_agent.py) 的 `retry_allowed()`：明确允许重试的错误，不只写 `except: retry`。
2. `RecoverySales.query()`：固定次数、相同参数、错误日志、退避；仅用于本地已知的只读销售工具。
3. `McpTransport.exchange()`：新连接、新发现、已有 schema 与回执校验、快照检查。
4. `RecoveryChat`：模型请求重试，不把重复请求变成重复业务执行。
5. `run_recovery()`：回答降级条件以及最终日志事务。
6. [test_recovery.py](test_recovery.py)：次数上限、失败分类、日志失败、真实 MCP 和跨进程回放。

Day 79 的恢复发生在当前进程的一次任务内部。进程退出后，日志只可查看；重新执行 `run` 会新建任务，并非从检查点续跑。没有写入工具的幂等执行、多用户认证或人工审批。HITL 留给 Day 80，平台 API/Docker 未接入本实验。
