# Day 60：持久化任务进度

接收 Day 59 的有效计划，用 LangGraph 原生 SQLite 检查点保存模拟进度。每次恢复只推进一个模拟步骤；所有命令均为本地操作，模型请求数为 0。

完整安装、关闭窗口后恢复、故障处理与验收步骤见 [Day 60 操作说明](../../docs/week-9.md#day60)。

| 文件 | 用途 |
| --- | --- |
| `progress_graph.py` | 暂停 → 模拟步骤 → 暂停或结束 |
| `task_store.py` | UUID、原生 SqliteSaver、进程锁、检查点校验 |
| `task_progress.py` | start / status / resume / recover 命令 |
| `test_task_progress.py` | 独立进程、异常退出和状态保护测试 |
| [graph.mmd](graph.mmd) | 从实际图导出的 Mermaid |
| [requirements-lock.txt](requirements-lock.txt) | Windows / Python 3.14.2 环境快照 |

默认数据位于仓库 `data/day60/`，已被 Git 忽略。`--store-dir` 必须放在子命令之前。此实验没有接入 FastAPI、Docker 或真实业务工具。
