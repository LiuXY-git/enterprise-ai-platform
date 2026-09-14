# Day 49 可重复验收脚本

## CRM 保存后的整条回放保护

`day49-test-replay-guard.ps1` 每次创建两组虚构客户、事件、工作流和跟进记录，分别模拟通知明确失败与结果不确定，然后验证整条工作流回放被拒绝。

脚本只调用本地 FastAPI 的健康检查、运行管理及 CRM 状态接口，不调用 n8n、模型或真实消息接口。请求中的 `notification_mode: send` 用于建立待发送状态；本脚本登记尝试并填写模拟结果，不执行消息发送。

从项目根目录运行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/day49/day49-test-replay-guard.ps1
```

前提：本地 API 已运行，包含 Day 48 的 CRM、通知状态、恢复及回放保护接口。无需保留历史 run_id，无需启动 n8n 测试监听，也无需模型或通知凭据。

验收断言：

- 两种场景均返回 HTTP 409，错误内容必须来自 CRM 已保存的回放保护，其他冲突不能算通过。
- 拒绝前后的完整工作流、客户、跟进记录及客户跟进列表不变。
- 工作流保持 failed，通知分别保持 failed 或 delivery_unknown。
- retry_count 保持 0，通知尝试保持 1 次，跟进记录保持 1 条，通知请求标识不变。
- 自动恢复被禁止；明确失败进入 notification，结果不确定进入 human_delivery_check，均要求人工处理。

成功时显示 `Day 49 fresh-data replay guard tests passed.`，并打印本轮 event_id、run_id、followup_id 和断言结果。脚本必须完整结束才算两项均通过。

## 验收记录与重复执行

默认 JSON 证据目录为 `%TEMP%\day49-acceptance`。每轮使用唯一文件名，脚本开始和结束都会显示实际路径；可通过 `-EvidenceDirectory` 指定其他目录。

证据包含本轮标识、API 地址、起止时间、场景、完整前后快照及结果。若请求或断言失败，脚本立即停止，保存 `passed: false` 和已知标识；不会自动重试超时请求。先检查报告中的错误和对应记录，再决定是否重新运行。

每次重新运行都创建独立数据，不复用前一次事件。测试数据保留在本地数据库中供核对，每次成功执行新增两个客户及两条跟进记录；脚本不删除业务数据。证据为本地状态接口验收，不是 n8n Production URL、AI 故障或真实消息发送验收。

`-ApiBaseUrl` 默认为 `http://localhost:8000`，仅接受本机 HTTP 地址。可以使用该参数对临时测试实例验收。

## 脚本验证记录

本轮在 Windows PowerShell 5.1 下执行脚本，使用项目真实 CRM 与工作流路由、独立临时 SQLite 数据库和临时本地端口：

- 从空数据库运行成功，覆盖两类通知故障。
- 在同一测试数据库再次运行成功，四个场景使用不同 run_id，无需清空旧数据。
- 负向检查将回放响应替换成另一种 HTTP 409，脚本正确报错并保存失败证据。

以上为隔离环境验证。用户已于 2026-09-13 在部署的 API 上完成回放保护验收，批次 17e171ec3a4a470b8118a25c512d0268，两种场景均通过。控制台摘要曾因有序字典转换显示 null，JSON 证据完整；摘要转换已修复并通过 PowerShell 5.1 回归。

后续继续验收 Production URL，以及最终 n8n 版本的 AI/CRM 故障场景。

## 人工核对与通知重试

`day49-test-notification-resolution.ps1` 使用新建模拟记录验收两条路径：

| 场景 | 通知最终状态 | 通知尝试次数 | 工作流最终状态 |
| --- | --- | --- | --- |
| 确认已送达 | sent | 1 | failed |
| 确认未送达后人工重试并模拟成功 | sent | 2 | failed |

