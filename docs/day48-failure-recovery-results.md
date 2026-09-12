# Day 48 故障恢复验收记录

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

## 可重复验证

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

## 收尾状态

已同步最新 n8n 编辑版本到可移植工作流文件，并移除实例元数据和凭据引用。
新增回放入口保护：CRM 保存后禁止整条回放；回归测试同时验证拒绝时原状态完全不变。
API 已重建并达到 healthy；部署后的回放保护测试通过。
n8n 当前工作流已发布；Git 合并与推送由用户执行收尾脚本。
Day 48 Production URL 正常与重复事件测试通过；真实消息发送链路未验收。

## 本轮质量检查结果

2026-09-12 在最终源码上完成：

- 全量 pytest：415 passed，1 个 ChromaDB 弃用警告。
- Ruff：All checks passed。
- JavaScript：12 个分类回归用例通过；CRM 普通/恢复请求体及检查点归属测试通过。
- Git diff --check：通过。
- Docker Compose config --quiet：通过；现有 API 和 n8n 容器均 healthy。
- 本机 OpenAPI：检查点、失败、恢复查询、通知尝试、通知结果、人工核对共 6 条接口均存在。

重建后使用两条通知异常记录请求回放，均返回预期 409；workflow、followup 和 retry_count 均保持不变。
## 发布后最终验收

根据用户提供的实际执行输出：

- 回放保护：`1cd2de32-4afd-4b85-b140-2990da9db654`（failed）和 `4e82b6bd-076d-4081-b887-b5ff513bd273`（delivery_unknown）均返回 HTTP 409，重试次数仍为 0，运行和跟进记录未改变。
- Production event_id：`day48-production-3a8ef52373904928b308016861c3fb9c`。
- Production run_id：`0a6f8b52-e24e-46dc-8c32-27f1f1b0541e`。
- Production followup_id：`22e4566b-3559-4427-baf8-d1941a99ffad`。
- 最终状态 succeeded，阶段 notification_recorded，检查点已保存，通知状态 preview。
- 相同事件重复提交被识别；duplicate_count 为 1，followup_count 为 1，CRM 内容不变。

复现脚本：`scripts/day48/day48-test-production.ps1`；回放保护脚本为 `scripts/day48/day48-test-replay-guard.ps1`，后者依赖上述保留的测试记录。