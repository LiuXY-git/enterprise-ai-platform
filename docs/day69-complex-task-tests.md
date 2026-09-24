# Day 69：复杂任务、失败边界与简报验收

Day 68 已能在一项任务中组合 SQL、知识检索和天气工具。Day 69 将正常和异常路径整理成可重复的验收集，并增加一个从工具回执生成简报的程序，解决模型摘要漏写虚构背景和来源网址的问题。

本日新增独立实验，复用 Day 64–68 的代码；原实现、历史证据和已发布 v0.1 冻结文件保持不变。

## 新增内容

| 文件 | 作用 |
| --- | --- |
| [scenarios.json](../experiments/day69/scenarios.json) | 18 个场景的预期状态、停止原因与调用次数 |
| [acceptance.py](../experiments/day69/acceptance.py) | 场景注入、实际结果与预期比对、独立会话重跑、真实模型验证 CLI |
| [briefing.py](../experiments/day69/briefing.py) | 根据工具回执确定性地生成 Markdown 简报、来源目录与缺失项 |
| [test_acceptance.py](../experiments/day69/test_acceptance.py) | 新增 84 项集成、展示与失败边界测试 |

场景注入只发生在测试层，不能扩展原编排器的工具允许列表、任务范围或请求预算。底层仍最多 4 轮模型调用、3 次工具尝试，每个工具最多一次。

## 18 个复杂场景

| 分类 | 场景 | 预期 |
| --- | --- | --- |
| 完整流程 | `full`、`reverse` | SQL 先执行，制度和天气可交换顺序，completed |
| 前置条件 | `no_sales`、`sql_error` | 无订单或 SQL 失败，跳过两个后续工具；分别为 no_sales、failed |
| 部分结果 | `weather_timeout`、`weather_first_timeout`、`knowledge_empty`、`both_fail` | 保留独立成功结果，失败和无证据均不能伪装成完整任务，partial |
| 模型中断 | `model_after_sales`、`model_before_report` | 保留已取得回执，但报告未完成，rejected |
| 重复与越界 | `duplicate_id`、`repeat_sql`、`batch`、`wrong_scope`、`extra_call` | 拒绝重复 ID、重复工具、单轮多调用、偏离范围及超预算 |
| 报告和不可信内容 | `bad_citation`、`premature_report`、`injection` | 拒绝未知引用、提前完成，以及尝试执行检索片段中的非法工具命令 |

`injection` 是把恶意文字放入固定知识片段，再让模拟模型尝试调用未注册工具，验证程序拒绝执行。它不证明真实模型能抵抗所有 Prompt 注入。模型超时、天气超时、双工具失败等异常也由测试程序注入，不宣称真实线上服务发生了这些故障。

## 从回执生成交付简报

模型原始结果仍保留在 `result.report`，不进行重写。新入口的 `delivery.markdown` 不复制未经逐句验证的模型摘要，而是直接使用工具回执中的字段：

- 销售部分固定标注“虚构销售数据”，输出查询范围、已支付订单数、金额及明细截断说明。
- 制度部分展示来源与检索片段原文，标明是资料而非指令，并转义 Markdown/HTML 控制字符；空结果不推断报销限额。
- 天气部分输出回执中的日期、数值、时区和查询时间；真实预报固定附 Open-Meteo 来源链接及 CC BY 4.0 署名，Mock 数值明确标为虚构。
- 出错的工具仅展示失败与错误码；未尝试的工具和按前置条件跳过的工具分别记录。

每次会话生成独立 `run_id`。来源目录使用 `run_id/T1`、`run_id/T2:K1` 等完整标识，避免把不同会话的 T 编号混为同一份证据。

如果模型在所有工具都完成后超时，`missing` 中可以没有缺失工具，但 `final_report_missing=true`、任务状态仍为 rejected；简报明确说明只展示观察结果，不能视为完整报告。

确定性转写解决的是说明、来源和数值呈现问题，不验证原始业务数据真伪、天气预测准确率或片段相关性。制度片段按原检索结果展示，可能含不相关片段；仍需结合实际资料判断。`business_truth_verified=false`，没有把排版或来源关联当作业务事实证明。

## 复刻步骤

第一步，运行全部离线场景：

