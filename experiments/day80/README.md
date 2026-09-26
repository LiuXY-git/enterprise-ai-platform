# Day 80：Human in the Loop 人工确认

让 Agent 先生成销售简报，再创建审批单，等待你查看内容、批准或拒绝。批准后的效果只是在本地 SQLite 中新增一条模拟发送记录，没有真实收件人或消息发送接口。

生成阶段沿用 Day 79 的只读 MCP、有限重试和回执模板降级；审批动作由独立命令处理。模型只能请求原来的销售查询工具，工具列表中没有批准或发送操作。Day 80 默认使用模拟模型和真实 MCP stdio，不需要 API key，也没有 `--live` 选项。

## 1. 创建待审批简报

在 PowerShell 执行：

```powershell
Set-Location 'C:\Users\Administrator\Desktop\enterprise-ai-platform'
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'

$day80Draft = & .\experiments\day73\.venv\Scripts\python.exe -B .\experiments\day80\hitl_agent.py create --case monthly --recipient sales-manager-demo | ConvertFrom-Json
if ($LASTEXITCODE -ne 0 -or $null -eq $day80Draft.approval) { throw '未生成可审批的简报，请查看生成结果。' }
$day80Card = $day80Draft.approval
$day80Card | ConvertTo-Json -Depth 10
```

预期：`status=pending`，`simulation_count=0`，`external_send=false`。`proposal.body` 是已校验的虚构销售简报：4 单、3000.00 元；`recipient` 为本地教学接收对象 `sales-manager-demo`。

请完整查看 `proposal` 中的操作、接收对象、正文、备注、来源和降级标记，再决定是否批准。`digest` 是这些具体内容的 SHA-256 摘要，用于绑定你查看的版本，不是身份认证密码。

