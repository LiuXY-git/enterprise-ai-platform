# Day 78：Agent 任务日志

在 Day 73 的固定 MCP 查询流程外加日志适配器。运行一次任务，会把用户请求、可观察的决策、工具调用与结果、回填关联和最终回答逐条保存到 SQLite。每条事件有任务编号、序号、UTC 时间和相对启动毫秒数。

默认是模拟模型 + 真实 MCP stdio + 临时虚构销售库，不消耗模型额度。继续复用 Day 73 独立环境和锁定依赖，不修改 v0.5 冻结代码。

## 1. 运行并取得任务编号

在 PowerShell 运行：

```powershell
Set-Location 'C:\Users\Administrator\Desktop\enterprise-ai-platform'
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'

$day78Run = & .\experiments\day73\.venv\Scripts\python.exe -B .\experiments\day78\logged_agent.py run --case monthly | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) { throw '任务未成功，请查看日志列表。' }
$day78Run | ConvertTo-Json -Depth 8
```

预期 `status=completed`，回答包含虚构销售额 `3000.00` 元、4 单和来源引用。`model_requests=0`；`mcp_tool_attempts=1`；`database_unchanged=true`。记下 `task_id`。

默认日志文件是项目根目录的 `data/day78/tasks.sqlite`，已被 Git 忽略。它与一次性创建的虚构销售库是两个数据库：销售库退出后删除，任务日志保留。