```powershell
Set-Location 'C:\Users\Administrator\Desktop\enterprise-ai-platform'
$env:PYTHONUTF8 = '1'
& .\.venv\Scripts\python.exe experiments/day69/acceptance.py --check-all
```

输出的顶层 `passed=true` 表示 18 个实际结果均符合场景预期。每个场景包含 `verdict`、原 `result` 和新 `delivery`。预期失败也算验收通过，所以退出码 0 不代表所有任务状态都是 completed。默认无任何外部请求，临时 SQL 库由 Day 65 的 7 条虚构订单创建，执行前后核对数据库文件哈希。

第二步，查看部分结果和中断后的交付：

```powershell
& .\.venv\Scripts\python.exe experiments/day69/acceptance.py --case weather_timeout --markdown
& .\.venv\Scripts\python.exe experiments/day69/acceptance.py --case model_before_report --markdown
```

天气超时的简报应保留销售与制度资料，明确天气未取得，不包含编造的天气数值。模型最终回复失败时，即使三个工具都返回了结果，也会显示“会话未通过验收”。

第三步，验证恢复边界：

```powershell
& .\.venv\Scripts\python.exe experiments/day69/acceptance.py --recovery-check
```

同一只读虚构数据库上先运行天气失败场景，再创建一个全新会话运行完整成功场景。两个 run_id 不同，各自重新执行三个工具；第一次的 partial 记录保持原样，不能被后一次成功覆盖。

这验证的是**检查后新建会话重跑**，不是继续原进度。没有自动重试、失败工具单独重试、持久化检查点或跨进程恢复；原成功查询也会再次执行。Day 60 的模拟检查点实验尚未接到这套真实工具链上。

第四步，重放历史数据的展示，不重做工具调用：

```powershell
& .\.venv\Scripts\python.exe experiments/day69/acceptance.py --render-day68 --markdown
```

该命令先核对 Day 68 `live-full.json` 在原验收清单中的哈希，再生成新简报。0 次模型请求、0 次天气请求，原文件未修改。天气日期与查询时间保持历史值。可直接阅读 [本轮保存的历史简报](evidence/day69/historical-briefing.md)。

第五步，可选真实 Qwen 验证：

```powershell
& .\.venv\Scripts\python.exe experiments/day69/acceptance.py --live --case no_sales
& .\.venv\Scripts\python.exe experiments/day69/acceptance.py --live --case weather_timeout
```

使用已有 `.env` 配置，可加 `--env-file .env`。无销售场景最多 2 次模型请求；天气失败场景最多 4 次，Qwen 和隔离知识库检索真实执行，但天气客户端由本地 Mock 注入超时，实际天气网络请求为 0。知识库仍需要已有本地 ONNX 缓存。真实模式不接受其它场景，避免无意触发额外服务调用。

本轮无销售场景只执行 SQL，然后以 no_sales 结束；天气失败场景取得销售与制度资料，以 partial 结束。没有访问真实企业数据，也没有发送通知或预订。

## 验收与限制

验证日期：2026-09-24。

- **648 项测试通过**：Day 69 新增 84 项，已有回归 564 项；无失败、错误或跳过，Ruff 和格式检查通过。保留一条既有 Chroma 弃用提示。
- [18 个离线场景记录](evidence/day69/scenarios.json) 与 [新会话重跑记录](evidence/day69/recovery.json)：均不联网。
- [历史渲染记录](evidence/day69/historical-render.json) 与 [简报文件](evidence/day69/historical-briefing.md)：补齐 Day 68 原摘要遗漏的背景与来源，不增加真实请求。
- [真实 Qwen 无销售场景](evidence/day69/live-no_sales.json)、[真实 Qwen 加模拟天气失败](evidence/day69/live-weather_timeout.json)：共 6 次模型请求、0 次天气网络请求。
- [验收清单与代码/证据哈希](evidence/day69/validation.json)：记录环境、来源、请求数与历史完整性检查。

本日是单一教学任务的复杂路径测试，不是通用任意目标 Agent 验收；未覆盖真实企业权限、线上故障恢复、高并发或长期稳定性。未更新容器、未重跑全平台 API 测试，也不将原始模型摘要宣称为已完成语义验证。Week 10 的版本清单、发布范围和发行验收留给 Day 70。
