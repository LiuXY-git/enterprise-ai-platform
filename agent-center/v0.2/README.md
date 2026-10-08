# Agent Center v0.2.0 发布候选

这是 Week 10（Day 64–70）的统一使用入口。当前可运行受约束的销售拜访简报实验：先查虚构销售数据，再按查询结果调用知识检索和天气工具，最后展示有来源的结果。无订单时跳过后续工具；某个独立工具失败时保留已取得的数据。

当前状态为发布候选，组件标签计划使用 `agent-center-v0.2.0`。代码提交、main 合并、远端推送、标签和 GitHub Release 是不同步骤，候选验收不代表已经上线。

- [版本说明与边界](../../docs/week-10.md#agent-center-v0.2)
- [Day 70 版本验收与发布流程](../../docs/week-10.md#day70)
- [Week 10 总结](../../docs/week-10.md#summary)
- [机器可读清单](../release-v0.2.0.json)
- [v0.1 历史入口](../README.md)

## 三分钟离线体验

从仓库根目录运行，使用项目已有 `.venv`，不需要 API Key：

```powershell
$env:PYTHONUTF8 = '1'
& .\.venv\Scripts\python.exe experiments/day69/acceptance.py --case full --markdown
if ($LASTEXITCODE -ne 0) { throw '完整场景验收失败' }
& .\.venv\Scripts\python.exe experiments/day69/acceptance.py --case weather_timeout --markdown
if ($LASTEXITCODE -ne 0) { throw '部分完成场景验收失败' }
& .\.venv\Scripts\python.exe experiments/day69/acceptance.py --case no_sales --markdown
if ($LASTEXITCODE -ne 0) { throw '无销售场景验收失败' }
```

完整场景应显示虚构销售额 3000.00 元、4 条已支付订单、制度片段和模拟天气；天气失败场景保留销售与制度，明确天气缺失；无销售场景明确跳过制度和天气。数据只用于教学。

这些 CLI 是验收入口：退出码 0 表示实际结果符合场景预期，`partial`、`no_sales` 等预期分支也能验收通过。实际任务状态以 `result.status` 和简报内容为准。

```powershell
& .\.venv\Scripts\python.exe experiments/day69/acceptance.py --check-all
if ($LASTEXITCODE -ne 0) { throw '18 个场景未全部符合预期' }
& .\.venv\Scripts\python.exe experiments/day69/acceptance.py --recovery-check
if ($LASTEXITCODE -ne 0) { throw '新会话重跑验证失败' }
& .\.venv\Scripts\python.exe scripts/day70/release_gate.py
if ($LASTEXITCODE -ne 0) { throw '版本完整性检查失败' }
& .\.venv\Scripts\python.exe scripts/day70/verify_v02.py
if ($LASTEXITCODE -ne 0) { throw '版本离线验收失败，请查看输出日志' }
```

新会话重跑会重新执行工具，没有继续旧检查点。完整离线验收要求 648 项既有测试和 40 项发布检查全部通过；不会自动安装依赖、启用 `--live` 或发布到 GitHub。

## 环境与可选真实调用

已配置的项目环境无需重装。新检出目录按 [Day 70 环境说明](../../docs/week-10.md#day70)准备，测试依赖见 [requirements-test.txt](requirements-test.txt)。离线测试使用模拟模型、HTTP Mock 和临时虚构 SQLite，不需要模型密钥或下载 ONNX；真实知识检索另外需要本地 ONNX 缓存。

真实模式是可选项，会产生外部请求。逐个工具与真实组合的参数见 [Day 65](../../docs/week-10.md#day65)、[Day 66](../../docs/week-10.md#day66)、[Day 67](../../docs/week-10.md#day67)、[Day 68](../../docs/week-10.md#day68)、[Day 69](../../docs/week-10.md#day69)。不要把任意企业数据库直接当作演示数据源。

历史天气简报可通过 `experiments/day69/acceptance.py --render-day68 --markdown` 查看；日期和查询时间保持历史值，不是当前天气。
