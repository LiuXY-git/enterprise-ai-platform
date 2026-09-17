# Day 55：Workflow Center 业务 Demo

目标是在约 6–8 分钟的视频中展示一次真实的“客服咨询 → 邮件人工复核 → 销售分析与 CRM → 重复事件保护”。三个场景使用各自独立的虚构事件，不把它们描述成已实现的跨工作流自动接力。演示材料准备、现场执行、视频录制与视频验收分别记录。

本次交付的是录制讲稿、离线请求包工具、逐步请求执行工具和验收表。**尚未完成本轮真实业务演示或视频录制。** Day 49 业务证据和原 AI 客服视频保留为历史成果，不计作 Day 55 新录制。

**2026-09-17 排期调整：** 维护者暂时无法录制，已决定先进行 Day 56，之后补录。本页保留为后续操作稿，未完成项继续待验收；阶段总结与发布安排见 [Week 8 总结](week-8-summary.md) 和 [v1.0 候选说明](workflow-center-v1.0.md)。恢复录制时按当日环境生成新演示包。

## 1. 演示主线

| 环节 | 要展示的业务价值 | 本次通过依据 |
| --- | --- | --- |
| 客服咨询 | 从已有知识库回答产品问题 | 实际回答有依据；记录 Dify 执行 ID |
| 邮件人工复核 | 高优先级请求交给人工处理 | `needs_human_review`、空草稿和平台持久化状态一致 |
| 销售跟进 | 分析线索并形成可追踪的 CRM 跟进 | 正常业务结果、平台运行、分析检查点、唯一跟进记录；通知为 preview |
| 重复事件 | 重复提交不会创建第二条跟进 | 相同 run_id、`duplicate=true`、`processed=false`，跟进仍为一条 |
| 工程支撑 | 配置、部署和日志可检查 | 展示本次检查结果及按运行标识筛选的日志，解释各自覆盖范围 |

邮件片段特意选择 `priority=high` 的确定性人工复核分支，不声称该片段使用了 LLM 分类。客服和销售需要模型调用；邮件草稿生成可作为扩展片段，步骤见 [邮件模板](../n8n/templates/email-assistant/README.md)。销售风险识别结果由实际模型和校验决定，不预先保证一定走正常分支。

## 2. 录制前准备

先按 [使用指南](user-guide.md) 确认部署、凭据和三个模板。现有环境复用工作流，避免导入相同 Webhook 路径的副本。

- API、n8n 已运行；独立 Dify 工作流已发布且能读取所需知识库。客服样例询问“知识库支持哪些文档格式”，Dify 应用需已接入包含该信息的项目资料。
- 客服、持久化邮件和销售工作流均已发布，才能使用下面的 Production URL。邮件主流程的 Error Workflow 已绑定；销售节点已绑定 n8n 内的 DashScope 凭据。
- 使用虚构数据；关闭 `.env`、凭据页面和无关通知。画面只保留终端、n8n 对应执行和项目文档。
- 预留终端和浏览器可读字号；先试录约 10 秒检查声音与文字，再正式录制。既有视频文件不覆盖，新视频放在仓库之外。

在项目根目录检查现有部署：

```powershell
Set-Location 'C:\Users\Administrator\Desktop\enterprise-ai-platform'
& .\scripts\check-deployment.ps1 -CheckComponents llm,dify
```

配置检查只验证格式。`llm` 是 API 自己的模型配置，不能代替销售的 n8n Credential 检查；Dify 连通性与业务输出需要执行后核对。本轮脚本不更新镜像，演示工具无需重建容器。

## 3. 生成本次录制请求包

使用已准备好的项目 Python 环境，以下操作完全离线：

```powershell
$demoDir = Join-Path $env:TEMP ('day55-demo-' + [guid]::NewGuid().ToString('N'))
.\.venv\Scripts\python.exe .\scripts\day55\prepare_demo.py `
    --production --output-dir $demoDir
