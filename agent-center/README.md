# Agent Center v0.1.0

Week 9 学习实验的版本入口，包含规划、状态恢复、销售场景契约与模型报告校验。2026-09-21 完成 v0.1.0 内容定版，清单状态为 released。远端发布状态以 [GitHub Release](https://github.com/LiuXY-git/enterprise-ai-platform/releases/tag/agent-center-v0.1.0) 为准；清单定版不代表远端发布已完成。

- [版本说明与能力边界](../docs/agent-center-v0.1.md)
- [Day 63 验收与运行说明](../docs/week-9-notes.md#day63)
- [Week 9 总结](../docs/week-9-summary.md)
- [机器可读版本清单](release-v0.1.0.json)

## 选择入口

以下命令从仓库根目录运行；LangGraph 使用 Day 60 独立环境，销售契约与 Prompt 使用原有 API 环境。

| 目的 | 命令 |
| --- | --- |
| 检查版本文件与证据一致性 | `& .\.venv\Scripts\python.exe .\scripts\day63\check_release.py` |
| 执行完整离线版本验收 | `& .\.venv\Scripts\python.exe .\scripts\day63\verify_release.py` |
| 看状态图的模拟分支 | `& .\experiments\day60\.venv\Scripts\python.exe .\experiments\day58\langgraph_basics.py --case all` |
| 看任务规划的离线输出 | `& .\experiments\day60\.venv\Scripts\python.exe .\experiments\day59\task_planner.py` |
| 创建可恢复的模拟任务 | `& .\experiments\day60\.venv\Scripts\python.exe .\experiments\day60\task_progress.py start` |
| 检查销售场景规则 | `& .\.venv\Scripts\python.exe .\experiments\day61\check_scenario.py --check-all` |
| 检查 Prompt 输出验收流程 | `& .\.venv\Scripts\python.exe .\experiments\day62\sales_prompt.py --check-all` |

这些命令默认不请求模型。真实模型调用需要显式 --live，具体参数见 [Day 59](../docs/week-9-notes.md#day59) 和 [Day 62](../docs/week-9-notes.md#day62)。本组件没有统一 Agent HTTP API，Day 62 报告也尚未写入 Day 60 检查点。
