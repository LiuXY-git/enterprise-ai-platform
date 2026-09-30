# Day 59：任务规划 Agent

模型生成结构化计划，LangGraph 编排输入检查、模型请求、计划校验和结果返回。计划中的步骤不会执行。完整操作说明见 [Day 59 文档](../../docs/week-9-notes.md#day59)。

| 文件 | 用途 |
| --- | --- |
| [task_planner.py](task_planner.py) | 图、运行状态、默认 Mock 与显式 Live CLI |
| [chat_planner.py](chat_planner.py) | 单次 JSON Mode HTTP 请求、边界与错误分类 |
| [plan_schema.py](plan_schema.py) | Pydantic 字段、步骤依赖和计划/澄清约束 |
| [plan-schema.json](plan-schema.json) | 从模型导出的字段 Schema；跨字段约束以 Python 校验器为准 |
| [mock-responses.json](mock-responses.json) | 人工编写的正常、澄清、非法输出、错误样例 |
| [test_task_planner.py](test_task_planner.py) | 离线图执行、Schema、HTTP MockTransport 和 CLI 测试 |
| [requirements.txt](requirements.txt)、[requirements-lock.txt](requirements-lock.txt) | 直接依赖与完整环境快照 |
| [graph.mmd](graph.mmd) | 由实际编译图导出的结构 |

默认模式不读取 `.env`、不请求模型；只有 `--live --goal ...` 才会使用现有配置。每次任务最多一个 HTTP 请求，不自动重试或修复输出。远程追踪在图入口关闭。

状态含义：`planned` 表示计划通过结构检查；`waiting_for_input` 表示需要补充；`failed` 表示输入、模型调用或输出校验失败。`planned` 不表示资料已查到、问题已回答或计划已经执行。

使用独立 `.venv` 安装锁定依赖；不要安装进 API 或 Day 58 环境。没有 LangGraph 时实验测试会跳过，验收需要在独立环境确认全部通过且无 skipped。真实 Qwen 样例见 [live-plans.json](../../docs/evidence/day59/live-plans.json)，完整验证范围见 [validation.json](../../docs/evidence/day59/validation.json)。