if ($LASTEXITCODE -ne 0) { throw '演示包生成失败' }
Get-Content -LiteralPath (Join-Path $demoDir 'manifest.json') -Raw -Encoding UTF8
```

保留终端打印的目录，后续命令在同一个 PowerShell 会话执行。换窗口后，把 `$demoDir` 设置为该目录的完整路径；恢复查看结果时不要重新生成另一批事件。

| 文件 | 用途 |
| --- | --- |
| `01-customer.request.json` | 客服咨询 |
| `02-email-review.request.json` | 高优先级邮件人工复核 |
| `03-sales.request.json` | 一条独立销售线索 |
| `04-sales-duplicate.request.json` | 与首次销售请求完全相同，用于重复保护演示 |
| `manifest.json` | 本批标识、URL、请求哈希、准备状态 |
| `recording-notes.json` | 尚未填写的业务和视频验收记录，默认检查结果均为 null |

每个新目录有独立事件和客户标识；销售日期取上海时区当天。输出目录必须不存在，即使空目录也拒绝覆盖。生成器复用 Day 50 模板，只替换演示标识与请求来源，不修改原始模板或工作流。

`--production` 仅生成生产 URL，不发布工作流或执行请求。省略时生成 Test URL，每次提交前需要重新开启相应 Webhook 的测试监听，包括销售重复请求。正式视频建议用已发布的 Production URL。

准备清单内的 `execution_performed=false` 描述生成时的状态，不会随着后续执行自动更新；本次真实执行以各步骤的 `.result.json` 和持久化记录为准。演示结果不会自动写成通过。

## 4. 逐步执行与核对

下面的步骤会发送真实 Webhook 请求，产生演示运行及 CRM 数据，客服和销售会调用模型。每步确认结果后再继续，不要一次性粘贴全部步骤。执行工具只支持本机 HTTP n8n 地址，默认 `localhost:5678`；它仅发送请求文件的 `body`。

执行前核对请求哈希和对应 Webhook 路径。执行开始先建立结果文件；HTTP 失败、超时或中断后也阻止直接重复执行同一步。`response_received_unverified` 只表示收到 HTTP 响应，业务状态仍需按下文确认。工具不读取 n8n 执行 API，不宣称已核对节点轨迹。

### A. 客服问答

```powershell
& .\scripts\day55\invoke-demo-step.ps1 -BundleDirectory $demoDir -Step 01-customer
```

查看回答与知识依据，不以 HTTP 200 代替答案正确性。`workflow_run_id` 属于 Dify，到 Dify 的对应运行记录核对；本客服模板没有平台事件去重。未检索到依据时可以展示真实拒答，但本项“有依据的资料咨询”验收仍待完成。

### B. 邮件人工复核

```powershell
& .\scripts\day55\invoke-demo-step.ps1 -BundleDirectory $demoDir -Step 02-email-review
$mail = (Get-Content -LiteralPath (Join-Path $demoDir '02-email-review.result.json') -Raw -Encoding UTF8 | ConvertFrom-Json).response
if (-not $mail.workflow_run_id) { throw '邮件未返回平台运行 ID，请检查结果' }
$mailRun = Invoke-RestMethod -Method Get -Uri ("http://127.0.0.1:8000/workflow-runs/" + $mail.workflow_run_id)
$mailRun | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath (Join-Path $demoDir 'email-run.json') -Encoding UTF8
$mail | Select-Object status, need_human_review, draft_reply, workflow_run_id, persisted_status
$mailRun | Select-Object run_id, status, priority
```

预期响应 `need_human_review=true`、`draft_reply` 为空，平台状态为 `needs_human_review`。这里没有发送邮件，也没有自动完成真正的人工审核。

### C. 销售分析与 CRM

```powershell
& .\scripts\day55\invoke-demo-step.ps1 -BundleDirectory $demoDir -Step 03-sales
```

先查看 `status`、`requires_human_review`、分析内容和通知。正常演示要求 `succeeded`、无需人工复核和 `notification.mode/status=preview`。若模型返回风险标记或发生异常，先保留事实并排查；不要把复核分支改写成成功。

确认正常结果后读取本轮持久化记录，并保存重复请求前的快照：

```powershell
$sales = (Get-Content -LiteralPath (Join-Path $demoDir '03-sales.result.json') -Raw -Encoding UTF8 | ConvertFrom-Json).response
if ($sales.status -ne 'succeeded' -or -not $sales.run_id -or -not $sales.followup_id) {
    throw '销售结果尚未满足正常演示条件，请检查已保存结果'
}
function Get-Day55SalesState {
    [ordered]@{
        workflow = Invoke-RestMethod -Method Get -Uri ("http://127.0.0.1:8000/workflow-runs/" + $sales.run_id)
        followup = Invoke-RestMethod -Method Get -Uri ("http://127.0.0.1:8000/crm/followups/" + $sales.followup_id)
        followups = Invoke-RestMethod -Method Get -Uri ("http://127.0.0.1:8000/crm/customers/" + $sales.customer_id + '/followups')
    }
}
$before = Get-Day55SalesState
$before | ConvertTo-Json -Depth 40 | Set-Content -LiteralPath (Join-Path $demoDir 'sales-before-duplicate.json') -Encoding UTF8
$before.workflow | Select-Object run_id, status, duplicate_count, retry_count, processing_stage
$before.followup | Select-Object followup_id, notification_mode, notification_status, notification_attempt_count
$before.followups | Select-Object count
```

查看完整快照中的分析检查点和跟进分析，核对归属于本次事件。首次正常运行应只保存一条跟进，通知 `preview`、尝试次数 0。通知预览不等于飞书或企业微信送达。

### D. 重复事件保护

保留同一份销售输入，不更改 event_id，不设置 replay。工具要求首次销售结果已保存且为成功预览状态，才允许发送重复请求：

```powershell
& .\scripts\day55\invoke-demo-step.ps1 -BundleDirectory $demoDir -Step 04-sales-duplicate
$duplicate = (Get-Content -LiteralPath (Join-Path $demoDir '04-sales-duplicate.result.json') -Raw -Encoding UTF8 | ConvertFrom-Json).response
$after = Get-Day55SalesState
$after | ConvertTo-Json -Depth 40 | Set-Content -LiteralPath (Join-Path $demoDir 'sales-after-duplicate.json') -Encoding UTF8
$duplicate | Select-Object run_id, event_id, duplicate, processed
$after.workflow | Select-Object run_id, status, duplicate_count, retry_count
$after.followups | Select-Object count
$after.followup | Select-Object followup_id, notification_status, notification_attempt_count
```

逐项核对：原 `run_id`、`duplicate=true`、`processed=false`；前后跟进 ID 一致且数量始终为 1；`duplicate_count` 从 0 增至 1，`retry_count` 保持 0；通知仍为 preview、尝试次数 0。这是演示核对，完整的 CRM 字段不变验收沿用 [Day 49 记录](day49-release-acceptance.md)，不把本轮人工展示描述成重新执行了全部回归。

### E. 查看本轮日志

```powershell
$runIds = @($mail.workflow_run_id, $sales.run_id)
Get-Content -LiteralPath '.\logs\workflow-events.jsonl' -Tail 300 |
    ForEach-Object { $_ | ConvertFrom-Json } |
    Where-Object { $_.run_id -in $runIds } |
    Select-Object timestamp, operation, outcome, run_id, duration_ms, total_tokens, metrics_source