没有 Day 73 环境时，先按 [原安装步骤](../day73/README.md#1-安装独立环境)准备。无需安装新依赖或更新容器。

## 2. 查看后批准

下面的命令会批准当前版本并生成一条本地模拟发送记录。确认内容后再执行：

```powershell
& .\experiments\day73\.venv\Scripts\python.exe -B .\experiments\day80\hitl_agent.py approve $day80Card.approval_id --digest $day80Card.digest --confirm APPROVE
```

预期 `status=executed`、`decision_result=executed`、`simulation_count=1`。`executed` 仅表示本地模拟动作已提交；`external_send` 始终为 `false`。

审批事件依次包含 `approval_requested`、`human_approved`、`simulation_executed`。批准事件、模拟记录和最终状态在同一个事务中提交；不经过先批准、稍后无保护发送的间隙。

重复执行同一条批准命令，返回 `decision_result=already_executed`，记录数仍为 1。这个保证只针对同一个 `approval_id`。再次执行 `create` 会生成新的任务与审批单，属于新的操作意图，不会根据内容相似度自动去重。

## 3. 关闭终端后继续审批

记录默认保存在项目的 `data/day80/`：

| 文件 | 内容 |
| --- | --- |
| `tasks.sqlite` | Day 78/79 格式的生成与恢复日志 |
| `approvals.sqlite` | 待审批内容、人工决定、审批事件和模拟发送记录 |

新终端进入项目并设置 UTF-8 环境变量后：

```powershell
& .\experiments\day73\.venv\Scripts\python.exe -B .\experiments\day80\hitl_agent.py list
$day80Card = & .\experiments\day73\.venv\Scripts\python.exe -B .\experiments\day80\hitl_agent.py show '替换成实际审批编号' | ConvertFrom-Json
$day80Card | ConvertTo-Json -Depth 10
```

重新查看内容后，可用第 2 步命令批准。查看原始生成过程：

```powershell
& .\experiments\day73\.venv\Scripts\python.exe -B .\experiments\day80\hitl_agent.py task-log $day80Card.proposal.source_task_id
```

`list`、`show`、`task-log` 均只读，不调用模型或 MCP。`list` 最多展示最近 100 个审批版本；数据库没有自动清理策略。自定义目录时，将 `--data-dir .\data\day80-practice` 放在子命令前，并在后续所有命令中使用相同目录。

这只恢复持久化的待审批事项，不是恢复中断的 Agent 计算。生成阶段仍遵循 Day 79 的边界。

## 4. 拒绝一份新的审批单

已执行的审批无法撤销。练习拒绝时先重新执行第 1 步，取得新的待审批编号，再执行：

```powershell
& .\experiments\day73\.venv\Scripts\python.exe -B .\experiments\day80\hitl_agent.py reject $day80Card.approval_id --digest $day80Card.digest --reason not_needed
```

预期 `status=rejected`、`simulation_count=0`。该审批单之后不能再批准；需要重新准备时新建任务。另一个拒绝原因是 `needs_revision`。

## 5. 修改内容后重新审批

仅允许修改尚未过期、仍为 `pending` 的审批单。先按第 1 步创建新的审批单，再修改备注或接收对象：

```powershell
$day80Old = $day80Card
$day80Card = & .\experiments\day73\.venv\Scripts\python.exe -B .\experiments\day80\hitl_agent.py revise $day80Old.approval_id --digest $day80Old.digest --recipient finance-demo --note '请财务复核此份虚构教学数据' | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) { throw '修改未完成，请查看原审批单状态。' }
$day80Card | ConvertTo-Json -Depth 10
```

新版本得到新的审批编号和内容摘要，仍为 `pending`；旧版本变为 `superseded`。必须重新查看并批准新版本。用旧编号批准会被拦截；把旧摘要用于新编号也会被拦截。

本实验保留已校验的简报正文，不提供直接编辑金额的入口。可改的内容是接收对象和人工备注；若要改变查询范围，需要重新 `create`。备注最多 200 字符；接收对象仅有两个本地教学标识。

## 6. 过期与异常处理

默认有效期为 1800 秒，即 30 分钟；创建或修订新版本时可用 `--ttl-seconds` 指定 1–86400 秒。过期后不会自动批准。

例如创建一个 5 秒到期的审批单：

```powershell
& .\experiments\day73\.venv\Scripts\python.exe -B .\experiments\day80\hitl_agent.py create --ttl-seconds 5
```

超过有效期后，`show` 的 `effective_status` 为 `expired`。只读查看不会更新数据库，所以原始 `status` 可能仍为 `pending`；再次尝试有效摘要对应的审批动作时，会记录 `approval_expired`，实际发送数为 0。

| 情况 | 处理 |
| --- | --- |
| 尚未批准 | 保持等待，不执行 |
| 明确拒绝 | 结束该审批，执行数 0 |
| 内容摘要不匹配 | 记录 `decision_blocked`，不执行 |
| 内容修改 | 新建审批版本，旧版本失效 |
| 已过期 | 不能执行，也不能通过修订旧单绕过有效期 |
| 重复或并发批准 | 同一个审批最多一条模拟发送记录 |
| 审批/日志/模拟记录写失败 | 整个事务回滚；检查原审批编号后再决定是否重试 |
| 查询失败、金额校验失败或需要澄清 | 不创建审批单，保留生成日志 |

成功完成命令（包括明确拒绝、读取和已执行记录的重复确认）退出码为 0；状态冲突、过期或存储错误为 1；缺失 `--digest` / `--confirm APPROVE` 等 CLI 参数错误为 2。

## 7. 观察错误恢复与人工确认的衔接

```powershell
& .\experiments\day73\.venv\Scripts\python.exe -B .\experiments\day80\hitl_agent.py create --scenario tool_timeout_once
& .\experiments\day73\.venv\Scripts\python.exe -B .\experiments\day80\hitl_agent.py create --scenario report_timeout
& .\experiments\day73\.venv\Scripts\python.exe -B .\experiments\day80\hitl_agent.py create --scenario invalid_report
```

第一种查询重试成功后仍停在 `pending`；第二种使用回执模板后仍停在 `pending`，审批正文保留降级提示；第三种输出错误金额时返回 `approval=null`。重试或降级都不会代替人工批准。

## 8. 验证与代码阅读

```powershell
& .\experiments\day73\.venv\Scripts\python.exe -B -m pytest .\experiments\day64 .\experiments\day65\test_sales_sql.py .\experiments\day72\test_sales_mcp.py .\experiments\day73 .\experiments\day78 .\experiments\day79 .\experiments\day80 -q
& .\experiments\day73\.venv\Scripts\python.exe -B -m ruff check .\experiments\day80
& .\experiments\day73\.venv\Scripts\python.exe -B .\scripts\day77\release_gate.py
```

pytest 默认临时目录不可用时，可指定一个新的专用 `--basetemp` 目录，不要指向存有个人文件的目录。

- [hitl_agent.py](hitl_agent.py)：复用 Day 79 生成合格简报，再转为待审批事项；CLI 将生成与决策分开。
- [approval_store.py](approval_store.py)：内容摘要、有效期、版本失效、事务和唯一模拟执行记录。
- [test_hitl.py](test_hitl.py)：多进程审批、并发竞争、事务故障与中断、旧内容拒绝、生成失败和跨进程读取。

本实验是本地单用户教学实现。`local_cli_user` 仅标识操作来自 CLI，不验证操作者身份；摘要也不是签名。拥有本地文件/命令权限的人可以操作记录，不构成多用户权限隔离或防篡改审计。审批工具没有提供给模型，但本实验无法识别任意外部脚本是否由真人发起。

模拟效果完全位于同一个 SQLite 事务，不能据此宣称真实飞书、企业微信或邮件接口也能恰好发送一次。接入外部服务需要另行设计幂等、发送状态核对和权限控制。平台 API、Docker、旧版本冻结代码均未改变。
