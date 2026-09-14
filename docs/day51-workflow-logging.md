# Day 51：工作流结构化事件日志

Day 51 为客服、邮件和销售工作流增加统一事件日志，记录可关联的输入、输出、状态、处理时间和用量来源。基线是 Day 50 本地提交 fd59aef，平台 API 与既有请求/响应契约保持不变。

## 日志放在哪里

原来的 `backend/logs/app.log` 继续用于普通应用日志。API 启动时另行配置 `backend/logs/workflow-events.jsonl`，一行一个 JSON 对象，同时输出到控制台。单文件达到约 5 MiB 轮转，保留 3 份备份；按当前单 API 进程使用，不宣称支持多进程共享文件的并发轮转。

日志目录已由现有 `.gitignore` 排除。容器中的路径取决于应用所在目录；未新增日志卷，容器文件可能在重建时丢失。持续保存与部署配置在后续部署任务中处理。

## 哪些调用会记录

| operation | 记录时机 | 输入与输出 |
| --- | --- | --- |
| dify.call | `/dify/workflow` 调用完成或失败 | question/user；成功时 answer 与 outputs |
| workflow.start | 运行登记、重复命中或回放决策完成 | 实际返回的已保存 input_data，避免把重复请求的新内容误记为原输入 |
| workflow.finish | 保存成功/人工复核结果后 | 账本输入与已保存 output_data |
| workflow.checkpoint | 保存分析检查点后 | 账本输入与 checkpoint_data，覆盖销售 AI 分析结果 |
| workflow.fail | 按 run_id 保存失败后 | 已有账本输入/输出及安全错误类型 |
| workflow.fail_by_execution | n8n Error Trigger 按执行 ID 保存失败后 | 已有账本输入/输出及安全错误类型 |

这些是经过请求校验后进入路由的业务事件。框架直接拒绝的 422、只读查询、CRM 通知状态接口和 n8n 内部逐节点执行日志不在本次新增记录范围内。API 返回 200 表示记录操作成功，实际业务结果看 status；例如人工复核是 needs_human_review，失败落库可能是 failed。

## 字段与关联方式

每行包含 schema_version、UTC timestamp、独立 log_event_id、operation、outcome、http_status、status、run_id、dify_run_id、event_id、workflow_name、n8n_execution_id、request_n8n_execution_id、retry_count、duplicate_count、processing_stage、failure_stage、error_type、duration_ms、elapsed_time_seconds、total_tokens、metrics_source、input、output 和 snapshot_policy。

- run_id 只放平台运行 ID，dify_run_id 只放 Dify ID。二者不互相替代。
- log_event_id 标识一条日志，不是跨系统 trace_id。当前邮件调用 Dify 时没有传平台运行 ID，不能仅凭日志时间把两者视为已经准确关联。
- request_n8n_execution_id 表示本次登记请求提供的执行号；n8n_execution_id 表示返回记录中的执行号。重复请求不会凭空覆盖原运行的执行归属。
- outcome 区分 success、duplicate、replayed、error；HTTP 错误只记录类型和状态码，不写原始异常正文或堆栈。
- 单条 API 事件不等于一次完整工作流；一个运行可有登记、检查点和完成等多条日志。

## 时间与 Token 如何理解

| 字段/来源 | 含义 |
| --- | --- |
| duration_ms | API 路由内部处理耗时，单调时钟测量；不含 n8n 全流程或日志写入时间 |
| elapsed_time_seconds + dify_response | Dify 响应报告的工作流耗时，不能等同于纯模型推理耗时 |
| total_tokens + dify_response | Dify 报告用量；缺失保留 null |
| workflow_client_reported | 完成接口调用方提供的耗时/Token，没有由日志层重新测量 |
| not_reported | 本事件未获得对应耗时/Token；字段保留 null |

邮件草稿的用量通常由 Dify 传入；人工复核分支沿用现有 0 值约定，日志如实记录为调用方报告。销售流程目前未上报模型 Token，保持 null，不从文本长度估算。重复、失败或检查点事件不将记录里残留的统计值当作新调用用量。

**不要把所有日志的 total_tokens 直接相加。** 同一次邮件 Dify 用量可能同时出现在 dify.call 和 workflow.finish，统计时应选一个来源并明确覆盖范围。回放保留相同平台 run_id，应结合 retry_count 区分尝试。

## 输入输出记录范围

快照先替换常见凭据字段以及 Bearer、sk- 和 key/value 形式的密钥，再限制字符串长度、嵌套深度与元素数量；单个快照超过 8000 字符时保留截断预览。日志字符串用 JSON 编码，换行不会伪造额外日志行。

这不是完整的个人信息匿名化工具，业务正文仍可能包含姓名、客户信息或商业内容；仅在当前可信本地环境中使用。不要通过日志公开业务正文。快照不会修改响应或数据库，完整业务输入/输出仍沿用现有账本存储规则。

请求执行期间日志构造或写入失败不会改变已经完成的业务响应，应用日志会尝试写入固定故障标记。JSONL 是尽力记录的诊断日志，不是和数据库事务原子提交的审计账本。

## 如何查看

在项目根目录，用 PowerShell 读取最新记录：

```powershell
Get-Content -LiteralPath backend/logs/workflow-events.jsonl -Tail 20 | ForEach-Object { $_ | ConvertFrom-Json } | Select-Object timestamp,operation,outcome,run_id,dify_run_id,duration_ms,total_tokens,metrics_source
```

本次新增检查使用隔离临时数据库和模拟 Dify 响应，不调用模型、不运行 n8n、不发送消息。已验收业务链路继续沿用；新日志需要运行更新后的 API 才会产生，不会回填旧记录，也不声称已在当前容器验收。

## 增量检查结果

- 24 项直接相关检查通过，覆盖新增日志以及原有 Dify/工作流路由契约。
- 发现非有限浮点数可能导致整条日志丢失后，增加安全占位处理；仅补跑该新增边界，1 项通过。
- 新增及受影响 Python 文件通过 Ruff，Git 空白检查通过。
- 测试使用隔离临时数据库和模拟 Dify 响应，没有调用模型、运行 n8n、修改业务数据库或发送消息。
