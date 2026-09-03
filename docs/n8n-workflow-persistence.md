# Day 41：n8n 工作流数据库持久化

## 学习目标

Day 41 将 Day 39 的 AI 邮件助手接入 SQLite，保存工作流输入、输出、时间、
请求者、执行状态和错误信息，并增加重复事件拦截及失败回放能力。

本日完成：

- 新增 `workflow_runs` 表和索引
- 新增工作流登记、完成、失败、查询 API
- 使用 `(workflow_name, event_id)` 保证业务事件幂等
- 使用 n8n `Error Trigger` 自动保存生产执行失败
- 对失败记录提供最多 3 次回放
- 将人工审核、成功、重复、失败和回放场景纳入真实验收

## 架构

```text
Webhook
  ↓
Normalize Email Request
  ↓
POST /workflow-runs/start
  ↓
Should Process?
  ├─ false → Build Duplicate Response → Webhook Response
  └─ true  → 分类与 AI / 人工审核
                  ↓
             PATCH /workflow-runs/{run_id}/result
                  ↓
             Webhook Response

生产执行失败
  ↓
Error Trigger
  ↓
PATCH /workflow-runs/executions/{n8n_execution_id}/failure
```

## 数据库设计

`workflow_runs` 保存以下核心信息：

| 字段 | 作用 |
|---|---|
| `run_id` | 平台生成的工作流运行 ID |
| `event_id` | 上游业务事件 ID |
| `workflow_name` | 工作流稳定名称 |
| `source` / `requester` | 来源与请求者 |
| `report_date` | 日报归属日期 |
| `status` | `running`、`succeeded`、`failed` 或 `needs_human_review` |
| `input_json` / `output_json` | 完整输入与输出 |
| `n8n_execution_id` | n8n 执行 ID，用于错误回调关联 |
| `retry_count` | 失败回放次数 |
| `duplicate_count` | 重复事件命中次数 |
| `elapsed_time` / `total_tokens` | AI 调用耗时与 Token |
| `error_type` / `error_message` | 最后一次失败信息 |
| `started_at` / `finished_at` | 开始与结束时间 |

唯一约束：

```text
UNIQUE(workflow_name, event_id)
```

同一工作流再次收到相同 `event_id` 时只增加 `duplicate_count`，不会再次调用
分类器或 AI。只有状态为 `failed` 且请求显式携带 `replay: true` 时才允许回放。

## API

| 方法 | 地址 | 作用 |
|---|---|---|
| `POST` | `/workflow-runs/start` | 登记新运行、拦截重复事件或开始回放 |
| `PATCH` | `/workflow-runs/{run_id}/result` | 保存成功或人工审核结果 |
| `PATCH` | `/workflow-runs/executions/{execution_id}/failure` | 按 n8n 执行号保存失败 |
| `GET` | `/workflow-runs/{run_id}` | 查询单条运行 |
| `GET` | `/workflow-runs?report_date=YYYY-MM-DD` | 查询指定日期运行 |

## n8n 工作流

版本化文件：

```text
n8n/workflows/w6d41-persistent-ai-email-assistant.json
n8n/workflows/w6d41-workflow-error-handler.json
```

仓库版工作流保持 `active: false`，并删除以下实例专属数据：

- 工作流 ID、版本 ID 和发布状态
- Webhook ID
- Credential 引用
- 项目、用户和实例元数据

导入后必须先发布错误处理工作流，再在主工作流设置中将它选为
`Error Workflow`。错误工作流通过执行号关联运行记录，因此不需要在失败分支
传递输入数据。

## 回放语义

首次执行失败后，数据库状态为 `failed`。相同事件再次请求时：

- `replay: false`：视为重复事件，不重新处理
- `replay: true`：状态改回 `running`，`retry_count` 加 1
- 回放成功：状态改为 `succeeded`，清空旧错误字段
- 超过 3 次：API 返回冲突，不再执行

回放继续使用首次保存的 `input_json`，避免调用者在重试时悄悄修改原始业务
输入。

## 真实验收

2026-09-03 完成 Docker 与 n8n 真实运行验收：

| 场景 | 结果 |
|---|---|
| 人工审核 | 保存为 `needs_human_review` |
| 正常 AI 请求 | 保存为 `succeeded`，记录分类、耗时和 Token |
| 重复事件 | 返回 `duplicate`，原任务不重复执行，计数加 1 |
| 自动执行失败 | Error Trigger 保存为 `failed` 和错误详情 |
| 失败回放 | 复用原 `run_id`，成功后 `retry_count = 1` |

验收同时确认：SQLite 中的中文输入和输出保持 UTF-8。Windows PowerShell 5.1
显示 FastAPI JSON 时可能出现乱码，这是客户端响应解码问题，不是数据库损坏。

## 当前限制

- API 尚未增加认证和租户隔离，只适用于当前本地可信网络
- `source`、`requester` 和事件 ID 目前使用简单格式约束
- 失败回放由调用者显式设置 `replay: true`，尚未配置定时自动重试
- Error Trigger 只处理已绑定工作流的自动执行失败，手动测试执行不会触发

## 相关文档

- [Day 40：n8n AI 工作流日报](n8n-daily-workflow-report.md)
- [Day 39：n8n AI 邮件助手](n8n-ai-email-assistant.md)
- [数据库设计](database.md)