从项目根目录运行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/day49/day49-test-notification-resolution.ps1
```

脚本只调用本地状态 API，模拟 message_id 不代表真实平台消息；不需要模型、通知凭据或 n8n 监听。每轮创建两个虚构客户及两条跟进记录，保留数据作为证据。不会修改前一轮回放保护验收的记录。

重点断言：

- delivery_unknown 核对前，自动和人工重发都被拒绝。
- 确认已送达后禁止重发；确认未送达后仍禁止自动重发，但允许显式人工重试一次。
- 重试请求等待结果时，重复登记被拒绝；记录 sent 后，人工和自动重发均被拒绝。
- 重复核对被拒绝；重复写入相同 sent 结果保持幂等。
- 所有被拒绝的请求均返回 409，拒绝前后的完整运行和跟进记录不变。
- 通知请求标识稳定、客户资料和 CRM 业务字段不变、跟进仅一条。
- 通知与工作流状态分别查询和断言。当前通知核对/重试不会自动完成原 failed 工作流，工作流 retry_count 保持 0；业务运行收尾仍为后续待办。

成功时显示 `Day 49 simulated notification resolution tests passed.`。JSON 证据写入 `%TEMP%\day49-acceptance\day49-notification-resolution-<batch_id>.json`，包含核对前、核对后和最终状态，以及所有被拒绝请求的检查结果。支持 `-ApiBaseUrl` 和 `-EvidenceDirectory`，失败保存未通过报告并停止，不自动重试请求。

2026-09-13 已在 Windows PowerShell 5.1、项目真实路由及隔离 SQLite 上完成两轮验证；每轮两条路径共检查 14 次请求被拒绝且记录不变，并核对控制台摘要与证据字段完全一致。另注入错误允许重发的 HTTP 200，脚本能正确失败并保存证据。用户已于 2026-09-13 在部署 API 上完成本轮人工核对验收，批次 7975a813112249e394725f60c88a6ff4。两场景通过，14 次受限请求均返回 409 且记录不变；通知 sent、工作流 failed，通知尝试分别为 1 和 2。

## Production URL 正常处理与重复事件

`day49-test-production.ps1` 向已发布的销售工作流提交一条新线索，确认成功后再次提交完全相同的事件，检查重复响应和持久化结果。

从项目根目录执行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/day49/day49-test-production.ps1
```

前提是 API、n8n 均已运行，销售工作流已发布并绑定可用的 DashScope 模型凭据。固定调用 `/webhook/w7d47-sales-followup-assistant`，不使用测试 URL，无需点击 Execute workflow。本次会调用真实模型，第一次分析最多等待 180 秒。沿用当前销售工作流的 preview 模式，不增加通知发送编排。

核心检查：

- 首次事件成功，采购窗口 60 天对应 normal，无人工复核；响应和数据库均为通知 preview，通知尝试为 0，message_id 为空。
- 检查点存在并归属于本次 run_id/event_id，CRM 中只有一条跟进，返回分析与 CRM 一致。
- 重复事件返回原 run_id/event_id，duplicate 为 true、processed 为 false。
- duplicate_count 从 0 增至 1。除 duplicate_count 与 updated_at 外，运行全部字段保持不变；客户、跟进记录和列表完整内容不变。
- 工作流 retry_count 为 0，通知尝试仍为 0，跟进仍为 1 条。

脚本返回 `Day 49 Production URL and duplicate tests passed.` 即完成本项 HTTP 与持久化验收，不再要求追加节点轨迹核对。脚本不读取 n8n 执行 API，不把该验收结果表述为读取过节点轨迹。已通过的验收沿用结果；只有相关改动、失败或新增风险时才重验。

本轮输入、首次响应、重复响应和前后数据库快照保存在 `%TEMP%\day49-acceptance\day49-production-<batch_id>.json`。HTTP 200 但业务状态异常仍会失败；失败即停止并保存证据，不自动重试超时或错误请求。若失败，先根据 event_id 查 n8n 记录和报告，不要盲目重跑。每次重新运行脚本都会创建新事件。

支持 `-ApiBaseUrl`、`-N8nBaseUrl` 和 `-EvidenceDirectory` 参数，本地地址是默认值。脚本的离线验证使用模拟 Webhook 与项目真实路由/临时数据库，已验证正常路径、重复时客户被错误修改和通知模式错误这三类响应，并核对摘要和请求次数；这不替代用户的真实 n8n/模型验收。

### 分析字段顺序误报与续跑

2026-09-13 批次 02db679f027d43db9411a2bc1f7c5df4 的首次业务处理已成功，run_id 为 f5d944b0-3468-460f-bf47-a3bbbc83e650。原脚本以 JSON 文本比较分析内容，因对象字段顺序不同而误报，重复事件请求尚未执行。

现已将 JSON 对象按键规范化后比较，保留数组顺序、标量类型和真实值差异。修复使用本轮真实响应以及类型/数组顺序反例验证，并在隔离模拟 Webhook 下复现原错误，再验证只提交一次重复请求即可续跑。未重新运行用户的首次业务处理。

参数 `-ResumeEvidencePath` 仅支持这类分析比较失败的报告，并要求地址一致、首次运行成功且尚未执行重复验收。复用报告中的成功响应、run_id 和 event_id，读取当前持久化结果，然后只提交原事件的重复请求；若已完成重复验收则停止。续跑报告使用新批次文件并保留原批次关联，不覆盖原始证据。
