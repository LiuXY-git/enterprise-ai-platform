# Day 58：LangGraph 最小状态图

真实运行 LangGraph，节点使用固定计划和模拟知识结果。完整说明与运行命令见 [Day 58 文档](../../docs/week-9-notes.md#day58)。

| 文件 | 用途 |
| --- | --- |
| [langgraph_basics.py](langgraph_basics.py) | State、四个节点、固定边与条件边、CLI |
| [test_langgraph_basics.py](test_langgraph_basics.py) | 五类结束分支、进度隔离、额度限制、断网和递归保护测试 |
| [requirements.txt](requirements.txt) | 三项直接依赖 |
| [requirements-lock.txt](requirements-lock.txt) | Windows / Python 3.14.2 实测环境的完整版本快照 |
| [graph.mmd](graph.mmd) | 从实际编译图导出的 Mermaid 源码 |

实验只接受预设 `--case`，不支持任意自然语言任务。`success`、`missing-input`、`empty-result`、`tool-error`、`budget-limit` 用于改变固定输入或模拟返回值。

依赖安装需要联网；运行示例不需要 API Key，不读取项目 `.env`，不访问知识库或模型，不启用远程追踪。使用单独的 `.venv`，不要把本目录依赖安装进 API 环境。当前锁定的 LangGraph SDK 要求 `websockets < 17`，API 环境固定为 `17.0.1`。

状态保存在一次图调用的内存中；没有检查点和重启恢复。`waiting_for_input` 在本实验中结束本次调用，不是可以恢复的 LangGraph interrupt。

项目默认测试环境没有 LangGraph 时，本目录测试会跳过；这不代表通过。有效验收必须在独立环境中运行，并确认 **14 passed、没有 skipped**。运行证据见 [graph-validation.json](../../docs/evidence/day58/graph-validation.json)。
