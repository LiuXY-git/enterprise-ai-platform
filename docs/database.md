# SQLite 数据库设计

项目使用 SQLite 保存文档处理、工作流运行、模拟 CRM 客户与跟进记录。

数据库文件：

```text
data/enterprise_ai.db
```

## documents 表

| 字段 | 类型 | 作用 |
| --- | --- | --- |
| id | INTEGER | 文档唯一编号 |
| filename | TEXT | 原始文件名 |
| file_type | TEXT | pdf、docx 或 markdown |
| content_type | TEXT | 文件 MIME 类型 |
| size | INTEGER | 文件大小，单位为字节 |
| status | TEXT | 文档处理状态 |
| created_at | TEXT | 文档创建时间 |

## 状态设计

- `parsed`：文件已经成功解析。
- `failed`：文件处理失败。

## workflow_runs 表

`workflow_runs` 记录 n8n 自动化工作流的完整生命周期。

| 字段 | 类型 | 作用 |
| --- | --- | --- |
| id | INTEGER | 数据库自增主键 |
| run_id | TEXT | 平台工作流运行 ID，全局唯一 |
| event_id | TEXT | 上游业务事件 ID |
| workflow_name | TEXT | 工作流稳定名称 |
| source | TEXT | 请求来源 |
| requester | TEXT | 请求者标识 |
| report_date | TEXT | 日报归属日期 |
| status | TEXT | 运行状态 |
| category | TEXT | 业务分类 |
| priority | TEXT | 优先级 |
| input_json | TEXT | JSON 格式输入 |
| output_json | TEXT | JSON 格式输出 |
| processing_stage | TEXT | 当前处理阶段 |
| checkpoint_json | TEXT | 可选的 AI 分析检查点 |
| failure_stage | TEXT | 可选的失败阶段 |
| error_type | TEXT | 错误类型 |
| error_message | TEXT | 错误说明 |
| n8n_execution_id | TEXT | n8n 执行 ID |
| retry_count | INTEGER | 失败回放次数 |
| duplicate_count | INTEGER | 重复事件次数 |
| elapsed_time | REAL | 执行耗时（秒） |
| total_tokens | INTEGER | AI Token 用量 |
| started_at | TEXT | 开始时间 |
| finished_at | TEXT | 结束时间 |
| created_at | TEXT | 创建时间 |
| updated_at | TEXT | 最后更新时间 |

状态允许值：

- `running`
- `succeeded`
- `failed`
- `needs_human_review`

`(workflow_name, event_id)` 使用唯一约束实现业务事件幂等；
`n8n_execution_id` 使用非空唯一索引，供 Error Trigger 根据执行号保存失败。

详细流程见 [Day 41：n8n 工作流数据库持久化](n8n-workflow-persistence.md)。


## customers 表

| 字段 | 类型 | 作用 |
| --- | --- | --- |
| id | INTEGER | 内部自增主键 |
| customer_id | TEXT | 稳定客户标识，唯一 |
| company_name | TEXT | 企业名称 |
| industry | TEXT | 行业，可空 |
| sales_owner | TEXT | 销售负责人标识 |
| created_at / updated_at | TEXT | 创建和更新时间 |

sales_owner 建立查询索引。工作流使用 POST /crm/followups 在单一事务中更新客户并创建跟进，而不是先后提交两个独立写请求。

## followup_records 表

| 字段 | 类型 | 作用 |
| --- | --- | --- |
| id | INTEGER | 内部自增主键 |
| followup_id | TEXT | 跟进记录标识，唯一 |
| customer_id | TEXT | 关联 customers.customer_id |
| run_id | TEXT | 关联 workflow_runs.run_id，唯一 |
| event_id | TEXT | 业务事件标识 |
| requirement_snapshot | TEXT | 本次需求快照 |
| analysis_json | TEXT | 结构化分析 |
| priority | TEXT | high 或 normal |
| review_status | TEXT | not_required 或 pending |
| review_reasons_json | TEXT | 人工复核原因 |
| notification_mode | TEXT | preview 或 send |
| notification_channel | TEXT | feishu、wecom 或空 |
| notification_status | TEXT | pending、preview、sent、failed、delivery_unknown、skipped |
| notification_request_key | TEXT | 稳定通知请求标识，可空 |
| notification_message_id | TEXT | 上游消息标识，可空 |
| notification_error_code | TEXT | 安全错误码，可空 |
| notification_attempt_count | INTEGER | 通知尝试次数，初值 0 |
| notification_last_attempt_at | TEXT | 最近一次尝试时间，可空 |
| notification_resolved_at | TEXT | 人工核对时间，可空 |
| created_at / updated_at | TEXT | 创建和更新时间 |

customer_id、event_id、notification_status 建立普通索引；非空 notification_request_key 使用部分唯一索引。客户与运行外键均为 ON DELETE RESTRICT，每次连接启用外键检查。run_id 唯一约束保证同一运行至多一条跟进；事务失败同时回滚客户与跟进写入。

## 阶段与次数

processing_stage 取 workflow_registered、analysis_completed、crm_saved、notification_requested、notification_recorded。failure_stage 记录 unknown、ai_analysis、ai_output_validation、crm_transaction 或 notification。API 将 input_json、output_json、checkpoint_json 和 analysis_json 解析为结构化对象返回。

workflow_runs.retry_count 统计整条工作流的显式失败回放，最多 3 次。notification_attempt_count 统计通知尝试，当前最多 3 次总尝试（含首次）；明确失败后的重发必须标记 manual。二者不是同一个计数器。duplicate_count 只统计同一业务事件的重复请求。

通知结果与工作流结果分别记录：preview 模式不登记发送尝试；人工核对为 sent 或模拟重试成功不会自动把 failed 工作流改成 succeeded。新一轮通知尝试会清除旧的核对时间，通知请求标识保持稳定。

## 初始化与已有数据

应用启动执行 init_database，创建缺失的表和索引，并通过 _ensure_column 补充 Day 48 新列。该机制不删除现有数据，也不等同于完整的版本迁移工具。切换历史代码前需保留数据库与 n8n 卷备份，避免把代码回退误当作数据库已回退。

当前验收和已知限制见 [Day 49 发布验收记录](week-7-notes.md#day49)。
