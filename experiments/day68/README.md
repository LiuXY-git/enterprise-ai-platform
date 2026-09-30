# Day 68：组合 SQL、知识库和天气工具

一个“销售与拜访准备简报”同时使用前三天的工具：先查虚构月销售额，有已支付订单时再查酒店报销制度和上海天气。模型可以选择后两项的顺序，程序负责限制权限、次数和完成状态。

在仓库根目录使用已有 API 虚拟环境，无需安装新依赖或更新容器：

```powershell
& .\.venv\Scripts\python.exe experiments/day68/multi_tool_agent.py --show-tools
& .\.venv\Scripts\python.exe experiments/day68/multi_tool_agent.py --check-all
```

默认不联网：SQLite 查询真实执行，销售记录虚构；知识片段、天气响应和模型回复使用固定样例。每次 CLI 运行创建并清理独立临时教学数据库，不接受真实数据库或知识库路径参数。

| 场景 | 应有状态 | 工具尝试次数 |
| --- | --- | --- |
| `full` | `completed` | 3 |
| `no_sales` | `no_sales` | 1，跳过制度与天气 |
| `weather_timeout` | `partial` | 3，保留销售和制度信息 |
| `knowledge_empty` | `partial` | 3，不编造报销限额 |
| `sql_error` | `failed` | 1，不能当作零销售额 |

可用 `--case weather_timeout` 单独查看失败路径。单例的 `partial`、`failed`、`rejected` 退出码为 1；`--check-all` 中全部符合预期状态时退出码为 0，表示测试通过。

真实三工具联调：

```powershell
& .\.venv\Scripts\python.exe experiments/day68/multi_tool_agent.py --live --case full
```

仅该显式命令联网，最多 4 次模型请求、1 次公开上海天气请求。使用已有 `.env` 模型配置，可加 `--env-file .env`。SQL 仍为虚构教学库；知识检索使用 Day 66 的真实 Knowledge Hub 检索函数、本地 ONNX 缓存和隔离虚构集合。天气使用 Day 67 的 Open-Meteo 接口。模型与 API 均不自动重试。

本轮 83 项新增测试通过，加上此前回归共 564 项；1 个真实完整场景使用 Qwen qwen3.7-plus，依次完成 SQL、知识检索、天气三个工具并输出带来源简报。失败分支和反向调用顺序的证据是离线测试，不宣称已做相应真实模型验证。

```powershell
$day68TestDir = Join-Path $env:TEMP ('day68-tests-' + [guid]::NewGuid().ToString('N'))
& .\.venv\Scripts\python.exe -m pytest experiments/day64 experiments/day65 experiments/day66 experiments/day67 experiments/day68 tests/test_retrieval_service.py -q -p no:cacheprovider --basetemp $day68TestDir
```

详见 [完整复刻流程](../../docs/week-10-notes.md#day68) 和 [验收证据](../../docs/evidence/day68/validation.json)。`completed` 表示所需工具结果齐全且报告状态/引用格式通过，不能代替业务事实或预测质量验证。销售、制度数据始终虚构，不能直接作为真实拜访计划。
