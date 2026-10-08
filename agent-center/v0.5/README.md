# Agent Center v0.5.0 发布候选

Week 11（Day 71–77）学习成果的统一入口：本地 MCP 销售服务、模型通过 MCP 查询、可恢复的会话记忆、Memory 与 Planning 学习材料。

当前为 **candidate**。版本号对应学习路线的阶段命名，不代表任意 Agent 功能完备或已上线。组件标签拟为 `agent-center-v0.5.0`，平台 API 仍为 `1.0.0`。正式状态以 [版本清单](../release-v0.5.0.json) 为准；正式标签和 GitHub Release 尚未创建。

这些能力分布在独立实验中，Memory、Planning 和 MCP 尚未自动串成一个季度分析 Agent。

- [版本范围与边界](../../docs/week-11.md#agent-center-v0.5)
- [Week 11 总结](../../docs/week-11.md#summary)
- [Day 77 验收与后续发布步骤](../../docs/week-11.md#day77)
- [Release 说明草稿](release-notes.md)

## 三个学习入口

在项目根目录执行，已有各日独立环境时无需重新安装。

```powershell
Set-Location 'C:\Users\Administrator\Desktop\enterprise-ai-platform'
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'

# 模拟模型，真实 MCP stdio 查询虚构销售数据
& .\experiments\day73\.venv\Scripts\python.exe -B .\experiments\day73\mcp_agent.py --check-all --markdown

# 模拟模型，14 个独立进程演示真实 SQLite 会话保存、恢复、更新和清除
& .\experiments\day75\.venv\Scripts\python.exe -B .\experiments\day75\demo.py

# 人工 Mock 计划，由原有 LangGraph 规划流程校验；不执行任务
& .\experiments\day59\.venv\Scripts\python.exe -B .\experiments\day59\task_planner.py --mock-case normal
```

依次应看到：销售额 3000.00 元等四场景结果；记忆演示 `passed=true`；规划结果 `planned` 且 `task_executed=false`。均不会请求模型服务。

详细复刻：[Day 72](../../experiments/day72/README.md)、[Day 73](../../experiments/day73/README.md)、[Day 75](../../experiments/day75/README.md)、[Day 76](../../experiments/day76/README.md)。

## 离线发布验收

```powershell
& .\experiments\day73\.venv\Scripts\python.exe -B .\scripts\day77\release_gate.py
if ($LASTEXITCODE -ne 0) { throw '版本完整性检查失败' }
& .\experiments\day73\.venv\Scripts\python.exe -B .\scripts\day77\verify_v05.py
if ($LASTEXITCODE -ne 0) { throw '离线发布验收失败' }
```

要求 456 项全部通过：去重后的既有回归 418 项，发布检查 38 项，无失败、错误或跳过。规划器测试在 Day 59 环境运行，其余在 Day 73 环境运行。脚本输出新的临时证据目录，保留日志与 JUnit；拒绝覆盖既有输出目录。不会自动安装依赖、启用 live、提交代码或发布。

新检出仓库按 [环境准备](../../docs/week-11.md#day77)安装。真实模型历史验证来自 Day 73 的 4 次请求和 Day 75 的 2 次请求；本日不再产生真实请求，也不把旧证据当作当前凭据连通性检查。
