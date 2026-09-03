# SQLite 数据库设计

项目使用 SQLite 保存文档处理记录和自动化工作流运行记录。

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
- `failed`：文件解析失败，计划在 Day 13 使用。

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
