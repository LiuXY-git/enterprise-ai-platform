# Day 40：n8n AI 工作流日报

## 学习目标

Day 40 使用 n8n 原生 LLM 节点完成每日工作流报告，目标包括：

- 每天 18:00 按 `Asia/Shanghai` 时区触发日报
- 支持 Webhook 指定日期进行手动回放
- 校验 `YYYY-MM-DD` 格式和真实日历日期
- 汇总执行数、成功率、耗时、Token、分类和失败事件
- 使用 `Basic LLM Chain` 与通义千问生成中文运营日报
- 对无数据日期设置事实边界，避免模型把“无记录”解释为“无风险”
- 将脱敏后的工作流和自动化结构测试纳入 Git

工作流名称：

```text
W6D40 - Daily Workflow Report
```

## 架构

```text
Daily Report Schedule ─┐
                      ├→ Prepare Report Context
Manual Report Replay ─┘          ↓
                       Load Fixed Workflow Runs
                                  ↓
                       Aggregate Daily Metrics
                                  ↓
                    Generate Daily Report Summary
                                  │
                    DashScope Qwen Chat Model
```

工作流包含 7 个节点。调度触发器与手动回放复用同一条统计和总结链路；
模型通过 n8n 原生 AI 子节点连接，不再调用 Day 39 的 FastAPI / Dify
客服工作流。

## 触发方式

`Daily Report Schedule` 每天 18:00 触发。n8n 实例时区由 Docker 环境配置为
`Asia/Shanghai`；工作流的日期计算也显式使用该时区。

手动回放使用：

```text
POST /webhook-test/w6d40-daily-workflow-report
```

请求体：

```json
{
  "report_date": "2026-09-01"
}
```

不传 `report_date` 时使用上海时区当天日期。`2026-02-30` 等不存在的日历
日期会在 `Prepare Report Context` 节点被拒绝，后续统计与模型节点不会执行。

## 固定测试数据和指标

Day 40 使用 9 条脱敏固定记录验证日报链路，不连接生产数据库，也不包含真实
客户数据。`2026-09-01` 的验收基线为：

| 指标 | 期望值 |
|---|---:|
| 总执行数 | 6 |
| 成功数 | 4 |
| 失败数 | 2 |
| 成功率 | 66.67% |
| 平均耗时 | 4 秒 |
| 累计 Token | 3060 |
| 产品 / 技术 / 敏感 / 其他 | 2 / 2 / 1 / 1 |
| 失败事件 | `mail-report-005`、`mail-report-006` |

`Aggregate Daily Metrics` 在记录数为 0 时显式返回零值，避免出现 `NaN` 或
`Infinity`。

## n8n 原生 LLM 配置

根节点使用 `Basic LLM Chain`，模型子节点使用 `OpenAI Chat Model` 的
OpenAI 兼容接口模式：

| 参数 | 值 |
|---|---|
| Model ID | `qwen3.7-plus` |
| Responses API | 关闭 |
| Sampling Temperature | `0.2` |
| Maximum Number of Tokens | `1000` |

工作流导入后需要在 n8n 中创建 Credential：

```text
API Key  = DASHSCOPE_API_KEY 的值
Base URL = https://dashscope.aliyuncs.com/compatible-mode/v1
```

`Organization ID` 留空，不启用自定义 Header。Credential 应限制为仅访问
`dashscope.aliyuncs.com`（版本支持时），并只在 n8n 中保存；禁止把 API Key
写入节点、工作流 JSON、文档或 Git。

导入仓库版 JSON 后，将该 Credential 重新绑定到
`DashScope Qwen Chat Model` 即可运行。

## Prompt 事实边界

日报 Prompt 要求模型：

- 只使用聚合节点提供的数字
- 输出标题、指标概览、风险分析和优化建议
- 不补造记录、失败原因或指标
- 无数据时将成功率写为“无执行数据，不适用”
- 无数据时只能说明无法评估稳定性，不得声称系统平稳或无风险

这组规则解决了初版无数据报告把“没有执行记录”错误推断为“系统无风险”的
问题。

## 运行态验收

2026-09-02 完成以下本地测试：

| 场景 | 输入 | 结果 |
|---|---|---|
| 正常数据 | `2026-09-01` | 指标与基线一致，生成四部分中文日报 |
| 无数据 | `2026-09-03` | 全部计数为 0，成功率显示不适用，不虚构风险结论 |
| 非法日期 | `2026-02-30` | HTTP 500，日期校验节点终止后续执行 |

正常场景中 n8n 原生 LLM Chain 和 Qwen 模型均执行成功，旧的
FastAPI / Dify HTTP 节点未保留在仓库版工作流中。

## 导出与脱敏

版本化文件：

```text
n8n/workflows/w6d40-daily-workflow-report.json
```

入库前已执行：

- 删除顶层 `id`、`versionId` 和 `meta.instanceId`
- 删除 Webhook `webhookId`
- 删除模型节点的 Credential ID 和名称引用
- 修正 Webhook Path 的前导空格
- 修正 Prompt 导出时多出的表达式前缀 `=`
- 保持 `active: false` 和空 `pinData`
- 保留节点 ID 与连线，确保导入后编辑关系完整
- 确认没有明文 API Key、真实客户信息或生产数据

## 当前限制

- 本 Day 40 工作流仍保留固定测试记录作为可复现实验基线；Day 41 已在独立持久化工作流中接入数据库并保存输入、输出、时间和用户，详见 [Day 41：n8n 工作流数据库持久化](n8n-workflow-persistence.md)
- 调度工作流尚未发布；发布前应确认 n8n 实例时区和 Credential 权限
- Webhook 仅用于本地回放，尚未增加认证、签名、限流和重放保护
- LLM 输出是自然语言，关键指标仍应以聚合节点结果作为事实来源
- 当前没有邮件、IM 或工单投递节点，日报只作为执行结果返回

## Day 40 验收清单

| 验收项 | 结果 |
|---|---|
| 每日调度与手动回放双触发 | 通过 |
| 真实日历日期校验 | 通过 |
| 固定数据筛选与指标聚合 | 通过 |
| 正常、无数据、非法日期测试 | 通过 |
| n8n 原生 LLM Chain + Qwen | 通过 |
| 无数据事实边界 | 通过 |
| 工作流保持未发布 | 通过 |
| 实例 ID、Webhook ID、Credential 引用清理 | 通过 |
| 无明文密钥和真实客户数据 | 通过 |
| 自动化结构测试 | 通过 |

## 相关文档

- [Day 39：n8n AI 邮件助手](n8n-ai-email-assistant.md)
- [Day 38：n8n 连接 AI 工作流](n8n-ai-integration.md)
- [n8n 基础与本地部署](n8n-foundation.md)
