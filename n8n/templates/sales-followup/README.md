# 销售线索与 CRM 模板

适用：分析企业线索、整理缺失信息和下一步行动，写入模拟 CRM。不包含报价承诺、交付承诺或真实通知发送。

## 导出与依赖

导入 [销售助手](../../workflows/w7d47-sales-followup-assistant.json)，依赖包含 Day 48 实现的 API、SQLite。在 DashScope Qwen Chat Model 节点绑定 openAiApi 类型的 DashScope OpenAI 兼容凭据，模型沿用 qwen3.7-plus。销售使用自身 AI/CRM 错误分支，不要求绑定邮件错误处理器。

入口：POST `/webhook-test/w7d47-sales-followup-assistant`；已发布时使用 `/webhook/w7d47-sales-followup-assistant`。

## 输入

| 字段 | 校验与约定 |
| --- | --- |
| event_id / customer_id / sales_owner | 必填，1–128 字符，仅字母、数字、点、下划线、冒号、连字符 |
| company_name | 必填，去除首尾空白后 1–200 字符 |
| requirement | 必填，去除首尾空白后 1–4000 字符 |
| report_date | 必填，真实的 YYYY-MM-DD 日期 |
| industry / budget_range | 可省略或为 null，分别最多 100 / 200 字符 |
| purchase_window_days | 可省略或为 null；有值时为 0–365 的整数 |
| replay | 可选布尔值，默认 false |

拒绝未知字段；无效输入返回 HTTP 422。不能从请求体设置 notification_mode 或将 preview 改成真实发送。

样例：[常规线索](examples/normal.json)、[报价与交付复核候选](examples/review-candidate.json)。后者包含风险内容，预期模型识别风险后进入人工复核，但 Day 50 只验证输入有效，不声称已验证模型风险识别或固定分支。

## 输出与恢复

成功输出 run_id、followup_id、customer_id、status、requires_human_review、analysis、notification。run_id 是平台运行 ID；有风险时进入 needs_human_review。通知为 preview，需复核时可能为 skipped，不能视为真实送达。耗时和 Token 沿用现有 null 语义。

业务名称为 `sales-followup-assistant`。同一 event_id 去重，同一 run_id 只创建一条跟进。CRM 失败可显式回放并复用分析检查点；CRM 已保存后整条回放被拒绝。通知 delivery_unknown 先人工核对，不能直接重发；通知 sent 不会自动完成原 failed 工作流。

已通过业务验收直接沿用 [Day 49 证据](../../../docs/week-7-notes.md#day49)。更详细说明见 [销售助手](../../../docs/n8n-sales-followup-assistant.md)。

## Day 52 配置归属

销售分析的模型位于 n8n 的 `DashScope Qwen Chat Model` 节点，凭据绑定在 n8n Credentials 中。后端 `LLM_PROVIDER`、`QWEN_MODEL` 和 `DASHSCOPE_API_KEY` 不会自动修改该节点。API 配置自检不验证 n8n 凭据。通知仍为 preview。

配置优先级、完整字段与生效方式见 [配置中心说明](../../../docs/week-8-notes.md#day52)。