若 Day 73 环境尚不存在，先按 [Day 73 安装步骤](../day73/README.md#1-安装独立环境)创建。无需升级平台 API 环境。

## 2. 按顺序查看日志

```powershell
& .\experiments\day73\.venv\Scripts\python.exe -B .\experiments\day78\logged_agent.py show $day78Run.task_id
```

正常销售查询有 11 条事件：

| 事件 | 学习时观察什么 |
| --- | --- |
| `user_request` | 当前固定场景和请求范围，标记虚构数据 |
| `discovery_started` / `discovery_result` | 开始发现工具、完成本地 schema 校验 |
| `model_started` | 第几次调用模型接口；模拟模式也有此事件，但不发网络请求 |
| `agent_decision` | 模型提出调用工具或回答；`validation=pending`，尚未批准 |
| `tool_call` | 参数与场景范围检查通过后，先记录 `T1` 调用意图，再执行 |
| `tool_result` | 已校验的金额、订单数、明细条数及截断标记 |
| `tool_feedback` | 把 `T1` 对应的回执放入下一轮输入；不是服务端收到请求的证明 |
| 第二次 `model_started` / `agent_decision` | 根据回执提出回答；仍需结果校验 |
| `final_answer` | 最终状态、通过校验的模板回答、停止原因、实际请求次数 |

`task_id` 是日志任务编号；`agent_run_id` 是 Day 73 内部编号。`tool_feedback.receipt_id` 为 `agent_run_id/T1`，与最终答案的引用对应。同一场景每次运行生成新任务，不覆盖旧记录。

## 3. 新终端中查看与回放

关闭终端后重新打开，进入项目并设置上述 UTF-8 环境变量，然后列出最近 100 个任务：

```powershell
& .\experiments\day73\.venv\Scripts\python.exe -B .\experiments\day78\logged_agent.py list
```

将列表里的实际 `task_id` 传给 `show`：

```powershell
& .\experiments\day73\.venv\Scripts\python.exe -B .\experiments\day78\logged_agent.py show '替换成实际任务编号'
```

`list` / `show` 使用 SQLite 只读连接，不创建缺失数据库，不连接 MCP，不调用模型。这里的“回放”是查看已保存的事件，不会重新执行工具，也不会从中断处继续任务。

自定义日志文件时，`--log-db` 必须放在子命令前；运行和查看使用同一路径：

```powershell
& .\experiments\day73\.venv\Scripts\python.exe -B .\experiments\day78\logged_agent.py --log-db .\data\day78\practice.sqlite run --case empty
& .\experiments\day73\.venv\Scripts\python.exe -B .\experiments\day78\logged_agent.py --log-db .\data\day78\practice.sqlite list
```

## 4. 对比四种场景

| `--case` | 预期状态 | 工具调用次数 | 关键结果 |
| --- | --- | --- | --- |
| `monthly` | `completed` | 1 | 全客户 4 单，3000.00 元，明细只展示 2 条 |
| `customer` | `completed` | 1 | C001 共 2 单，1550.00 元 |
| `empty` | `no_data` | 1 | 0 单，0.00 元 |
| `clarification` | `needs_clarification` | 0 | 缺少年月，先澄清；仍会发现工具 |

例如：

```powershell
& .\experiments\day73\.venv\Scripts\python.exe -B .\experiments\day78\logged_agent.py run --case clarification
```

观察这个任务只有 6 条事件，没有 `tool_call`、`tool_result` 或 `tool_feedback`。提出工具调用但未通过参数校验的任务也不会产生真正的工具调用事件。

## 5. 如何读失败日志

- `stage_error` 表示模型、发现、工具、连接或关闭阶段异常。只记阶段，不写原始异常文本。
- `final_answer.status=rejected` 表示模型协议、范围或回答校验未通过；通过 `stop_reason` 定位。
- 工具超时后，记录调用及错误；执行结果保持未知，不宣称“肯定没执行”，也不自动重试。
- 最终状态与 `final_answer` 在同一事务中提交，避免任务显示完成但找不到最终事件。
- 日志写失败时，不再启动后续模型或工具操作；如果工具已经执行，则保留此前事件，不会把未落盘的结果展示为成功。
- `running_or_interrupted` 表示尚无最终事件：任务可能仍在运行，也可能进程已退出。仅凭日志无法区分，不能把它解释为已完成或已恢复。

## 6. 测试与可选真实模型

```powershell
& .\experiments\day73\.venv\Scripts\python.exe -B -m pytest .\experiments\day64 .\experiments\day65\test_sales_sql.py .\experiments\day72\test_sales_mcp.py .\experiments\day73 .\experiments\day78 -q
& .\experiments\day73\.venv\Scripts\python.exe -B -m ruff check .\experiments\day78
& .\experiments\day73\.venv\Scripts\python.exe -B .\scripts\day77\release_gate.py
```

若 pytest 默认临时目录不可访问，可追加 `--basetemp` 指向一个新建的专用测试目录；不要指定存放个人文件的目录，pytest 会管理该目录。

真实模型仅在显式加 `--live` 时启用，读取既有 Qwen 配置，正常流程最多两次模型请求：

```powershell
& .\experiments\day73\.venv\Scripts\python.exe -B .\experiments\day78\logged_agent.py run --case monthly --live --env-file .\.env
```

Day 78 本次验收没有执行此命令；真实 Qwen 历史证据仍是 Day 73 的独立记录，不能当作今天日志包装层的真实模型验收。

## 实现与边界

- [task_log.py](task_log.py)：SQLite 事务、任务隔离、逐条落盘、只读读取。每任务最多 64 个事件，单事件 JSON 最多 16 KiB；任务列表最多返回 100 条，但数据库总量不自动清理。
- [logged_agent.py](logged_agent.py)：包装模型和 MCP 适配器，继续复用 Day 73 的参数及答案验证。无新的 LangGraph 图。
- [test_task_log.py](test_task_log.py)：故障注入、隐私投影、并发任务隔离、事务失败、跨进程查看和真实 MCP 集成。
- 只保存固定请求、决策类别、已校验参数和结果摘要、最终模板回答。不保存 API key、system prompt、完整消息、未校验原文或模型内部推理。
- 这是本地单用户教学日志，无多用户访问控制、加密、签名、防篡改、自动留存策略或生产负载验证。不要放入真实客户数据。
- 任务日志不是会话 Memory，也不是 Day 60 的模拟任务检查点。本次不自动重试、恢复执行或审批，不改变平台 API/Docker，不改变已发布 v0.5 清单。

学习总结与自测见 [Day 78 文档](../../docs/week-12.md#day78)。
