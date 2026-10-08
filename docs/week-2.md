# Week 2：Knowledge Hub 文档接入

学习路线：Day 8–14。

按学习路线归档，计划、实施记录与阶段总结集中在本页。记录中的版本、验收结果和“当前”均对应各节写作时点；后续修订会单独注明。

[总目录](README.md#按周阅读) · [上一周](week-1.md) · [下一周](week-3.md)

<a id="contents"></a>

## 本周目录

- [SQLite 数据库设计](#database)
- [本周总结（阶段记录）](#summary)

---

<a id="database"></a>

## SQLite 数据库设计

> 本节按文档元数据首次落地的 Week 2 归档；同一数据库在 Week 6–7 增加的运行账本和销售表也保留在这里。

项目使用 SQLite 保存文档处理、工作流运行、模拟 CRM 客户与跟进记录。

数据库文件：

```text
data/enterprise_ai.db
```

<a id="database-documents-表"></a>

### documents 表

| 字段 | 类型 | 作用 |
| --- | --- | --- |
| id | INTEGER | 文档唯一编号 |
| filename | TEXT | 原始文件名 |
| file_type | TEXT | pdf、docx 或 markdown |
| content_type | TEXT | 文件 MIME 类型 |
| size | INTEGER | 文件大小，单位为字节 |
| status | TEXT | 文档处理状态 |
| created_at | TEXT | 文档创建时间 |

<a id="database-状态设计"></a>

### 状态设计

- `parsed`：文件已经成功解析。
- `failed`：文件处理失败。

<a id="database-workflow_runs-表"></a>

### workflow_runs 表

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

详细流程见 [Day 41：n8n 工作流数据库持久化](week-6.md#n8n-workflow-persistence)。


<a id="database-customers-表"></a>

### customers 表

| 字段 | 类型 | 作用 |
| --- | --- | --- |
| id | INTEGER | 内部自增主键 |
| customer_id | TEXT | 稳定客户标识，唯一 |
| company_name | TEXT | 企业名称 |
| industry | TEXT | 行业，可空 |
| sales_owner | TEXT | 销售负责人标识 |
| created_at / updated_at | TEXT | 创建和更新时间 |

sales_owner 建立查询索引。工作流使用 POST /crm/followups 在单一事务中更新客户并创建跟进，而不是先后提交两个独立写请求。

<a id="database-followup_records-表"></a>

### followup_records 表

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

<a id="database-阶段与次数"></a>

### 阶段与次数

processing_stage 取 workflow_registered、analysis_completed、crm_saved、notification_requested、notification_recorded。failure_stage 记录 unknown、ai_analysis、ai_output_validation、crm_transaction 或 notification。API 将 input_json、output_json、checkpoint_json 和 analysis_json 解析为结构化对象返回。

workflow_runs.retry_count 统计整条工作流的显式失败回放，最多 3 次。notification_attempt_count 统计通知尝试，当前最多 3 次总尝试（含首次）；明确失败后的重发必须标记 manual。二者不是同一个计数器。duplicate_count 只统计同一业务事件的重复请求。

通知结果与工作流结果分别记录：preview 模式不登记发送尝试；人工核对为 sent 或模拟重试成功不会自动把 failed 工作流改成 succeeded。新一轮通知尝试会清除旧的核对时间，通知请求标识保持稳定。

<a id="database-初始化与已有数据"></a>

### 初始化与已有数据

应用启动执行 init_database，创建缺失的表和索引，并通过 _ensure_column 补充 Day 48 新列。该机制不删除现有数据，也不等同于完整的版本迁移工具。切换历史代码前需保留数据库与 n8n 卷备份，避免把代码回退误当作数据库已回退。

当前验收和已知限制见 [Day 49 发布验收记录](week-7.md#day49)。

---

<a id="summary"></a>

## 本周总结（阶段记录）

<a id="summary-本周目标"></a>

### 本周目标

建立企业知识库的文档接入基础，使系统能够上传、解析并记录文档信息。

<a id="summary-已完成功能"></a>

### 已完成功能

- 支持上传 PDF 文件
- 支持上传 DOCX 文件
- 支持上传 Markdown 文件
- 提取文档文本和统计信息
- 使用 SQLite 保存文档元数据
- 使用 Docker Volume 持久化数据库和日志
- 增加空文件检查
- 增加不支持文件类型检查
- 增加文档解析异常处理
- 增加应用运行日志

<a id="summary-api-接口"></a>

### API 接口

| 请求方法 | 地址 | 作用 |
| --- | --- | --- |
| GET | `/health` | 检查服务运行状态 |
| POST | `/chat` | 发送聊天消息 |
| POST | `/upload` | 上传并解析文档 |

<a id="summary-支持的文件格式"></a>

### 支持的文件格式

- PDF
- DOCX
- Markdown

<a id="summary-数据库存储内容"></a>

### 数据库存储内容

当前 SQLite 数据库保存：

- 文档 ID
- 文件名
- 文件类型
- Content-Type
- 文件大小
- 解析状态
- 创建时间

<a id="summary-当前限制"></a>

### 当前限制

- 暂未保存原始文件
- 暂未保存提取出的完整文本
- 暂无文档查询和删除接口
- 暂未接入向量数据库
- 暂未实现 RAG 问答

<a id="summary-下一阶段"></a>

### 下一阶段

Week 3 将开始实现 RAG 系统，包括文本切分、向量化、检索和带来源的回答。