```

只展示本轮运行的诊断字段。若日志已轮转，到对应备份里查找，不能以最近 300 行未出现记录就认定业务失败。客服 Dify ID 可用 `dify_run_id` 筛选。日志没有统一全链路 trace_id；用量缺失可能为 null，也不能跨事件简单累加 Token。

## 5. 录制时间轴与讲稿

| 时间 | 画面与操作 | 讲解要点 |
| --- | --- | --- |
| 0:00–0:40 | README 与架构图 | “平台现在有知识库和工作流中心。这次用三类业务场景展示问答、人工复核和销售跟进。” |
| 0:40–1:10 | 本次部署检查结果 | “API 与 n8n 健康，配置格式通过。真实模型是否可用，要看接下来的业务执行。” |
| 1:10–2:10 | 客服实际请求、回答和 Dify 记录 | “这次咨询通过 n8n、API 到 Dify，再依据接入资料回答。这里的执行 ID 属于 Dify。”只按实际回答解释依据。 |
| 2:10–3:00 | 邮件响应与平台运行 | “高优先级请求进入人工复核，不生成自动草稿。平台已保存状态，但没有自动发送邮件。” |
| 3:00–4:40 | 销售输入、分析和 CRM | “模型整理需求、缺失信息和跟进建议。分析检查点和 CRM 跟进关联到同一次平台运行。”展示实际结果。 |
| 4:40–5:40 | 原事件重复提交与前后快照 | “再次提交的是同一个业务事件。系统返回原运行，跟进仍只有一条，避免重复业务写入。” |
| 5:40–6:30 | 过滤后的日志、模板和配置入口 | “模板便于复用，日志用于排障。API、Dify 和 n8n 各自管理模型配置。” |
| 6:30–7:00 | 结果与当前边界 | “销售通知目前是预览。真实通知编排、统一鉴权与租户隔离仍待完善，Day 56 再整理阶段发布。” |

按真实耗时留出余量；可剪去等待时间，并在剪辑处标注。不要将历史截图插入后当成本次实时执行，录制失败时不按预写讲稿宣称成功。

## 6. 失败处理与录制验收

| 情况 | 本轮处理 |
| --- | --- |
| 输出目录已存在 | 查看原包；独立的新演示才生成新目录。生成失败可能保留部分文件，不覆盖旧目录 |
| 请求哈希不匹配 | 核对是否修改了请求；不要修改清单哈希来绕过检查。需要自定义输入时使用模板指南并单独留证 |
| 结果文件已存在 | 查看该步骤结果与原事件；不要删除文件来触发重发 |
| Test URL 不监听、生产 Webhook 未发布、HTTP 失败或超时 | 保留结果文件和原事件标识，查 n8n 执行及平台状态；超时可能已经完成部分业务写入 |
| 邮件或销售业务状态异常 | 先排查原运行；CRM 已保存后不整条回放，恢复规则见使用指南 |
| 第一次销售结果无需再次请求，只想补录画面 | 展示已保存结果，说明是本轮记录回看；只读查询可以重新执行 |
| 模型不可用 | 录制可以暂停；历史证据仅作为明确标注的历史片段，当前未完成项保持待验收 |

演示包的执行保护只覆盖本工具，不是服务端幂等替代品；客服流程本身仍没有事件去重。`.result.json` 保存原输入和实际响应，`business_verified` 初始为 false，需用本次快照填写 `recording-notes.json`。不要将 HTTP 响应成功直接填作全部业务通过。

按 [录制验收表](../demo/day55-recording-checklist.md) 核对视频和业务结果，保存本批请求、响应、快照、验收记录和视频文件。视频保留在仓库之外，可用以下命令计算真实文件的 SHA-256，再填写记录：

```powershell
# 将路径替换为本次实际录制的视频文件。
Get-FileHash -LiteralPath 'C:\Users\Administrator\Videos\day55-workflow-center-demo.mp4' -Algorithm SHA256
```

`recording-notes.json` 的状态在完成录制后可改为 `recorded_pending_review`，全部必需检查通过后再改为 `accepted`；未检查保持 null，失败填 false 并记录问题。生成器和请求执行工具不会自动标记视频完成或发布新版本。

## 7. 本次材料验证

基线为 Day 54 合并提交 `1764740`。本轮检查结果：

- 19 项离线/隔离模拟检查通过，覆盖批次唯一性、原文件保留、销售重复输入一致性、默认测试 URL、UTF-8 请求体、错误与超时留证、重发拦截、请求修改拦截、重复步骤前置条件、本机地址约束和禁止重定向。
- 请求工具在 Windows PowerShell 5.1 和 PowerShell 7.6 中使用临时本地模拟 HTTP 服务验证；11 次请求全部发给该模拟服务，未调用真实 n8n、模型、业务 API 或消息接口。
- 14 段文档 PowerShell 示例及请求脚本在两个 PowerShell 版本中通过语法解析；7 份相关文档的 142 个本地链接检查通过。
- 新增 Python 工具通过 Ruff 检查与格式检查。业务代码、部署配置和工作流导出沿用基线，没有因本轮工具准备重新进行容器部署或全量业务回归。

以上只证明演示材料与工具的相应行为。Day 55 的真实业务展示、视频文件和人工验收仍待完成，不能将模拟结果填写进正式录制验收记录。
