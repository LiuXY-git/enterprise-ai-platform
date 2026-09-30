# Week 7：企业平台集成与销售流程验收

路线范围：Day 43–49。本文件包含 2 个每日章节，保留完整步骤、命令、验收记录与能力边界。

本周内容按日期排列，各节保留对应日期的实施状态，当前进度以[项目首页](../README.md)为准。

本文件收录 Day 48–49；Day 43–47 的阶段记录见[Week 7 总结](week-7-summary.md)。

[返回周目录](README.md#按周阅读) · [本周总结](week-7-summary.md)

## 本周目录

- [Day 48 故障恢复验收记录](#day48)
- [Day 49 发布验收记录](#day49)

---

<a id="day48"></a>

## Day 48 故障恢复验收记录


记录日期：2026-09-12。分支：feature/day48-failure-recovery；本记录随 Day 48 功能提交保存。
以下联调结果来自用户提供的脚本成功输出和 n8n 执行截图，所有业务数据均为测试数据。

| 场景 | run_id | 结果 |
|---|---|---|
| 正常分析检查点 | aeb24059-737f-41ad-bfdb-034192ba79f8 | succeeded；检查点及 CRM 保存 |
| CRM 故障及恢复 | 00045f52-12f9-4f1b-9645-78ee587ddea5 | 故障时客户和跟进回滚；恢复复用检查点，retry_count 2→3，最终 succeeded |
| AI 非法结构 | 13733075-f9c3-4c69-9fb0-f77b6f3e35eb | needs_human_review；无 CRM、检查点或通知 |
| AI 服务异常 | 27de39bf-ef61-4bf8-986c-252ff15f8549 | failed / ai_analysis；无 CRM 或检查点 |
| 模拟通知明确失败 | 1cd2de32-4afd-4b85-b140-2990da9db654 | failed；CRM 保留，尝试 1 次，禁止自动重发 |
| 模拟通知结果不确定 | 4e82b6bd-076d-4081-b887-b5ff513bd273 | delivery_unknown；核对前阻止人工与自动重发 |
| 模拟确认已送达 | 225177a8-fe37-4889-b951-6e554dc352ce | 通知 sent；尝试仍为 1，禁止重发 |
| 模拟确认未送达并人工重试 | 25b739d8-768f-464e-888a-6322630d65c5 | 通知 sent；尝试 2 次，稳定请求标识未改变 |

通知测试只验证状态接口及重发约束，没有调用真实飞书发送接口。
人工核对测试仅断言通知 sent，没有断言工作流最终 succeeded。
AI 结构与服务异常联调先于分类代码最后修复；最后修复通过 12 个离线分类回归用例，
最新 n8n 导出已确认包含该修复。

<a id="day48-可重复验证"></a>

### 可重复验证

从项目根目录执行（需要本地 Day 48 API；每次生成新的模拟数据）：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/day48/day48-test-notification-states.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/day48/day48-test-notification-resolution.ps1
python -m pytest -q
python -m ruff check .
node tests/test_day48_workflow_nodes.cjs
git diff --check
docker compose config --quiet
```

脚本使用 ASCII 源码，兼容 Windows PowerShell 5.1；不会发送消息。
节点测试实际执行导出中的分类和 CRM 请求体代码，验证普通/恢复数据形状及检查点归属。

<a id="day48-收尾状态"></a>

### 收尾状态

已同步最新 n8n 编辑版本到可移植工作流文件，并移除实例元数据和凭据引用。
新增回放入口保护：CRM 保存后禁止整条回放；回归测试同时验证拒绝时原状态完全不变。
API 已重建并达到 healthy；部署后的回放保护测试通过。
n8n 当前工作流已发布；Git 合并与推送由用户执行收尾脚本。
Day 48 Production URL 正常与重复事件测试通过；真实消息发送链路未验收。

<a id="day48-本轮质量检查结果"></a>

### 本轮质量检查结果

2026-09-12 在最终源码上完成：

- 全量 pytest：415 passed，1 个 ChromaDB 弃用警告。
- Ruff：All checks passed。
- JavaScript：12 个分类回归用例通过；CRM 普通/恢复请求体及检查点归属测试通过。
- Git diff --check：通过。
- Docker Compose config --quiet：通过；现有 API 和 n8n 容器均 healthy。
- 本机 OpenAPI：检查点、失败、恢复查询、通知尝试、通知结果、人工核对共 6 条接口均存在。

重建后使用两条通知异常记录请求回放，均返回预期 409；workflow、followup 和 retry_count 均保持不变。
<a id="day48-发布后最终验收"></a>

### 发布后最终验收

根据用户提供的实际执行输出：

- 回放保护：`1cd2de32-4afd-4b85-b140-2990da9db654`（failed）和 `4e82b6bd-076d-4081-b887-b5ff513bd273`（delivery_unknown）均返回 HTTP 409，重试次数仍为 0，运行和跟进记录未改变。
- Production event_id：`day48-production-3a8ef52373904928b308016861c3fb9c`。
- Production run_id：`0a6f8b52-e24e-46dc-8c32-27f1f1b0541e`。
- Production followup_id：`22e4566b-3559-4427-baf8-d1941a99ffad`。
- 最终状态 succeeded，阶段 notification_recorded，检查点已保存，通知状态 preview。
- 相同事件重复提交被识别；duplicate_count 为 1，followup_count 为 1，CRM 内容不变。

复现脚本：`scripts/day48/day48-test-production.ps1`；回放保护脚本为 `scripts/day48/day48-test-replay-guard.ps1`，后者依赖上述保留的测试记录。

---

<a id="day49"></a>

## Day 49 发布验收记录


记录日期：2026-09-13，时区 Asia/Shanghai。工作分支为 feature/day49-workflow-center-v0.5，基线提交为 992d0fd。Day 49 增量包括清单、脚本和文档，后端业务代码与销售工作流导出沿用 Day 48；本地定版日期为 2026-09-14，组件标签为 workflow-center-v0.5.0。

本记录汇总已完成验收，不触发重新测试。证据中的 UTC 时间比本地时间早 8 小时，因此 JSON 中 2026-09-12T16 时段对应本地 2026-09-13 凌晨。所有客户和消息标识均为测试数据；通知核对使用模拟结果。

<a id="day49-本轮业务结果"></a>

### 本轮业务结果

| 场景 | run_id | 工作流状态 | 通知状态 | 通知尝试 | 证据 |
| --- | --- | --- | --- | --- | --- |
| confirmed_delivered | `a06b1757-baf5-4139-832a-0eef125b5935` | failed | sent | 1 | [JSON](evidence/day49/day49-notification-resolution-7975a813112249e394725f60c88a6ff4.json) |
| confirmed_not_delivered | `4488410b-af08-403a-b490-c8a6e09198e1` | failed | sent | 2 | [JSON](evidence/day49/day49-notification-resolution-7975a813112249e394725f60c88a6ff4.json) |
| Production 正常与重复事件 | `f5d944b0-3468-460f-bf47-a3bbbc83e650` | succeeded | preview | 0 | [JSON](evidence/day49/day49-production-fc8d9aebad1e42b5b658d74dd57e155b.json) |
| failed | `85148ae8-feac-4b3a-8897-38cbbd311a24` | failed | failed | 1 | [JSON](evidence/day49/day49-replay-guard-17e171ec3a4a470b8118a25c512d0268.json) |
| delivery_unknown | `dc337f30-160d-4b64-8a30-5807004537c5` | failed | delivery_unknown | 1 | [JSON](evidence/day49/day49-replay-guard-17e171ec3a4a470b8118a25c512d0268.json) |

<a id="day49-crm-保存后的回放保护"></a>

#### CRM 保存后的回放保护

批次 17e171ec3a4a470b8118a25c512d0268。两类通知异常的整条回放均返回预期 409，工作流、客户、跟进记录及跟进列表不变。工作流重试次数为 0、通知尝试为 1、跟进为 1 条，恢复策略要求人工处理。

<a id="day49-人工通知核对与重试"></a>

#### 人工通知核对与重试

批次 7975a813112249e394725f60c88a6ff4。确认已送达后不重发，尝试保持 1；确认未送达后显式人工重试并模拟成功，尝试为 2。共 14 次禁止操作返回 409 且记录不变，客户资料和 CRM 业务字段不变，通知请求标识稳定。

两条通知最终均为 sent，但工作流保持 failed、retry_count 保持 0。已送达场景 manual_retry_verified=false 表示无需执行重试；workflow_completion_pending=true 表示通知恢复后的业务运行收尾尚未实现。

<a id="day49-production-正常与重复事件"></a>

#### Production 正常与重复事件

原事件为 day49-production-02db679f027d43db9411a2bc1f7c5df4，run_id 为 f5d944b0-3468-460f-bf47-a3bbbc83e650，followup_id 为 378efd7e-735a-4bb7-a043-ed44eda0ccd8。

首次模型分析与业务处理成功。原脚本因为 JSON 字段顺序不同，在分析比较处误报并停止，尚未提交重复请求。修复后通过批次 fc8d9aebad1e42b5b658d74dd57e155b 复用首次结果续跑，仅补完同事件重复检查。

最终工作流 succeeded，阶段 notification_recorded，检查点归属正确。通知 preview、尝试次数为 0；重复请求返回原 run_id/event_id，duplicate=true、processed=false。duplicate_count=1、retry_count=0、跟进=1 条，CRM 完整内容不变。HTTP 与持久化验收完成，无需额外节点轨迹核对；本记录不声称读取过本轮节点轨迹。

<a id="day49-沿用的基线证据"></a>

### 沿用的基线证据

| 检查 | 已记录结果 | 来源与使用范围 |
| --- | --- | --- |
| AI 非法结构与服务异常 | 分别进入人工复核和 failed | Day 48 联调记录 |
| AI 分类最终修复 | 12 个离线分类回归通过 | Day 48 最终源码与导出记录 |
| CRM 事务失败与检查点恢复 | 回滚；复用检查点和 run_id 恢复成功 | Day 48 CRM 故障记录 |
| 全量 pytest | 415 passed | Day 48 基线，并非 Day 49 重跑结果 |
| Ruff 与节点回归 | 通过 | Day 48 最终代码检查 |
| Docker/Compose 与 OpenAPI | 健康检查、配置和新增接口验收通过 | Day 48 记录；Day 49 起始 API/n8n 也为 healthy |
| Day 49 清单及销售相关检查 | 21 passed，Ruff 通过 | Day 49 第二步局部检查，含 7 项新增清单测试 |

AI 两类故障联调早于 Day 48 分类代码最后修复；最后修复有 12 个离线回归且导出已同步，按既有证据沿用，不将其表述为 Day 49 新一轮 AI 故障联调。详情见 [Day 48 验收记录](week-7-notes.md#day48)。

<a id="day49-验收脚本修复"></a>

### 验收脚本修复

- 有序字典摘要先转成 PSCustomObject，避免 Select-Object 输出 null；保存的原 JSON 证据不受影响。
- JSON 对象按键规范化后比较，忽略字段顺序，保留类型、值和数组顺序差异。
- PowerShell 5.1 读取续跑证据显式使用 UTF-8，避免中文数据按本地编码读取。
- 失败报告保留输入和已知标识，续跑生成新报告并记录原批次，不重复首次成功处理。

这些修复均有隔离环境验证，真实 Production 的最后未完成步骤也已由用户续跑通过。脚本和参数见 [Day 49 可重复验收说明](../scripts/day49/README.md)。

<a id="day49-发布状态与剩余事项"></a>

### 发布状态与剩余事项

业务验收已完成，本轮文档同步直接使用以上结果。未受本次改动影响的检查不重复执行；只有相关代码改变、失败或新增风险时才安排对应重验。

清单 release_status=released、release_date=2026-09-14 表示本地组件版本定版。维护者负责 GitHub 推送及 Release 发布；线上状态以远端记录为准。业务验收结果沿用本记录，本地发布元数据调整不触发重新执行业务验收。

已知功能边界：销售通知为预览，通知恢复后的工作流收尾待实现，企业微信真实发送待外部条件满足。发布范围见 [v0.5.0 发布说明](workflow-center-v0.5.md)。
