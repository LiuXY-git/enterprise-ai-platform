# Day 65：只读 SQL Tool

用 Python 和 SQLite 实现 `query_monthly_sales`：模型给出年月、可选客户和明细条数，程序执行固定的参数化查询，把结果回传模型。

数据库由 [7 条虚构订单](sales-data.json)创建。真实执行的是 SQLite 查询；这些记录不代表真实企业销售数据。

## 快速运行

在仓库根目录使用已有 API 虚拟环境，无需装依赖或更新容器：

```powershell
& .\.venv\Scripts\python.exe experiments/day65/sql_agent.py
& .\.venv\Scripts\python.exe experiments/day65/sql_agent.py --check-all
& .\.venv\Scripts\python.exe experiments/day65/sql_agent.py --show-tools
```

默认自动创建并清理一个临时教学库。离线模式中模型回复是 fixture，但 SQL 实际执行；不加载模型凭据，也不发送模型请求。

| 案例 | 参数范围 | 应有结果 |
| --- | --- | --- |
| `monthly` | 2026-09，所有客户，明细最多 2 条 | 4 笔已支付订单，共 3000.00 元；明细已截断 |
| `customer` | 2026-09，C001，明细最多 5 条 | 2 笔，共 1550.00 元 |
| `empty` | 2026-07，所有客户 | `no_data`，0 笔、0.00 元 |

## 保留教学数据库

初始化只做一次，已有文件会被拒绝覆盖：

```powershell
& .\.venv\Scripts\python.exe experiments/day65/sales_sql.py init-demo --db .\data\day65\sales-demo.sqlite
& .\.venv\Scripts\python.exe experiments/day65/sales_sql.py query --db .\data\day65\sales-demo.sqlite --year 2026 --month 9 --limit 2
& .\.venv\Scripts\python.exe experiments/day65/sql_agent.py --case customer --db .\data\day65\sales-demo.sqlite
```

`init-demo` 是独立的应用端准备步骤，会写入虚构数据；注册给模型的查询工具只能读取。数据库路径来自程序或 CLI，不是模型参数。

## 真实模型

```powershell
& .\.venv\Scripts\python.exe experiments/day65/sql_agent.py --live --case monthly
& .\.venv\Scripts\python.exe experiments/day65/sql_agent.py --live --case empty
```

仅 `--live` 请求已有模型配置；可加 `--env-file .env`。每个案例最多 2 次模型请求、1 次 SQL 工具调用。真实查询失败会直接停止，不让模型把错误解释成“销售额为零”。

本轮 Qwen qwen3.7-plus 的 `monthly` 和 `empty` 共 4 次模型请求均完成闭环；客户筛选的证据为离线 SQL 与 fixture，不宣称已做第三个 live 场景。详见 [验收记录](../../docs/evidence/day65/validation.json)。

## 验收和范围

新增 96 项测试，包含 Day 64 回归共 237 项通过；Ruff 通过。测试用新目录隔离 SQLite 文件：

```powershell
$day65TestDir = Join-Path $env:TEMP ('day65-tests-' + [guid]::NewGuid().ToString('N'))
& .\.venv\Scripts\python.exe -m pytest experiments/day65 experiments/day64 -q -p no:cacheprovider --basetemp $day65TestDir
```

SQL 模板固定，查询连接只读，参数严格校验，返回明细最多 20 条，执行受 SQLite 指令预算和时间检查约束。没有自由 SQL 生成、真实 CRM 接入、数据库写入工具、权限管理服务或新 Agent HTTP API。完整原理、失败行为与复刻步骤见 [Day 65 操作说明](../../docs/week-10-notes.md#day65)。
