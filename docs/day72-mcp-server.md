# Day 72 第一个 MCP Server

本日对应原路线“搭建第一个 MCP Server，实现一个简单工具，例如查询数据库”。交付一个真实的本地 stdio MCP Server，将 Day 65 的虚构销售只读查询暴露为 `query_monthly_sales`，并通过两个独立客户端验证协议调用。

## 实现与复刻入口

- [实验 README](../experiments/day72/README.md)：环境准备、一键体验、原始消息观察和测试命令。
- [sales_mcp_server.py](../experiments/day72/sales_mcp_server.py)：服务端，复用原参数契约和查询实现。
- [smoke_client.py](../experiments/day72/smoke_client.py)：官方 SDK Client，10 个固定调用场景。
- [wire_client.py](../experiments/day72/wire_client.py)：不依赖 MCP Client SDK 的标准库 JSON-RPC 探针，6 次真实 stdio 交换。
- [test_sales_mcp.py](../experiments/day72/test_sales_mcp.py)：32 项契约、错误及子进程测试。
- [依赖 lock](../experiments/day72/requirements-lock.txt)：Windows/Python 3.14.2 独立环境。

SDK 固定为官方 `mcp==2.2.0`，实际通信协议版本为 `2026-07-28`。SDK 使用低层 `Server` 的 `on_list_tools` 与 `on_call_tool`，以保持 Day 65 已验证的工具参数形状。原 `sales_sql.py` 和已发布 v0.1/v0.2 冻结资产均未修改。

## 一次请求发生什么

1. 测试客户端启动本地服务子进程，通过 stdio 获取服务信息和工具清单。
2. `tools/list` 返回工具名称、描述、输入 schema、输出 schema 和只读提示。
3. `tools/call` 传入工具名称与年份、月份等参数；数据库路径和 SQL 文本不在工具参数中。
4. 服务端先检查名称，再按原 `SalesQuery` 严格校验类型、范围和额外字段，才进入数据库查询。
5. 原 `SalesTool` 执行固定参数化 SELECT，保留只读连接、查询授权与 SQL 预算。每个服务实例最多一个查询工作线程同时执行。
6. 结果通过 MCP 文本和结构化内容返回；两种表示一致，明确标注 `fictional=true`。

创建演示库是操作者的单独初始化操作；服务端启动与查询均不创建数据库。服务启动参数 `--db` 由本地操作者指定，它不是远程工具调用权限。此实现适用于可信本机教学，不是任意数据库开放服务。

## 成功、空数据与失败

| 情况 | MCP 表现 | 业务含义 |
| --- | --- | --- |
| 2026 年 9 月 | `isError=false`，4 条订单，3000.00 元 | 固定虚构样例查询成功 |
| 客户 C001 | `isError=false`，2 条订单，1550.00 元 | 客户筛选生效 |
| 2026 年 7 月 | `isError=false`，`data_status=no_data` | 查询成功但没有订单 |
| 月份 13、字符串年份、布尔月份、额外 SQL/路径字段 | `isError=true`，`invalid_query_parameters` | 在访问数据库前拒绝 |
| 不存在的工具名 | JSON-RPC `error.code=-32602` | 协议调用目标无效 |
| 缺失、损坏或结构不符的数据库 | `isError=true`，相应固定错误码 | 不冒充无销售结果 |
| 查询预算耗尽 | `isError=true`，`query_budget_exceeded` | 单次查询受控终止 |

工具错误返回固定信息，不将 SQL、文件路径、原始异常或传入攻击字符串回显。未知执行错误统一为 `tool_execution_failed`。参数错误后再发出有效请求可以成功，不需要重启服务。这是同一连接继续处理新请求，不是自动重试或检查点恢复。

只读提示本身不提供权限保护。单查询预算沿用 Day 65（最多 100000 SQLite 虚拟机步、0.5 秒检查预算），不是整个服务端的请求总期限。SDK smoke 客户端设有 5 秒响应超时、30 秒整体检查范围；原始探针逐条响应 5 秒，并在退出时回收自己启动的进程。没有宣称全服务限流、队列上限或生产级资源隔离。

## 本轮验收

- **99 项测试通过**：32 项新增 MCP 测试，67 项 Day 65 SQL 回归；无失败、错误或跳过。
- 真正的官方 SDK stdio 客户端通过 10 个场景；标准库探针通过 6 次交换并确认 stdin 关闭后服务端正常退出。
- 数据库二进制 SHA-256 在查询前后相同；测试使用临时虚构数据库。
- Ruff 与格式检查通过，独立环境 `pip check` 通过。
- v0.1 与 v0.2 完整性检查通过；未重跑旧版全部测试或全平台 API 测试。
- 0 次模型调用、0 次外部业务服务请求；只有安装依赖使用网络。没有更改平台 API 环境或容器。

证据：[validation.json](evidence/day72/validation.json)、[SDK 客户端结果](evidence/day72/sdk-client.json)、[原始协议交换](evidence/day72/wire-client.json)、[JUnit](evidence/day72/pytest.xml)。

“跨客户端”在本轮具体指官方 Python SDK Client 与独立标准库探针，不表示已接入桌面 AI 宿主或其他语言 SDK。多数测试使用进程内 SDK 连接做快速契约检查，另有真实 stdio 子进程测试，二者不会混称为全部跨进程。

## 下一步与边界

今天的调用参数由测试程序固定给出，尚未接入模型选择工具、对话、Agent 规划或 LangGraph。Day 73 再实现用户请求 → Agent → MCP 工具 → 回答。

没有启动 HTTP 监听或配置浏览器入口；没有远程鉴权、多用户授权、MCP Resources/Prompts、旧协议兼容性或大规模恶意输入验收。标准库探针只实现固定协议版本的必要请求，不能作为通用客户端产品。已发布 v0.2 的 tag/manifest 保留原样，后续 MCP 功能以独立实验演进。

## 官方参考

查阅日期：2026-09-24。代码按实际安装的 SDK 2.2.0 验证，不能直接混用旧版 FastMCP 教程。

- [Python SDK](https://py.sdk.modelcontextprotocol.io/)
- [低层 Server 与显式参数校验](https://py.sdk.modelcontextprotocol.io/advanced/low-level-server/)
- [Client](https://py.sdk.modelcontextprotocol.io/client/)
- [错误处理](https://py.sdk.modelcontextprotocol.io/servers/handling-errors/)
- [协议架构](https://modelcontextprotocol.io/docs/learn/architecture)
