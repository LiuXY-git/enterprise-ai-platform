# Day 47：n8n 销售线索跟进助手

## 学习目标

Day 47 将销售线索输入校验、工作流运行登记、结构化 AI 分析、模拟 CRM
持久化和通知预览串成一条可发布的 n8n 工作流。

本日完成：

- Webhook 接收并严格校验销售线索
- 使用 `(workflow_name, event_id)` 拦截重复事件
- 使用 Qwen 模型和 JSON Schema 生成结构化销售分析
- 通过确定性规则计算优先级和人工复核状态
- 在一个 CRM API 请求中保存客户和跟进记录
- 分别保存工作流状态和通知状态
- 为无需人工复核的结果生成飞书通知预览

## 工作流

版本化文件：

```text
n8n/workflows/w7d47-sales-followup-assistant.json
```

主流程：

```text
Receive Sales Lead
  ↓
Normalize Sales Lead
  ↓
Input Valid?
  ├─ false → Reject Invalid Input
  └─ true  → Start Workflow Run
                   ↓
            Restore Workflow Context
                   ↓
              Should Process?
              ├─ false → Return Duplicate Result
              └─ true  → Analyze Sales Lead
                               ↓
                    Build CRM Follow-up Payload
                               ↓
                       Save CRM Follow-up
                               ↓
                      Finish Workflow Run
                               ↓
                      Return Success Result
```

`Analyze Sales Lead` 使用独立的 Chat Model 和 Structured Output Parser
连接。输出必须包含 `summary`、`needs`、`missing_information`、
`next_actions` 和 `risk_flags`，Schema 禁止额外字段。

## 导入与配置

仓库中的工作流保持 `active: false`，并移除了工作流 ID、版本 ID、Webhook ID、
Credential 引用和实例元数据。导入后：

1. 打开 `DashScope Qwen Chat Model`。
2. 选择当前 n8n 实例中的 DashScope OpenAI 兼容凭据。
3. 确认模型为 `qwen3.7-plus`、最大输出 Token 为 1000、温度为 0.2。
4. 确认 API 和 n8n 容器位于同一个 Compose 网络。
5. 发布工作流。

测试地址：

```text
POST http://localhost:5678/webhook-test/w7d47-sales-followup-assistant
```

发布地址：

```text
POST http://localhost:5678/webhook/w7d47-sales-followup-assistant
```

工作流容器通过以下内部地址调用 API：

| 方法 | 地址 | 作用 |
|---|---|---|
| `POST` | `http://api:8000/workflow-runs/start` | 登记运行并判断是否处理 |
| `POST` | `http://api:8000/crm/followups` | 原子保存客户和跟进记录 |
| `PATCH` | `http://api:8000/workflow-runs/{run_id}/result` | 保存最终工作流状态 |

## 业务规则

- 未定义字段、空白必填字段、非法标识符、非法日期和越界采购窗口返回 422。
- 相同事件返回已有运行，不再次调用 AI 或写入 CRM。
- 采购评估窗口小于或等于 30 天时优先级为 `high`，其他情况为 `normal`。
- 发现能力、价格、交付、Prompt 注入或敏感信息风险时进入人工复核。
- 人工复核结果保存为 `needs_human_review`，通知状态为 `skipped`。
- 无需复核时保存为 `succeeded`，通知状态为 `preview`。
- 预览模式只生成通知正文，不调用真实飞书消息接口。

## 真实验收

2026-09-10 完成本地 Docker、n8n 和 SQLite 联调：

| 场景 | 结果 |
|---|---|
| 未定义字段 | HTTP 422，返回 `notification_recipient` 不允许 |
| 重复事件 | 命中重复分支，工作流成功结束且未重复分析 |
| 高优先级风险线索 | 保存 CRM，运行状态为 `needs_human_review`，通知跳过 |
| 普通线索 | 保存 CRM，运行状态为 `succeeded`，生成飞书通知预览 |
| CRM 查询 | 客户、跟进记录和工作流运行状态一致 |
| Production URL | 已发布地址返回 HTTP 200 和完整结果 |

生产地址验收生成独立的 `run_id` 和 `followup_id`，响应包含结构化分析、
优先级、人工复核结果和通知预览。验收数据均为虚构数据。

Windows PowerShell 5.1 直接显示部分 UTF-8 JSON 时可能出现乱码；n8n 响应、
数据库内容和字段断言均已确认正常。

## 当前限制

- 模型凭据必须在导入后的 n8n 实例中重新选择。
- 当前通知模式固定为 `preview`，不会发送真实消息。
- API 尚未增加认证和租户隔离，只适用于当前本地可信网络。
- Day 48 将补充 AI、CRM 和通知故障处理及分阶段恢复。

## 相关文档

- [销售线索跟进助手设计](sales-followup-design.md)
- [销售线索跟进助手验收方案](sales-followup-acceptance.md)
- [n8n 工作流数据库持久化](n8n-workflow-persistence.md)
- [飞书开放平台接入基础](feishu-open-platform.md)
