# Day 83：Agent Demo 讲稿与补录清单

2026-09-28，维护者暂时无法录制，决定先继续版本准备。当前只有演示材料与已有自动化验收，**视频未录制，也没有人工观看验收**。状态见 [recording-status.json](recording-status.json)。

目标：用 5–8 分钟展示“提出销售查询 → 调用 MCP → 核对金额与引用 → 保存日志 → 等待人工确认 → 本地模拟执行”。模型使用固定模拟回答，数据库为虚构销售数据，不把演示包装成真实客户业务或模型质量比较。

## 镜头 1：介绍边界（约 30 秒）

口播：“这是 Agent Center 的固定销售学习流程。模型负责提出请求，宿主检查参数和结果。今天不发送真实消息，最后的执行记录存在本地 SQLite 中。”

录制只展示下列新建演示目录的虚构数据；不要打开 `.env` 或其它真实客户资料。

## 镜头 2：生成简报（约 1 分钟）

```powershell
Set-Location 'C:\Users\Administrator\Desktop\enterprise-ai-platform'
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$day83Dir = Join-Path '.\data\day83' ('demo-' + [Guid]::NewGuid().ToString('N'))
& .\experiments\day73\.venv\Scripts\python.exe -B .\experiments\day82\prompt_lab.py prepare --case monthly --output-dir $day83Dir
if ($LASTEXITCODE -ne 0) { throw '生成失败，先检查结果，不继续批准。' }
$day83Result = Get-Content (Join-Path $day83Dir 'generation.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$day83Result.generation | Format-List
$day83Result.approval | Format-List
```

预期：2026 年 9 月，所有客户，已支付订单 4 条，合计 3000.00 元；只展示 2 条明细，合计仍覆盖全部订单。报告包含虚构标记和当前任务引用。审批是 `pending`。

口播：“Day 82 的候选 Prompt 把规则写得更清楚，但这里仍是模拟模型，只说明接入工作正常，不能证明模型准确率提高。”

## 镜头 3：回放日志（约 1 分钟）

```powershell
& .\experiments\day73\.venv\Scripts\python.exe -B .\experiments\day80\hitl_agent.py --data-dir $day83Dir task-log $day83Result.generation.task_id
& .\experiments\day73\.venv\Scripts\python.exe -B .\experiments\day80\hitl_agent.py --data-dir $day83Dir show $day83Result.approval.approval_id
```

指出请求、发现工具、工具参数、回执和最终回答。说明“日志可以跨进程读取，但读日志不等于恢复执行”。再指出审批绑定了正文、接收对象和内容摘要。

## 镜头 4：由人确认（约 1 分钟）

先在屏幕上核对正文与接收对象，明确说“我现在批准这份虚构简报的本地模拟发送”，再执行：

```powershell
& .\experiments\day73\.venv\Scripts\python.exe -B .\experiments\day80\hitl_agent.py --data-dir $day83Dir approve $day83Result.approval.approval_id --digest $day83Result.approval.digest --confirm APPROVE
if ($LASTEXITCODE -ne 0) { throw '批准未成功，请检查审批状态。' }
# 再次确认同一审批，只应返回 already_executed。
& .\experiments\day73\.venv\Scripts\python.exe -B .\experiments\day80\hitl_agent.py --data-dir $day83Dir approve $day83Result.approval.approval_id --digest $day83Result.approval.digest --confirm APPROVE
& .\experiments\day73\.venv\Scripts\python.exe -B .\experiments\day80\hitl_agent.py --data-dir $day83Dir show $day83Result.approval.approval_id
```

说明第一次 `executed`、第二次 `already_executed`，只有一条模拟记录；这不证明外部消息服务具备同样的恰好一次语义。默认审批 30 分钟后到期，如已过期，重新生成一项新任务并重新审阅。

## 镜头 5：失败与降级（约 1–2 分钟）

每次使用新目录，可单独选择一个分支展示：

```powershell
$day83Failure = Join-Path '.\data\day83' ('invalid-' + [Guid]::NewGuid().ToString('N'))
& .\experiments\day73\.venv\Scripts\python.exe -B .\experiments\day82\prompt_lab.py prepare --case monthly --scenario invalid_report --output-dir $day83Failure
# 上条命令预期返回非零：错误金额被拒绝，approval=null。

$day83Fallback = Join-Path '.\data\day83' ('fallback-' + [Guid]::NewGuid().ToString('N'))
& .\experiments\day73\.venv\Scripts\python.exe -B .\experiments\day82\prompt_lab.py prepare --case monthly --scenario report_timeout --output-dir $day83Fallback
```

说明故障是人工注入：错误报告直接停止；已有有效回执但模型回答阶段持续超时时，使用有明确标记的本地模板，仍需人工确认。

## 镜头 6：总结与补录验收（约 30 秒）

口播：“这套流程让固定销售任务有可追溯日志、有限重试和人工门禁。它还没有通用任务执行、生产身份认证、真实消息发送，Memory 和 Planning 也仍是独立实验。”

将来补录后，另行记录实际日期、视频文件/地址、对应提交、使用的演示目录和人工观看结果；确认以下内容后才能把视频标为完成：

- 画面与口播一致，能看清金额、引用与待审批状态。
- 清楚展示由人批准和重复批准只有一条模拟记录。
- 故障注入、模板降级和能力边界都有说明。
- 无凭证或真实业务资料，录制文件可播放、声音清楚。

不要为了完成待办而修改旧版本已冻结的状态文件或验收证据；应新建补录记录并按新的提交评审。Day 55 视频是另一项待办，不因本次材料准备自动完成。
