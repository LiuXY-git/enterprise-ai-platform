# Day 72 第一个 MCP Server

本实验把 Day 65 的只读销售查询作为一个 MCP 工具提供。测试客户端通过真正的本地 stdio 子进程发现并调用工具，不使用模型，不读取 `.env`，不请求外部业务服务。

```text
测试客户端 → MCP tools/list / tools/call → MCP Server → Day 65 SQL Tool → 虚构 SQLite
```

## 准备环境

在仓库根目录执行。MCP 使用独立环境，不向平台 API 的 `.venv` 安装本实验依赖。

```powershell
Set-Location 'C:\Users\Administrator\Desktop\enterprise-ai-platform'
$env:PYTHONUTF8 = '1'
if (-not (Test-Path '.\experiments\day72\.venv\Scripts\python.exe')) {
    & .\.venv\Scripts\python.exe -m venv experiments/day72/.venv
    if ($LASTEXITCODE -ne 0) { throw '创建 MCP 环境失败' }
}
& .\experiments\day72\.venv\Scripts\python.exe -m pip install -r experiments/day72/requirements-lock.txt
if ($LASTEXITCODE -ne 0) { throw '安装 MCP 依赖失败' }
& .\experiments\day72\.venv\Scripts\python.exe -m pip check
if ($LASTEXITCODE -ne 0) { throw 'MCP 依赖不兼容' }
```

本轮固定官方 `mcp==2.2.0`、Python 3.14.2、Pydantic 2.13.4。完整 lock 是 Windows 环境，包含 pywin32，不宣称可以原样用于 Linux/macOS。`requirements.txt` 记录直接依赖，完整复刻优先使用 lock。安装依赖需要网络，运行实验不需要外部网络或 API Key。

## 第一次体验

```powershell
& .\experiments\day72\.venv\Scripts\python.exe -B experiments/day72/smoke_client.py
if ($LASTEXITCODE -ne 0) { throw 'MCP stdio 验收失败' }
```

这个命令创建临时虚构数据库，用官方 Client 启动并连接 MCP Server，执行工具发现和 10 个调用场景，再关闭子进程并清理它自己创建的临时数据库。无需另开窗口启动服务端。

检查这些结果：

- 顶层 `status=passed`，`transport=stdio`，`protocol_version=2026-07-28`。
- `tool.name=query_monthly_sales`；`inputSchema` 给出年份、月份、客户编号和条数约束。
- `monthly`：9 月已支付订单 4 条，`total_yuan=3000.00`，最多展示 2 条明细。
- `customer`：C001 已支付订单 2 条，共 1550.00 元。
- `no_sales`：7 月无订单，`data_status=no_data`，`is_error=false`。
- 非法参数为 `is_error=true`；未知工具是 JSON-RPC 错误 `-32602`；随后正常请求仍能成功。
- `database_unchanged=true`，模型与外部服务请求均为 0。

顶层通过表示所有预期结果符合验收条件，其中包含正确拒绝的错误请求，不能把它理解成每次工具调用都成功。

## 看清协议消息

第二个客户端不导入 MCP Client SDK，使用 Python 标准库按行发送 JSON-RPC。它是固定场景诊断程序，不是完整通用 MCP 客户端。

先显式创建一个新的演示库。重复执行同一路径会被拒绝，已有文件不会被覆盖：

```powershell
& .\experiments\day72\.venv\Scripts\python.exe -B experiments/day65/sales_sql.py init-demo --db data/day72/sales.sqlite
if ($LASTEXITCODE -ne 0) { throw '演示库未创建；如果已存在，请直接使用已有库或换一个新路径' }
```

再执行：

```powershell
& .\experiments\day72\.venv\Scripts\python.exe -B experiments/day72/wire_client.py --db data/day72/sales.sqlite
if ($LASTEXITCODE -ne 0) { throw '原始协议验证失败' }
```

输出 `exchanges` 保存完整请求和响应，共 6 次交换：`server/discover`、`tools/list`、正常销售查询、非法月份、未知工具，以及错误后的无数据查询。观察每条消息的 `id`、`method`、`params`，以及响应中的 `result` 或 `error`。数据库路径只作为操作者的服务启动参数，不属于 MCP 工具参数。

## 阅读服务端

[sales_mcp_server.py](sales_mcp_server.py) 的三个主要部分：

1. `list_tools`：返回工具名称、用途、输入 schema、输出 schema 和只读提示。
2. `call_tool`：核对名称，使用 Day 65 的严格参数契约，再调用已有 SQL Tool，将结果包装成 MCP 响应。
3. `serve`：用 SDK 读写 stdio 协议消息。stdout 专供协议，诊断日志写入 stderr。

采用 SDK 的低层 `Server` 是为了直接复用 Day 65 的平面 schema 与严格校验；它不会自动应用声明的 input schema，所以参数检查显式写在执行前。`readOnlyHint` 只是给客户端的提示，实际只读保护来自原 SQL 实现。

如果单独运行下面命令，终端等待 MCP 消息是正常现象，它没有网页地址，也不会主动输出简报：

```powershell
& .\experiments\day72\.venv\Scripts\python.exe -B experiments/day72/sales_mcp_server.py --db data/day72/sales.sqlite
```

可以用 Ctrl+C 结束手工启动的进程。日常验证优先运行 smoke_client，它会管理子进程生命周期。

## 自动测试

```powershell
$day72Temp = Join-Path $env:TEMP ('day72-pytest-' + [guid]::NewGuid().ToString())
& .\experiments\day72\.venv\Scripts\python.exe -B -m pytest experiments/day72 experiments/day65/test_sales_sql.py -q -p no:cacheprovider --basetemp $day72Temp
if ($LASTEXITCODE -ne 0) { throw 'Day 72 回归失败' }
```

预期 99 项通过：32 项 MCP 测试、67 项原 SQL 回归。完整证据与能力边界见 [Day 72 文档](../../docs/week-11-notes.md#day72)。本轮尚未接入 Qwen 或其他模型，Agent 自动选择工具留给 Day 73；HTTP、鉴权、多用户、桌面宿主接入和旧协议兼容性未验收。
