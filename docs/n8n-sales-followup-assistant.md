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
- Day 48 已加入 AI/CRM 错误分支和 CRM 检查点恢复；通知异常与人工核对通过后端状态接口模拟验收。真实通知发送及其 n8n 编排未包含在本轮验收中。

## 相关文档

- [销售线索跟进助手设计](sales-followup-design.md)
- [销售线索跟进助手验收方案](sales-followup-acceptance.md)
- [n8n 工作流数据库持久化](n8n-workflow-persistence.md)
- [飞书开放平台接入基础](feishu-open-platform.md)


## Day 48 故障恢复

工作流保持原名称和 Webhook 路径，导出文件包含 26 个节点。导出默认 inactive，
不含 Credential 引用、Webhook 实例 ID、固定执行数据或实例版本信息。

- AI 结构校验失败转人工复核；模型服务错误记录 failed。
- AI 分析成功后保存 analysis_completed 检查点，再写入 CRM。
- CRM 失败后使用同一事件加 `replay: true` 恢复；复用原 run_id 和检查点，跳过 AI。
- Save CRM Follow-up 的请求体为 `{{ JSON.stringify($json.checkpoint_data ?? $json) }}`，兼容普通与恢复分支。
- Classify AI Failure 仅读取 error 的指定元数据，避免业务字段中的数字和关键词干扰分类。
- CRM 已保存后的整条工作流回放返回冲突，通知处理改用专用状态接口，避免重复分析与写入。

通知 API：`POST /crm/followups/{followup_id}/notification-attempts` 登记尝试；
`PATCH /crm/followups/{followup_id}/notification` 记录结果；
`PATCH /crm/followups/{followup_id}/notification-resolution` 记录人工核对。
这些接口只管理本地状态，不发送消息。模拟 message_id 不代表真实平台消息。
人工核对通知不会自动把原 failed 工作流改成 succeeded；最终运行状态仍需按业务结果处理。

Test URL 需要本次监听注册后才能调用。测试脚本遇到明确的“Webhook 未注册”404可以等待重试；
超时、503 或其他响应不得盲目重发。Production URL 仅使用已发布版本。
2026-09-12 用户已发布当前版本，Day 48 Production URL 正常处理、检查点保存及重复事件去重验收通过。

验收证据及命令见 [Day 48 验收记录](week-7-notes.md#day48)。


## Day 49 发布验收

Production 正常与重复事件、CRM 保存后的回放保护、人工通知核对及受限重试均已通过。销售工作流导出和后端业务实现沿用 Day 48 版本，Day 49 的修改集中在清单、脚本和文档。

Production 首次成功后的分析比较曾因 JSON 字段顺序误报，修复脚本后复用同一 run_id 续跑，仅补完重复请求；未重新执行首次模型分析。最终 duplicate_count 为 1，跟进仅一条，CRM 不变，通知 preview 且发送尝试为 0。

本轮 HTTP 与持久化验收已完成，不再要求追加节点轨迹核对。证据、沿用结果与限制见 [Day 49 发布验收记录](week-7-notes.md#day49)，运行方法见 [Day 49 脚本说明](../scripts/day49/README.md)。
