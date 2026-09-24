# Day 73：Agent 接入 MCP

把 Day 72 已运行的 MCP Server 接到模型工具调用循环：自然语言目标 → 模型提出 Function Calling → 应用校验 → MCP stdio → 只读 SQL → 回执回填 → 模型结构化报告 → 应用核对并展示。

本实验是独立 CLI。四个目标及允许的查询范围由程序预先定义，没有接入平台 API、Docker、网页或任意自然语言任务入口。默认使用模拟模型，MCP 通信和数据库查询均真实执行。

## 1. 安装独立环境

在 Windows PowerShell 中执行，项目根目录需有 Python 环境 `.venv`（本次验收为 Python 3.14.2）：

```powershell
Set-Location 'C:\Users\Administrator\Desktop\enterprise-ai-platform'
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
& .\.venv\Scripts\python.exe -m venv .\experiments\day73\.venv
& .\experiments\day73\.venv\Scripts\python.exe -m pip install -r .\experiments\day73\requirements-lock.txt
& .\experiments\day73\.venv\Scripts\python.exe -m pip check
```

`requirements.txt` 声明直接依赖；`requirements-lock.txt` 保存本次 Windows 验收环境的完整版本，其中 `pywin32` 只在 Windows 安装。MCP SDK 为 2.2.0，协商协议版本为 `2026-07-28`；本实验按此组合验收，不保证旧版协议兼容。Day 72 环境和 API 环境不需要升级。

## 2. 先运行不消耗模型额度的演示

```powershell
& .\experiments\day73\.venv\Scripts\python.exe -B .\experiments\day73\mcp_agent.py --check-all --markdown
```

每次运行在临时目录创建 7 条虚构订单，子进程只读查询，退出后清理临时数据库。没有业务库路径参数。

| 场景 | 预期结果 | MCP 调用 |
| --- | --- | --- |
| `monthly` | 2026 年 9 月全客户已支付 4 单，3000.00 元；只展示 2 条明细，合计不截断 | 1 |
| `customer` | C001 在 2026 年 9 月已支付 2 单，1550.00 元 | 1 |
| `empty` | 2026 年 7 月无已支付订单，明确返回 `no_data` | 1 |
| `clarification` | 缺少年月，提示补全范围 | 0 |

`clarification` 仍会建立 MCP 连接和发现工具，但不会执行销售工具。可单独选择场景：

```powershell
& .\experiments\day73\.venv\Scripts\python.exe -B .\experiments\day73\mcp_agent.py --case monthly
```

不加 `--markdown` 会输出完整 JSON：`discovery` 是工具发现结果，`messages` 是模型对话与工具回填，`receipt` 是查询回执，`raw_model_answer` 是模型最终原文，`report` 是验收后的报告。默认 `model_requests=0` 表示没有请求模型服务；不代表 MCP 被模拟。

## 3. 观察真正的模型调用

项目 `.env` 中已有有效 Qwen 配置时，可显式选择一个场景并开启 `--live`。这会产生模型请求：

```powershell
& .\experiments\day73\.venv\Scripts\python.exe -B .\experiments\day73\mcp_agent.py --case monthly --live --env-file .\.env --markdown
```

工具正常返回时最多 2 次模型请求：第一次提出调用，第二次根据回执输出报告。最多 1 次 MCP 工具调用；不自动重试。`--live` 必须指定 `--case`，不能与 `--check-all` 一起运行。

本次真实验收使用 `qwen3.7-plus`，`monthly` 和 `empty` 各完成 2 次模型请求、1 次 MCP 查询，共 4 次模型请求。证据保存于 [Day 73 证据目录](../../docs/evidence/day73/validation.json)，两次数据库文件哈希均保持不变。`customer` 和 `clarification` 仅作模拟模型验证。

## 4. 对照代码学习

1. [mcp_agent.py](mcp_agent.py) 的 `CASES`：自然语言目标及程序允许的范围。修改练习时需同步二者，不能只改目标文字。
2. [mcp_sales.py](mcp_sales.py) 的 `discover()`：调用 `tools/list`，检查服务名、协议、工具名及输入输出 schema，然后把发现的输入 schema 转为模型工具定义。工具描述由本地提供，服务描述不能修改应用规则。
3. `run_session()`：调用模型；复用 Day 65 严格参数契约，并核对范围；模型提出请求，程序决定能否执行。
4. `McpSales.query()`：通过官方客户端调用 `tools/call`。真正执行查询的是 Day 72 Server 子进程，Agent 主进程没有直接 SQL 回退路径。
5. `validate_receipt()`：检查 text/structured 两种结果一致、虚构标识、时间与客户范围、金额格式、明细与汇总一致性、截断标记。
6. `expected_report()`：将模型输出逐项与回执比较，包括 `<run_id>/T1` 来源引用。核对成功后 `render()` 才生成中文回答。

例如限制明细为 2 条时，不能把这 2 条的小计当成全月销售额。发生工具超时、返回错误或模型金额不匹配时，`answer` 为空并记录原因；最终模型失败时仍保留已收到的回执，便于判断失败发生在哪一步。

## 5. 复跑测试

```powershell
& .\experiments\day73\.venv\Scripts\python.exe -B -m pytest .\experiments\day64 .\experiments\day65\test_sales_sql.py .\experiments\day72\test_sales_mcp.py .\experiments\day73 -q
& .\experiments\day73\.venv\Scripts\python.exe -m ruff check .\experiments\day73
& .\experiments\day73\.venv\Scripts\python.exe -m ruff format .\experiments\day73 --check
& .\experiments\day73\.venv\Scripts\python.exe -B .\scripts\day70\release_gate.py
```

本次 319 项离线测试全部通过：Day 64 既有模型协议与传输 141 项、Day 65 SQL 67 项、Day 72 MCP 32 项、Day 73 新增 79 项。发布完整性检查核验 v0.1/v0.2 冻结文件和历史证据，不重新执行旧版全量发布测试。

## 能力边界

- 仅本地已知 MCP Server、固定只读工具、四个预设教学场景。不是任意 Server 插件加载器，也不是自由 SQL Agent。
- Function Calling 表达模型的调用请求；MCP 传送工具发现、调用和结果；应用承担参数校验、次数限制和结果核对。
- MCP 发现/调用设 5 秒等待限制；模型传输复用 Day 64 的连接 10 秒、网络操作 30 秒超时与响应大小限制。这不是整个任务的硬性总时限。回执字符限制在 SDK 解码之后检查。
- 超时后的执行结果记为未知，不据此认定工具完全没执行，也不自动重试。示例工具本身只有读取操作。
- 核对结果代表与工具回执一致，不代表现实销售数据真实可靠。最终中文措辞由程序模板生成，不声称验证了自由文本语义。
- 无长期 Memory、多轮续聊、检查点恢复、LangGraph 编排、远程 MCP 认证、多用户权限或生产负载验收。Day 74–76 另行学习实施。

官方参考：[MCP Python SDK 客户端](https://py.sdk.modelcontextprotocol.io/client/)、[传输方式](https://py.sdk.modelcontextprotocol.io/client/transports/)。
