# Day 49 发布验收记录

记录日期：2026-09-13，时区 Asia/Shanghai。工作分支为 feature/day49-workflow-center-v0.5，基线提交为 992d0fd。Day 49 增量包括清单、脚本和文档，后端业务代码与销售工作流导出沿用 Day 48；本地定版日期为 2026-09-14，组件标签为 workflow-center-v0.5.0。

本记录汇总已完成验收，不触发重新测试。证据中的 UTC 时间比本地时间早 8 小时，因此 JSON 中 2026-09-12T16 时段对应本地 2026-09-13 凌晨。所有客户和消息标识均为测试数据；通知核对使用模拟结果。

## 本轮业务结果

| 场景 | run_id | 工作流状态 | 通知状态 | 通知尝试 | 证据 |
| --- | --- | --- | --- | --- | --- |
| confirmed_delivered | `a06b1757-baf5-4139-832a-0eef125b5935` | failed | sent | 1 | [JSON](evidence/day49/day49-notification-resolution-7975a813112249e394725f60c88a6ff4.json) |
| confirmed_not_delivered | `4488410b-af08-403a-b490-c8a6e09198e1` | failed | sent | 2 | [JSON](evidence/day49/day49-notification-resolution-7975a813112249e394725f60c88a6ff4.json) |
| Production 正常与重复事件 | `f5d944b0-3468-460f-bf47-a3bbbc83e650` | succeeded | preview | 0 | [JSON](evidence/day49/day49-production-fc8d9aebad1e42b5b658d74dd57e155b.json) |
| failed | `85148ae8-feac-4b3a-8897-38cbbd311a24` | failed | failed | 1 | [JSON](evidence/day49/day49-replay-guard-17e171ec3a4a470b8118a25c512d0268.json) |
| delivery_unknown | `dc337f30-160d-4b64-8a30-5807004537c5` | failed | delivery_unknown | 1 | [JSON](evidence/day49/day49-replay-guard-17e171ec3a4a470b8118a25c512d0268.json) |

### CRM 保存后的回放保护

批次 17e171ec3a4a470b8118a25c512d0268。两类通知异常的整条回放均返回预期 409，工作流、客户、跟进记录及跟进列表不变。工作流重试次数为 0、通知尝试为 1、跟进为 1 条，恢复策略要求人工处理。

### 人工通知核对与重试

批次 7975a813112249e394725f60c88a6ff4。确认已送达后不重发，尝试保持 1；确认未送达后显式人工重试并模拟成功，尝试为 2。共 14 次禁止操作返回 409 且记录不变，客户资料和 CRM 业务字段不变，通知请求标识稳定。

两条通知最终均为 sent，但工作流保持 failed、retry_count 保持 0。已送达场景 manual_retry_verified=false 表示无需执行重试；workflow_completion_pending=true 表示通知恢复后的业务运行收尾尚未实现。

### Production 正常与重复事件

原事件为 day49-production-02db679f027d43db9411a2bc1f7c5df4，run_id 为 f5d944b0-3468-460f-bf47-a3bbbc83e650，followup_id 为 378efd7e-735a-4bb7-a043-ed44eda0ccd8。

首次模型分析与业务处理成功。原脚本因为 JSON 字段顺序不同，在分析比较处误报并停止，尚未提交重复请求。修复后通过批次 fc8d9aebad1e42b5b658d74dd57e155b 复用首次结果续跑，仅补完同事件重复检查。

最终工作流 succeeded，阶段 notification_recorded，检查点归属正确。通知 preview、尝试次数为 0；重复请求返回原 run_id/event_id，duplicate=true、processed=false。duplicate_count=1、retry_count=0、跟进=1 条，CRM 完整内容不变。HTTP 与持久化验收完成，无需额外节点轨迹核对；本记录不声称读取过本轮节点轨迹。

## 沿用的基线证据

| 检查 | 已记录结果 | 来源与使用范围 |
| --- | --- | --- |
| AI 非法结构与服务异常 | 分别进入人工复核和 failed | Day 48 联调记录 |
| AI 分类最终修复 | 12 个离线分类回归通过 | Day 48 最终源码与导出记录 |
| CRM 事务失败与检查点恢复 | 回滚；复用检查点和 run_id 恢复成功 | Day 48 CRM 故障记录 |
| 全量 pytest | 415 passed | Day 48 基线，并非 Day 49 重跑结果 |
| Ruff 与节点回归 | 通过 | Day 48 最终代码检查 |
| Docker/Compose 与 OpenAPI | 健康检查、配置和新增接口验收通过 | Day 48 记录；Day 49 起始 API/n8n 也为 healthy |
| Day 49 清单及销售相关检查 | 21 passed，Ruff 通过 | Day 49 第二步局部检查，含 7 项新增清单测试 |

AI 两类故障联调早于 Day 48 分类代码最后修复；最后修复有 12 个离线回归且导出已同步，按既有证据沿用，不将其表述为 Day 49 新一轮 AI 故障联调。详情见 [Day 48 验收记录](day48-failure-recovery-results.md)。

## 验收脚本修复

- 有序字典摘要先转成 PSCustomObject，避免 Select-Object 输出 null；保存的原 JSON 证据不受影响。
- JSON 对象按键规范化后比较，忽略字段顺序，保留类型、值和数组顺序差异。
- PowerShell 5.1 读取续跑证据显式使用 UTF-8，避免中文数据按本地编码读取。
- 失败报告保留输入和已知标识，续跑生成新报告并记录原批次，不重复首次成功处理。

这些修复均有隔离环境验证，真实 Production 的最后未完成步骤也已由用户续跑通过。脚本和参数见 [Day 49 可重复验收说明](../scripts/day49/README.md)。

## 发布状态与剩余事项

业务验收已完成，本轮文档同步直接使用以上结果。未受本次改动影响的检查不重复执行；只有相关代码改变、失败或新增风险时才安排对应重验。

清单 release_status=released、release_date=2026-09-14 表示本地组件版本定版。维护者负责 GitHub 推送及 Release 发布；线上状态以远端记录为准。业务验收结果沿用本记录，本地发布元数据调整不触发重新执行业务验收。

已知功能边界：销售通知为预览，通知恢复后的工作流收尾待实现，企业微信真实发送待外部条件满足。发布范围见 [v0.5.0 发布说明](workflow-center-v0.5.md)。
