# Day 62：销售分析 Agent Prompt

版本化 Prompt + 一次模型请求 + JSON/Schema 校验 + Day 61 证据规则核对。输入是 Day 61 的虚构资料快照，尚未查询真实 CRM 或接入 Day 60 持久化。

在仓库根目录使用现有 API 环境，无需新依赖：

```powershell
& .\.venv\Scripts\python.exe .\experiments\day62\sales_prompt.py --case normal
& .\.venv\Scripts\python.exe .\experiments\day62\sales_prompt.py --check-all
& .\.venv\Scripts\python.exe .\experiments\day62\sales_prompt.py --show-prompt
& .\.venv\Scripts\python.exe -m pytest .\experiments\day62\test_sales_prompt.py .\experiments\day61\test_sales_scenario.py -q
```

以上全部离线。fixture 模式使用人工预期报告检查校验流程，不能据此判断模型是否遵守 Prompt。真实调用需显式指定一个样例：

```powershell
& .\.venv\Scripts\python.exe .\experiments\day62\sales_prompt.py --live --case normal
```

该命令读取现有模型配置并发出一次请求；不会自动重试。`--check-all` 只允许离线模式，不能与 `--live` 同用。Windows 中文输出和完整复刻流程见 [Day 62 说明](../../docs/week-9.md#day62)。

| 文件 | 作用 |
| --- | --- |
| [system-prompt.md](system-prompt.md) | 角色、资料边界、分类规则、来源、排序和停止条件 |
| `prompt_builder.py` | System 规则与 JSON Schema；User 消息仅包含输入资料 |
| [report-schema.json](report-schema.json) | 模型输出结构，不包含运行元数据 |
| `report_contract.py` | 严格 JSON 解析、Pydantic 与 Day 61 证据核对 |
| `chat_report.py` | 单次有界 HTTPX 请求与脱敏错误 |
| `sales_prompt.py` | 离线/真实模式入口、运行结果和请求次数 |
| `test_sales_prompt.py` | 校验、Prompt 分离、错误响应和请求限制测试 |

使用 `mode` 和 `model_requests` 区分固定样例与真实模型。`verification=accepted` 表示报告通过校验；`report.status` 表示资料覆盖情况。两者都不表示已执行客户跟进。
