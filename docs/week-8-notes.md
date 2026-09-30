# Week 8：工作流整理、配置与部署

路线范围：Day 50–56。本文件包含 6 个每日章节，保留完整步骤、命令、验收记录与能力边界。

本周内容按日期排列，各节保留对应日期的实施状态，当前进度以[项目首页](../README.md)为准。

本文件收录 Day 50–55；Day 56 的发布准备见[Week 8 总结](week-8-summary.md)。

[返回周目录](README.md#按周阅读) · [本周总结](week-8-summary.md)

## 本周目录

- [Day 50：整理可复用工作流模板](#day50)
- [Day 51：工作流结构化事件日志](#day51)
- [Day 52 配置中心与离线自检](#day52)
- [Day 53 一键启动与持久化验收](#day53)
- [Day 54 使用与架构文档](#day54)
- [Day 55：Workflow Center 业务 Demo](#day55)

---

<a id="day50"></a>

## Day 50：整理可复用工作流模板


路线依据为 16 周学习路线 Week 8 / Day 50：整理客服、销售、邮件工作流模板。基线是已发布的 Workflow Center v0.5.0，提交 fe3c00e；平台 API 保持 1.0.0。

<a id="day50-当日安排"></a>

### 当日安排

| 步骤 | 内容 | 交付 |
| --- | --- | --- |
| 1 | 梳理场景、依赖和已有能力 | 三类模板选型表 |
| 2 | 整理输入输出与复用步骤 | 三份说明与机器目录 |
| 3 | 准备可复用请求样例 | 六份虚构样例、离线请求生成器 |
| 4 | 验证新增模板与现有导出的对应关系 | 目录引用、样例映射和生成器离线检查 |

模板入口：[n8n/templates](../n8n/templates/README.md)。目录引用原始导出，不生成另一套业务节点。客服沿用 Dify 运行 ID；邮件与销售使用平台运行 ID，销售额外包含 followup_id。统一的是文档结构和查找方式，接口字段保留原有语义。

<a id="day50-验收口径"></a>

### 验收口径

检查新增目录能定位实际导出、Webhook 路径和绑定节点，样例能经过现有输入映射，邮件高优先级样例进入人工复核，销售样例通过输入校验。生成器只写请求文件，新事件标识独立，不覆盖已有输出。

Day 49 及历史业务验收继续沿用。不重复调用模型、运行 n8n、写入 CRM 或发送消息；离线映射检查不代表完整 n8n 执行、模型输出验证或新的端到端验收。

<a id="day50-后续"></a>

### 后续

Day 51 统一日志字段与来源，Day 52 整理集中配置和模型选择。真实通知编排及运行状态收尾继续作为明确待办。Day 50 不更新已发布的 v0.5.0 清单或标签。

<a id="day50-本轮检查结果"></a>

### 本轮检查结果

- 新增 Python 检查共 10 项通过：首次 9 项通过，1 项因测试临时目录权限未启动；改用工作区临时目录后仅补跑该项并通过。
- 六份新样例通过原导出的离线输入兼容检查；邮件高优先级样例验证人工复核分类，销售样例仅验证输入有效。
- 新增 Python 文件 Ruff 通过，Git 空白检查通过；离线生成器已成功生成一份独立销售请求说明文件。
- 新文档链接在本地检查，原工作流导出和 v0.5.0 清单没有改动。

Git 状态：用户已完成本地分支 `feature/day50-workflow-templates` 和提交 `fd59aef`。该提交尚未合并或推送；未执行新一轮业务联调。

---

<a id="day51"></a>

## Day 51：工作流结构化事件日志


Day 51 为客服、邮件和销售工作流增加统一事件日志，记录可关联的输入、输出、状态、处理时间和用量来源。基线是 Day 50 本地提交 fd59aef，平台 API 与既有请求/响应契约保持不变。

<a id="day51-日志放在哪里"></a>

### 日志放在哪里

原来的 `logs/app.log` 继续用于普通应用日志。API 启动时另行配置 `logs/workflow-events.jsonl`，一行一个 JSON 对象，同时输出到控制台。单文件达到约 5 MiB 轮转，保留 3 份备份；按当前单 API 进程使用，不宣称支持多进程共享文件的并发轮转。

日志目录已由现有 `.gitignore` 排除。Day 53 实测确认容器目录为 `/app/logs`，已有 `./logs:/app/logs` 挂载。此前关于 `backend/logs` 和缺少日志卷的表述不准确；路径及重建验收见 [Day 53 部署说明](week-8-notes.md#day53)。

<a id="day51-哪些调用会记录"></a>

### 哪些调用会记录

| operation | 记录时机 | 输入与输出 |
| --- | --- | --- |
| dify.call | `/dify/workflow` 调用完成或失败 | question/user；成功时 answer 与 outputs |
| workflow.start | 运行登记、重复命中或回放决策完成 | 实际返回的已保存 input_data，避免把重复请求的新内容误记为原输入 |
| workflow.finish | 保存成功/人工复核结果后 | 账本输入与已保存 output_data |
| workflow.checkpoint | 保存分析检查点后 | 账本输入与 checkpoint_data，覆盖销售 AI 分析结果 |
| workflow.fail | 按 run_id 保存失败后 | 已有账本输入/输出及安全错误类型 |
| workflow.fail_by_execution | n8n Error Trigger 按执行 ID 保存失败后 | 已有账本输入/输出及安全错误类型 |

这些是经过请求校验后进入路由的业务事件。框架直接拒绝的 422、只读查询、CRM 通知状态接口和 n8n 内部逐节点执行日志不在本次新增记录范围内。API 返回 200 表示记录操作成功，实际业务结果看 status；例如人工复核是 needs_human_review，失败落库可能是 failed。

<a id="day51-字段与关联方式"></a>

### 字段与关联方式

每行包含 schema_version、UTC timestamp、独立 log_event_id、operation、outcome、http_status、status、run_id、dify_run_id、event_id、workflow_name、n8n_execution_id、request_n8n_execution_id、retry_count、duplicate_count、processing_stage、failure_stage、error_type、duration_ms、elapsed_time_seconds、total_tokens、metrics_source、input、output 和 snapshot_policy。

- run_id 只放平台运行 ID，dify_run_id 只放 Dify ID。二者不互相替代。
- log_event_id 标识一条日志，不是跨系统 trace_id。当前邮件调用 Dify 时没有传平台运行 ID，不能仅凭日志时间把两者视为已经准确关联。
- request_n8n_execution_id 表示本次登记请求提供的执行号；n8n_execution_id 表示返回记录中的执行号。重复请求不会凭空覆盖原运行的执行归属。
- outcome 区分 success、duplicate、replayed、error；HTTP 错误只记录类型和状态码，不写原始异常正文或堆栈。
- 单条 API 事件不等于一次完整工作流；一个运行可有登记、检查点和完成等多条日志。

<a id="day51-时间与-token-如何理解"></a>

### 时间与 Token 如何理解

| 字段/来源 | 含义 |
| --- | --- |
| duration_ms | API 路由内部处理耗时，单调时钟测量；不含 n8n 全流程或日志写入时间 |
| elapsed_time_seconds + dify_response | Dify 响应报告的工作流耗时，不能等同于纯模型推理耗时 |
| total_tokens + dify_response | Dify 报告用量；缺失保留 null |
| workflow_client_reported | 完成接口调用方提供的耗时/Token，没有由日志层重新测量 |
| not_reported | 本事件未获得对应耗时/Token；字段保留 null |

邮件草稿的用量通常由 Dify 传入；人工复核分支沿用现有 0 值约定，日志如实记录为调用方报告。销售流程目前未上报模型 Token，保持 null，不从文本长度估算。重复、失败或检查点事件不将记录里残留的统计值当作新调用用量。

**不要把所有日志的 total_tokens 直接相加。** 同一次邮件 Dify 用量可能同时出现在 dify.call 和 workflow.finish，统计时应选一个来源并明确覆盖范围。回放保留相同平台 run_id，应结合 retry_count 区分尝试。

<a id="day51-输入输出记录范围"></a>

### 输入输出记录范围

快照先替换常见凭据字段以及 Bearer、sk- 和 key/value 形式的密钥，再限制字符串长度、嵌套深度与元素数量；单个快照超过 8000 字符时保留截断预览。日志字符串用 JSON 编码，换行不会伪造额外日志行。

这不是完整的个人信息匿名化工具，业务正文仍可能包含姓名、客户信息或商业内容；仅在当前可信本地环境中使用。不要通过日志公开业务正文。快照不会修改响应或数据库，完整业务输入/输出仍沿用现有账本存储规则。

请求执行期间日志构造或写入失败不会改变已经完成的业务响应，应用日志会尝试写入固定故障标记。JSONL 是尽力记录的诊断日志，不是和数据库事务原子提交的审计账本。

<a id="day51-如何查看"></a>

### 如何查看

在项目根目录，用 PowerShell 读取最新记录：

```powershell
Get-Content -LiteralPath logs/workflow-events.jsonl -Tail 20 | ForEach-Object { $_ | ConvertFrom-Json } | Select-Object timestamp,operation,outcome,run_id,dify_run_id,duration_ms,total_tokens,metrics_source
```

本次新增检查使用隔离临时数据库和模拟 Dify 响应，不调用模型、不运行 n8n、不发送消息。已验收业务链路继续沿用；新日志需要运行更新后的 API 才会产生，不会回填旧记录，也不声称已在当前容器验收。

<a id="day51-增量检查结果"></a>

### 增量检查结果

- 24 项直接相关检查通过，覆盖新增日志以及原有 Dify/工作流路由契约。
- 发现非有限浮点数可能导致整条日志丢失后，增加安全占位处理；仅补跑该新增边界，1 项通过。
- 新增及受影响 Python 文件通过 Ruff，Git 空白检查通过。
- 测试使用隔离临时数据库和模拟 Dify 响应，没有调用模型、运行 n8n、修改业务数据库或发送消息。

---

<a id="day52"></a>

## Day 52 配置中心与离线自检


Day 52 将六组后端配置集中到 `backend/app/settings.py`，保留原来的配置导入接口，并增加按组件执行的离线自检。修改配置前，先确定读取者是后端、Dify 还是 n8n。

<a id="day52-模型由谁选择"></a>

### 模型由谁选择

| 场景 | 配置归属 | 后端 LLM_PROVIDER 是否影响 |
| --- | --- | --- |
| `/rag/answer` 生成回答 | 后端环境变量 | 是，支持已有 DeepSeek 和 Qwen |
| 客服、邮件草稿 | Dify 应用模型节点与凭据 | 否 |
| 销售分析、日报 | n8n 模型节点与 Credentials | 否 |

`/chat` 当前回显输入，`/rag/query` 只执行检索，都不用于检验生成模型切换。Embedding 配置也不在本次范围内。GPT、Claude、本地模型尚未新增适配。

<a id="day52-加载与校验"></a>

### 加载与校验

FastAPI 在 lifespan 启动阶段显式调用 `load_environment()`；离线工具也在自己的入口调用它。导入 settings 或原有 `services/*_config.py` 不会读取 `.env`、创建客户端或验证凭据。直接编写独立 Python 调用脚本时，若需要 `.env`，也应先调用 `load_environment()`。

加载顺序：进程环境变量优先，源码确定的项目根目录 `.env` 补缺，未设置字段再使用默认值。启动目录不会改变默认文件位置。进程环境中的空值仍优先，必填字段会明确报缺项。`.env` 内容按字面读取，不展开 `${VARIABLE}`，兼容 UTF-8 与 UTF-8 BOM；默认文件可以不存在，显式指定的文件必须存在并可读。

配置对象按组件读取，不长期缓存。加载 `.env` 不覆盖已有进程变量，因此修改文件后应重启进程。企业微信仍通过配置对象比较决定是否替换 Token 服务缓存。

缺少可选集成配置不会阻止 `/health` 和 OpenAPI 启动；使用相应功能时才校验该组字段。Dify 和飞书超时现要求有限正数，拒绝 `NaN`、`Infinity` 和负数。企业微信固定地址、单成员限制、飞书接收者及重试规则保持原有语义。

模型、Dify、飞书的 Base URL 必须是具有主机名的 HTTP(S) 地址，不能包含用户名密码、查询参数、片段、空白或非法端口。内网 HTTP 和已有测试地址可继续使用；这是配置格式检查，不是地址可信性或网络连通性认证。错误信息不回显配置原值。

<a id="day52-配置清单"></a>

### 配置清单

以下字段均在使用对应组件时校验。敏感字段只保存在本地环境中；`.env.example` 提供空值示例。

| 组 | 环境变量 | 默认值或要求 |
| --- | --- | --- |
| RAG | `LLM_PROVIDER` | `deepseek`；也支持 `qwen`，去空白并转小写 |
| DeepSeek | `DEEPSEEK_API_KEY` | 敏感；选中该 Provider 时必填 |
| DeepSeek | `DEEPSEEK_BASE_URL` / `DEEPSEEK_MODEL` | `https://api.deepseek.com` / `deepseek-v4-flash` |
| Qwen | `DASHSCOPE_API_KEY` | 敏感；选中该 Provider 时必填 |
| Qwen | `QWEN_BASE_URL` / `QWEN_MODEL` | `https://dashscope.aliyuncs.com/compatible-mode/v1` / `qwen3.7-plus` |
| Dify 调用 | `DIFY_WORKFLOW_API_KEY` | 敏感；应用工作流 Key，必填 |
| Dify 调用 | `DIFY_API_BASE_URL` | Python 默认 `http://localhost/v1`；Compose 默认 `http://host.docker.internal/v1` |
| Dify 调用 | `DIFY_WORKFLOW_TIMEOUT_SECONDS` | `120`，有限正数 |
| 外部知识库 | `DIFY_EXTERNAL_KNOWLEDGE_API_KEY` | 敏感；检索鉴权 Key，必填，与工作流 Key 分开 |
| 外部知识库 | `DIFY_EXTERNAL_KNOWLEDGE_ID` | `enterprise-knowledge-hub`，不可为空 |
| 飞书鉴权 | `FEISHU_APP_ID` / `FEISHU_APP_SECRET` | 必填；Secret 为敏感字段 |
| 飞书鉴权 | `FEISHU_API_BASE_URL` / `FEISHU_TIMEOUT_SECONDS` | `https://open.feishu.cn/open-apis` / `10`，超时为有限正数 |
| 飞书发送 | `FEISHU_RECEIVE_ID_TYPE` / `FEISHU_RECEIVE_ID` | 类型默认 `chat_id`，也支持 `open_id`；接收者必填并符合对应前缀 |
| 飞书发送 | `FEISHU_MAX_ATTEMPTS` | 默认 `3`，1—5，包含首次尝试 |
| 飞书发送 | `FEISHU_RETRY_BASE_SECONDS` | 默认 `0.5`，有限非负数 |
| 企业微信 | `WECOM_CORP_ID` / `WECOM_AGENT_ID` | 必填；Agent ID 为正整数 |
| 企业微信 | `WECOM_APP_SECRET` / `WECOM_TO_USER` | 必填；Secret 为敏感字段，只允许单个接收成员 |
| 企业微信 | `WECOM_API_BASE_URL` / `WECOM_TIMEOUT_SECONDS` | 固定 `https://qyapi.weixin.qq.com` / 默认 `10`，超时为有限正数 |

表内模型默认值沿用当前项目，不代表供应商最新推荐。n8n 的 `N8N_ENCRYPTION_KEY`、URL、时区等运行设置仍由 Compose 管理；原生模型凭据保存在 n8n Credentials 中，不纳入后端必填字段。

<a id="day52-离线自检"></a>

### 离线自检

在项目根目录执行需要的组件：

```powershell
.\.venv\Scripts\python.exe -m backend.app.check_config --component llm
.\.venv\Scripts\python.exe -m backend.app.check_config --component dify
.\.venv\Scripts\python.exe -m backend.app.check_config --component external-knowledge
.\.venv\Scripts\python.exe -m backend.app.check_config --component feishu
.\.venv\Scripts\python.exe -m backend.app.check_config --component wecom
```

`feishu` 检查鉴权与发送两组配置，每组至多报告首个错误；修正后再检查。Dify/n8n 内部模型明确标为外部管理、未检查。

可用 `--env-file` 指定一份文件。它替代默认 `.env`，但进程变量仍优先：

```powershell
.\.venv\Scripts\python.exe -m backend.app.check_config --component llm --env-file 'C:\path\to\local.env'
```

使用 `--all` 要求五个组件全部配置有效。未配置企业微信会使该命令失败，这不表示整个平台不能启动：

```powershell
.\.venv\Scripts\python.exe -m backend.app.check_config --all
$LASTEXITCODE
```

| 结果 | 退出码 | 含义 |
| --- | --- | --- |
| `configuration_valid` | 0 | 所选组件通过本地配置校验 |
| `configuration_invalid` | 1 | 有必填项缺失、值不合法或环境文件不可读取 |
| CLI 参数错误 | 2 | 组件名称或参数组合不正确 |

工具输出 JSON，密钥只显示 `configured` / `missing`；不输出模型原值、接收者、完整 URL 或配置对象。敏感 dataclass 字段也不出现在 repr 中，但配置对象仍携带调用所需密钥，不能用 `asdict` 等方式直接公开。

自检不导入 FastAPI 应用、模型客户端或数据库，不发请求、不取 Token、不发送消息，也不写业务数据。成功仅代表配置格式有效，不验证凭据有效性、模型可用性、连通性或工作流执行。dotenv 对文件的语法处理沿用 python-dotenv；字段级校验不替代完整环境文件语法审计。

<a id="day52-配置修改何时生效"></a>

### 配置修改何时生效

| 改动 | 操作 |
| --- | --- |
| 本地 `.env` | 重启本地 FastAPI 进程 |
| Compose 注入 API 的变量 | 重建 API 容器以重新注入；只 restart 不够 |
| API 代码 | 构建新镜像并重建 API 容器 |
| Dify 模型 | 修改对应应用并发布，验收受影响的流程 |
| n8n 原生模型 | 修改模型节点或 Credential 绑定，按现有保存/发布流程生效并验收 |

后端统一入口没有改写 Dify/n8n 模型设置或已有工作流导出。销售流程仍为 preview，企业微信真实发送仍受既有准入条件限制。

<a id="day52-验证与后续"></a>

### 验证与后续

测试覆盖环境优先级、工作目录独立性、旧导入兼容、两个 Provider 的 Mock 客户端调用、有限超时、URL 校验、脱敏、无配置启动、CLI 退出码及无网络/数据库依赖。测试统一隔离开发者的环境配置和真实 `.env`。

验收结果：相关测试首次 123 项通过；最终全量回归 498 项通过，Ruff 通过。保留一项既有 ChromaDB 关于 `asyncio.iscoroutinefunction` 的弃用警告。全量检查发现 Day 51 日志测试直接赋值日志级别会留下级别缓存，已将该测试夹具改为 `setLevel()` 并在结束时恢复，修复后全量通过。

测试在不包含真实 `.env` 的隔离源码副本中运行，使用虚构凭据、Mock 客户端和临时数据库。没有调用真实模型、发送通知或重启业务服务。测试结果不代表当前运行中的 API 容器已经更新。Day 53 实测更正：应用日志实际在 `/app/logs`，与已有卷映射一致，原文对路径层级的判断不准确。部署脚本与持久化验收见 [Day 53 部署说明](week-8-notes.md#day53)。

---

<a id="day53"></a>

## Day 53 一键启动与持久化验收


Day 53 提供 Windows PowerShell 一键启动和部署检查，限制文件及容器日志容量，并通过独立测试容器的删除重建验证 SQLite 与日志保留。Dify 继续由已有独立部署管理。

<a id="day53-核实后的目录"></a>

### 核实后的目录

| 内容 | 宿主机 | 容器 |
| --- | --- | --- |
| SQLite | `data/enterprise_ai.db` | `/app/data/enterprise_ai.db` |
| Chroma | `data/chroma` | `/app/data/chroma` |
| 应用日志 | `logs/app.log` | `/app/logs/app.log` |
| 工作流事件 | `logs/workflow-events.jsonl` | `/app/logs/workflow-events.jsonl` |
| Embedding 缓存 | `data/chroma-cache` | `/home/app/.cache/chroma` |
| n8n 数据与凭据 | 当前 Compose 项目的 `n8n_data` 命名卷 | `/home/node/.n8n` |

Day 53 直接读取当前容器的代码路径和挂载，确认现有挂载正确。此前 Day 51/52 文档写成 `backend/logs` 或 `/app/backend/logs` 是路径层级判断错误，已更正。此次没有迁移数据库或更换数据卷；现有 SQLite 完整性检查通过。

<a id="day53-一键启动"></a>

### 一键启动

前提：Docker Desktop 已启动、使用 Linux 容器、Compose 2.20.0 或以上；项目根目录有已配置的 `.env`。现有环境继续使用原 `.env` 和 `N8N_ENCRYPTION_KEY`，修改 n8n 加密密钥会影响已有凭据解密。

在项目根目录执行：

```powershell
& .\scripts\start.ps1 -CheckComponents llm,dify
```

脚本按顺序执行：检查 Docker 与 Compose → 检查 `.env` 与 Compose 语法 → 构建 API 镜像 → 启动或更新 API 和 n8n → 等待健康 → 核对部署及选定组件配置。配置或构建失败时，不进入容器更新步骤。

只更新 API：

```powershell
& .\scripts\start.ps1 -ApiOnly -CheckComponents llm,dify
```

从任意目录也可使用脚本绝对路径，脚本会定位自己的项目目录。若 PowerShell 执行策略阻止运行，可在项目根目录使用单次进程策略，并先完成部署检查，再单独执行配置自检：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start.ps1 -ApiOnly
docker compose exec -T api python -m backend.app.check_config --component llm
docker compose exec -T api python -m backend.app.check_config --component dify
```

不传 `-CheckComponents` 时仍执行容器、数据库和日志检查，仅跳过可选第三方组件的配置检查。`-WaitTimeoutSeconds` 默认 120，可在 30—600 秒之间设置。

首次安装需要自行从 `.env.example` 建立本地 `.env` 并填入所需配置，脚本不创建、覆盖或输出凭据。API-only 操作的 Compose 解析仍需要现有 `N8N_ENCRYPTION_KEY`，因为同一配置中定义了 n8n 服务。

默认启动包含 n8n，已启用的定时工作流可能按原计划运行。脚本本身不调用业务 Webhook、模型或通知接口。它不执行 `down`、删除卷或 Docker prune，不自动结束占用端口的其他进程，也不重启独立 Dify 项目。

<a id="day53-只检查已有部署"></a>

### 只检查已有部署

```powershell
& .\scripts\check-deployment.ps1 -CheckComponents llm,dify
```

只检查 API 可增加 `-ApiOnly`。检查项包括：

- 找到本项目唯一运行中的 API 容器，并要求状态为 healthy。
- 确认 API 以 `app` 用户运行，三个可写 bind mount 指向本项目的预期目录。
- 从该容器内部访问 `/health` 和 OpenAPI，避免误把其他占用本机端口的程序当成 API。
- 使用只读连接检查 SQLite 完整性，确认两种日志文件存在。
- 按需执行 Day 52 离线组件自检，不验证真实凭据或模型连通性。
- 检查 n8n 健康状态以及 `/home/node/.n8n` 的可写命名卷。

脚本不输出容器环境变量或业务记录。日志文件存在和挂载正确不能单独证明“容器重建后保留”，该项由下面的隔离测试验证。

<a id="day53-日志容量"></a>

### 日志容量

`app.log` 与 `workflow-events.jsonl` 各使用约 5 MiB 的单文件轮转阈值，保留三份备份。每种日志通常约占 20 MiB；单条大记录和轮转时点可能造成偏差。这适用于当前单 API 进程，不宣称支持多个进程共同轮转同一文件。

API 与 n8n 的 Docker 控制台日志采用 `json-file`，`max-size=10m`、`max-file=3`。配置变更在相应容器重新创建后生效，现有容器不会因为修改 YAML 立即改变日志策略。日志有业务内容，不应直接公开上传。

<a id="day53-独立容器重建验收"></a>

### 独立容器重建验收

运行以下命令会构建独立镜像并创建临时 API，消耗本地 Docker 构建和磁盘资源；不会使用当前业务容器或真实 `.env`：

```powershell
.\.venv\Scripts\python.exe .\scripts\verify_persistence.py
```

验证脚本从现有 Compose 渲染 API 设置，使用独立项目名称、独立镜像标签、独立数据及日志目录；不映射宿主机服务端口，不启动 n8n，也不注入模型密钥。

验证流程：

1. 用同一份 `start.ps1 -ApiOnly` 启动隔离 API。
2. 通过本地 API 保存一条虚构工作流登记，确认宿主机事件日志出现标识。
3. 强制重新创建测试容器，要求新旧容器 ID 不同。
4. 通过 API 查回相同事件，确认原应用日志和工作流日志内容仍保留。
5. 再次执行部署检查，并核对 Docker 日志容量设置。
6. 清理本次唯一名称的测试容器、网络与镜像，保留本次目录中的 `result.json` 和虚构数据用于复查。

默认结果在 `logs/deployment-checks/day53-check-<随机标识>/result.json`，不纳入 Git。也可通过 `--work-dir` 指定测试输出父目录。测试失败时同样保存结果并尝试清理独立资源；不执行全局清理。

这项验收覆盖 API 的 SQLite 与两种文件日志，不等于重建验证了现有 n8n 凭据、Chroma 检索效果或真实业务工作流。

<a id="day53-常用操作与故障处理"></a>

### 常用操作与故障处理

```powershell
docker compose ps
docker compose stop
docker compose start
```

需要排查失败时，先保留脚本报错，再查看 `docker compose ps`。只有需要时在本机查看 `docker compose logs --tail 50 api` 或 n8n 日志，分享前去除业务内容。不要分享完整 `docker compose config`，日常语法检查使用 `--quiet`。

构建失败保留原容器；健康检查超时则保留现场，脚本不会自动回滚或删除服务。启动脚本可在问题修复后重新运行，Compose 会按配置更新服务。`down -v` 会删除命名卷，不用于日常停止或升级。数据持久化不代替备份；跨机器迁移还需要保存数据库、Chroma、n8n 卷及原加密密钥。

Windows PowerShell 构建阶段若曾出现 `failed to get console: The handle is invalid.`，使用修复后的脚本重新执行即可。脚本已显式指定 Compose `--ansi never --progress plain`，使重定向输出使用纯文本进度，避免自动选择交互终端界面。该错误发生在构建步骤时，脚本尚未执行后续容器更新。

<a id="day53-验收状态"></a>

### 验收状态

- 全量自动化测试：506 项通过；保留一项既有 ChromaDB 弃用警告。
- Ruff：后端、测试与新增持久化验证脚本通过。
- PowerShell 7 的启动、失败停止、错误挂载与路径带空格检查通过；Windows PowerShell 5.1 的模拟启动检查也通过。
- 真实隔离 Docker 验收通过：同一启动脚本成功启动 API，强制重建后 SQLite 记录、应用日志、工作流事件日志保留，日志驱动容量设置符合预期。
- 独立测试容器、网络和镜像已清理；原业务 API 容器 ID 与镜像保持一致，API 和 n8n 仍 healthy。

可提交证据见 [Day 53 部署验收结果](evidence/day53/deployment-validation.json)。当前业务环境的更新、分支推送和合并由维护者按交付步骤执行；本轮没有部署 Day 53 到业务容器，也没有调用真实模型或发送消息。

控制台兼容修复补验：8 项部署脚本测试及 Ruff 通过；在 Windows PowerShell 5.1 中设置 `BUILDKIT_PROGRESS=tty`，修复后的脚本仍以纯文本完成独立镜像构建、启动和重建持久化验证，测试资源已清理。未重复执行业务测试或更新业务容器。

---

<a id="day54"></a>

## Day 54 使用与架构文档


Day 54 将已有功能整理为可操作、可核对的文档入口，为 Day 55 演示准备操作依据。基线为 Day 53 合并提交 `43ec854`，此次只更新 Markdown 文档。

<a id="day54-交付内容"></a>

### 交付内容

| 文档 | 完成内容 |
| --- | --- |
| [平台使用指南](user-guide.md) | 首次配置、启动与检查、知识库操作、三类模板导入和请求示例、结果核对、故障恢复与日常运维 |
| [系统架构](architecture.md) | 服务调用图、网络地址、后端职责、RAG 数据流、销售状态恢复、配置日志与持久化边界 |
| [技术选型](tech-stack.md) | 将已经使用的 SQLite、Chroma、LLM、RAG、Dify、n8n 与未来候选技术区分 |
| [后端说明](../backend/README.md) | 替换初始化占位内容，补齐目录、开发入口和验证命令 |
| [项目首页](../README.md)、[文档目录](README.md)、[模板入口](../n8n/templates/README.md) | 统一导航，更新 Day 50–53 已完成能力的说明 |

<a id="day54-本次澄清的关键约定"></a>

### 本次澄清的关键约定

- 客服返回的 `workflow_run_id` 是 Dify ID；邮件同名字段和销售 `run_id` 才是平台账本 ID。
- API、Dify、n8n 分别管理模型选择和凭据，API 的配置自检不验证另外两个系统内部的模型配置。
- 模板生成器只输出请求说明，真正执行时只 POST 其中的 `body`。Test URL 需要监听，Production URL 需要工作流已发布。
- 配置格式通过、容器健康、业务成功和消息送达是不同验收结果。
- 销售通知仍为预览；CRM 已保存后禁止整条回放，通知未知状态需要先人工核对。
- 日志是限定范围的诊断记录，不能把重复出现的 Token 数直接累计为总用量。

<a id="day54-验证范围"></a>

### 验证范围

本次离线检查结果：

- 8 份文档的 207 个本地链接和源码路径均存在，20 个代码围栏完整，UTF-8 内容无替换字符。
- 14 段 PowerShell 示例在 Windows PowerShell 5.1 和 PowerShell 7.6 中均通过语法解析；未执行其中的部署或业务调用命令。
- 使用指南中的 RAG JSON 请求通过当前 `RagQueryRequest` 模型校验。
- 三类模板的六种场景均通过命令行生成独立请求文件，生成的字段和 Webhook 路径与目录契约一致；导入文件及凭据/错误处理绑定引用均存在。
- 对比 Day 53 基线，业务代码、配置模板、工作流导出和部署脚本内容均未变化。

本轮不调用业务 Webhook、模型或消息接口，也不修改 `.env`、业务数据、工作流导出或部署脚本。Day 53 的 506 项自动化测试和隔离 Docker 重建结果是历史验收，本轮不把它们写成重新执行的结果。

维护者已经反馈 Day 53 的 API/n8n 更新及健康检查通过，并将 Day 53 合并推送到 `main`。这些来自维护者的执行反馈，与本轮文档验证分别记录。

<a id="day54-交付与后续"></a>

### 交付与后续

这次更新无需重建容器。代码审阅、分支推送和合并完成后，Day 55 可以按使用指南准备演示环境和脚本，再记录实际业务结果。

Day 54 不创建新 Release，不改变 API `1.0.0` 或 Workflow Center `0.5.0` 的版本与历史发布清单。真实通知编排、统一鉴权、租户隔离和 Agent/Evaluation Center 仍不在当前已实现范围内。

---

<a id="day55"></a>

## Day 55：Workflow Center 业务 Demo


目标是在约 6–8 分钟的视频中展示一次真实的“客服咨询 → 邮件人工复核 → 销售分析与 CRM → 重复事件保护”。三个场景使用各自独立的虚构事件，不把它们描述成已实现的跨工作流自动接力。演示材料准备、现场执行、视频录制与视频验收分别记录。

本次交付的是录制讲稿、离线请求包工具、逐步请求执行工具和验收表。**尚未完成本轮真实业务演示或视频录制。** Day 49 业务证据和原 AI 客服视频保留为历史成果，不计作 Day 55 新录制。

**2026-09-17 排期调整：** 维护者暂时无法录制，已决定先进行 Day 56，之后补录。本页保留为后续操作稿，未完成项继续待验收；阶段总结与发布安排见 [Week 8 总结](week-8-summary.md) 和 [v1.0 候选说明](workflow-center-v1.0.md)。恢复录制时按当日环境生成新演示包。

<a id="day55-1-演示主线"></a>

### 1. 演示主线

| 环节 | 要展示的业务价值 | 本次通过依据 |
| --- | --- | --- |
| 客服咨询 | 从已有知识库回答产品问题 | 实际回答有依据；记录 Dify 执行 ID |
| 邮件人工复核 | 高优先级请求交给人工处理 | `needs_human_review`、空草稿和平台持久化状态一致 |
| 销售跟进 | 分析线索并形成可追踪的 CRM 跟进 | 正常业务结果、平台运行、分析检查点、唯一跟进记录；通知为 preview |
| 重复事件 | 重复提交不会创建第二条跟进 | 相同 run_id、`duplicate=true`、`processed=false`，跟进仍为一条 |
| 工程支撑 | 配置、部署和日志可检查 | 展示本次检查结果及按运行标识筛选的日志，解释各自覆盖范围 |

邮件片段特意选择 `priority=high` 的确定性人工复核分支，不声称该片段使用了 LLM 分类。客服和销售需要模型调用；邮件草稿生成可作为扩展片段，步骤见 [邮件模板](../n8n/templates/email-assistant/README.md)。销售风险识别结果由实际模型和校验决定，不预先保证一定走正常分支。

<a id="day55-2-录制前准备"></a>

### 2. 录制前准备

先按 [使用指南](user-guide.md) 确认部署、凭据和三个模板。现有环境复用工作流，避免导入相同 Webhook 路径的副本。

- API、n8n 已运行；独立 Dify 工作流已发布且能读取所需知识库。客服样例询问“知识库支持哪些文档格式”，Dify 应用需已接入包含该信息的项目资料。
- 客服、持久化邮件和销售工作流均已发布，才能使用下面的 Production URL。邮件主流程的 Error Workflow 已绑定；销售节点已绑定 n8n 内的 DashScope 凭据。
- 使用虚构数据；关闭 `.env`、凭据页面和无关通知。画面只保留终端、n8n 对应执行和项目文档。
- 预留终端和浏览器可读字号；先试录约 10 秒检查声音与文字，再正式录制。既有视频文件不覆盖，新视频放在仓库之外。

在项目根目录检查现有部署：

```powershell
Set-Location 'C:\Users\Administrator\Desktop\enterprise-ai-platform'
& .\scripts\check-deployment.ps1 -CheckComponents llm,dify
```

配置检查只验证格式。`llm` 是 API 自己的模型配置，不能代替销售的 n8n Credential 检查；Dify 连通性与业务输出需要执行后核对。本轮脚本不更新镜像，演示工具无需重建容器。

<a id="day55-3-生成本次录制请求包"></a>

### 3. 生成本次录制请求包

使用已准备好的项目 Python 环境，以下操作完全离线：

```powershell
$demoDir = Join-Path $env:TEMP ('day55-demo-' + [guid]::NewGuid().ToString('N'))
.\.venv\Scripts\python.exe .\scripts\day55\prepare_demo.py `
    --production --output-dir $demoDir
if ($LASTEXITCODE -ne 0) { throw '演示包生成失败' }
Get-Content -LiteralPath (Join-Path $demoDir 'manifest.json') -Raw -Encoding UTF8
```

保留终端打印的目录，后续命令在同一个 PowerShell 会话执行。换窗口后，把 `$demoDir` 设置为该目录的完整路径；恢复查看结果时不要重新生成另一批事件。

| 文件 | 用途 |
| --- | --- |
| `01-customer.request.json` | 客服咨询 |
| `02-email-review.request.json` | 高优先级邮件人工复核 |
| `03-sales.request.json` | 一条独立销售线索 |
| `04-sales-duplicate.request.json` | 与首次销售请求完全相同，用于重复保护演示 |
| `manifest.json` | 本批标识、URL、请求哈希、准备状态 |
| `recording-notes.json` | 尚未填写的业务和视频验收记录，默认检查结果均为 null |

每个新目录有独立事件和客户标识；销售日期取上海时区当天。输出目录必须不存在，即使空目录也拒绝覆盖。生成器复用 Day 50 模板，只替换演示标识与请求来源，不修改原始模板或工作流。

`--production` 仅生成生产 URL，不发布工作流或执行请求。省略时生成 Test URL，每次提交前需要重新开启相应 Webhook 的测试监听，包括销售重复请求。正式视频建议用已发布的 Production URL。

准备清单内的 `execution_performed=false` 描述生成时的状态，不会随着后续执行自动更新；本次真实执行以各步骤的 `.result.json` 和持久化记录为准。演示结果不会自动写成通过。

<a id="day55-4-逐步执行与核对"></a>

### 4. 逐步执行与核对

下面的步骤会发送真实 Webhook 请求，产生演示运行及 CRM 数据，客服和销售会调用模型。每步确认结果后再继续，不要一次性粘贴全部步骤。执行工具只支持本机 HTTP n8n 地址，默认 `localhost:5678`；它仅发送请求文件的 `body`。

执行前核对请求哈希和对应 Webhook 路径。执行开始先建立结果文件；HTTP 失败、超时或中断后也阻止直接重复执行同一步。`response_received_unverified` 只表示收到 HTTP 响应，业务状态仍需按下文确认。工具不读取 n8n 执行 API，不宣称已核对节点轨迹。

<a id="day55-a-客服问答"></a>

#### A. 客服问答

```powershell
& .\scripts\day55\invoke-demo-step.ps1 -BundleDirectory $demoDir -Step 01-customer
```

查看回答与知识依据，不以 HTTP 200 代替答案正确性。`workflow_run_id` 属于 Dify，到 Dify 的对应运行记录核对；本客服模板没有平台事件去重。未检索到依据时可以展示真实拒答，但本项“有依据的资料咨询”验收仍待完成。

<a id="day55-b-邮件人工复核"></a>

#### B. 邮件人工复核

```powershell
& .\scripts\day55\invoke-demo-step.ps1 -BundleDirectory $demoDir -Step 02-email-review
$mail = (Get-Content -LiteralPath (Join-Path $demoDir '02-email-review.result.json') -Raw -Encoding UTF8 | ConvertFrom-Json).response
if (-not $mail.workflow_run_id) { throw '邮件未返回平台运行 ID，请检查结果' }
$mailRun = Invoke-RestMethod -Method Get -Uri ("http://127.0.0.1:8000/workflow-runs/" + $mail.workflow_run_id)
$mailRun | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath (Join-Path $demoDir 'email-run.json') -Encoding UTF8
$mail | Select-Object status, need_human_review, draft_reply, workflow_run_id, persisted_status
$mailRun | Select-Object run_id, status, priority
```

预期响应 `need_human_review=true`、`draft_reply` 为空，平台状态为 `needs_human_review`。这里没有发送邮件，也没有自动完成真正的人工审核。

<a id="day55-c-销售分析与-crm"></a>

#### C. 销售分析与 CRM

```powershell
& .\scripts\day55\invoke-demo-step.ps1 -BundleDirectory $demoDir -Step 03-sales
```

先查看 `status`、`requires_human_review`、分析内容和通知。正常演示要求 `succeeded`、无需人工复核和 `notification.mode/status=preview`。若模型返回风险标记或发生异常，先保留事实并排查；不要把复核分支改写成成功。

确认正常结果后读取本轮持久化记录，并保存重复请求前的快照：

```powershell
$sales = (Get-Content -LiteralPath (Join-Path $demoDir '03-sales.result.json') -Raw -Encoding UTF8 | ConvertFrom-Json).response
if ($sales.status -ne 'succeeded' -or -not $sales.run_id -or -not $sales.followup_id) {
    throw '销售结果尚未满足正常演示条件，请检查已保存结果'
}
function Get-Day55SalesState {
    [ordered]@{
        workflow = Invoke-RestMethod -Method Get -Uri ("http://127.0.0.1:8000/workflow-runs/" + $sales.run_id)
        followup = Invoke-RestMethod -Method Get -Uri ("http://127.0.0.1:8000/crm/followups/" + $sales.followup_id)
        followups = Invoke-RestMethod -Method Get -Uri ("http://127.0.0.1:8000/crm/customers/" + $sales.customer_id + '/followups')
    }
}
$before = Get-Day55SalesState
$before | ConvertTo-Json -Depth 40 | Set-Content -LiteralPath (Join-Path $demoDir 'sales-before-duplicate.json') -Encoding UTF8
$before.workflow | Select-Object run_id, status, duplicate_count, retry_count, processing_stage
$before.followup | Select-Object followup_id, notification_mode, notification_status, notification_attempt_count
$before.followups | Select-Object count
```

查看完整快照中的分析检查点和跟进分析，核对归属于本次事件。首次正常运行应只保存一条跟进，通知 `preview`、尝试次数 0。通知预览不等于飞书或企业微信送达。

<a id="day55-d-重复事件保护"></a>

#### D. 重复事件保护

保留同一份销售输入，不更改 event_id，不设置 replay。工具要求首次销售结果已保存且为成功预览状态，才允许发送重复请求：

```powershell
& .\scripts\day55\invoke-demo-step.ps1 -BundleDirectory $demoDir -Step 04-sales-duplicate
$duplicate = (Get-Content -LiteralPath (Join-Path $demoDir '04-sales-duplicate.result.json') -Raw -Encoding UTF8 | ConvertFrom-Json).response
$after = Get-Day55SalesState
$after | ConvertTo-Json -Depth 40 | Set-Content -LiteralPath (Join-Path $demoDir 'sales-after-duplicate.json') -Encoding UTF8
$duplicate | Select-Object run_id, event_id, duplicate, processed
$after.workflow | Select-Object run_id, status, duplicate_count, retry_count
$after.followups | Select-Object count
$after.followup | Select-Object followup_id, notification_status, notification_attempt_count
```

逐项核对：原 `run_id`、`duplicate=true`、`processed=false`；前后跟进 ID 一致且数量始终为 1；`duplicate_count` 从 0 增至 1，`retry_count` 保持 0；通知仍为 preview、尝试次数 0。这是演示核对，完整的 CRM 字段不变验收沿用 [Day 49 记录](week-7-notes.md#day49)，不把本轮人工展示描述成重新执行了全部回归。

<a id="day55-e-查看本轮日志"></a>

#### E. 查看本轮日志

```powershell
$runIds = @($mail.workflow_run_id, $sales.run_id)
Get-Content -LiteralPath '.\logs\workflow-events.jsonl' -Tail 300 |
    ForEach-Object { $_ | ConvertFrom-Json } |
    Where-Object { $_.run_id -in $runIds } |
    Select-Object timestamp, operation, outcome, run_id, duration_ms, total_tokens, metrics_source
```

只展示本轮运行的诊断字段。若日志已轮转，到对应备份里查找，不能以最近 300 行未出现记录就认定业务失败。客服 Dify ID 可用 `dify_run_id` 筛选。日志没有统一全链路 trace_id；用量缺失可能为 null，也不能跨事件简单累加 Token。

<a id="day55-5-录制时间轴与讲稿"></a>

### 5. 录制时间轴与讲稿

| 时间 | 画面与操作 | 讲解要点 |
| --- | --- | --- |
| 0:00–0:40 | README 与架构图 | “平台现在有知识库和工作流中心。这次用三类业务场景展示问答、人工复核和销售跟进。” |
| 0:40–1:10 | 本次部署检查结果 | “API 与 n8n 健康，配置格式通过。真实模型是否可用，要看接下来的业务执行。” |
| 1:10–2:10 | 客服实际请求、回答和 Dify 记录 | “这次咨询通过 n8n、API 到 Dify，再依据接入资料回答。这里的执行 ID 属于 Dify。”只按实际回答解释依据。 |
| 2:10–3:00 | 邮件响应与平台运行 | “高优先级请求进入人工复核，不生成自动草稿。平台已保存状态，但没有自动发送邮件。” |
| 3:00–4:40 | 销售输入、分析和 CRM | “模型整理需求、缺失信息和跟进建议。分析检查点和 CRM 跟进关联到同一次平台运行。”展示实际结果。 |
| 4:40–5:40 | 原事件重复提交与前后快照 | “再次提交的是同一个业务事件。系统返回原运行，跟进仍只有一条，避免重复业务写入。” |
| 5:40–6:30 | 过滤后的日志、模板和配置入口 | “模板便于复用，日志用于排障。API、Dify 和 n8n 各自管理模型配置。” |
| 6:30–7:00 | 结果与当前边界 | “销售通知目前是预览。真实通知编排、统一鉴权与租户隔离仍待完善，Day 56 再整理阶段发布。” |

按真实耗时留出余量；可剪去等待时间，并在剪辑处标注。不要将历史截图插入后当成本次实时执行，录制失败时不按预写讲稿宣称成功。

<a id="day55-6-失败处理与录制验收"></a>

### 6. 失败处理与录制验收

| 情况 | 本轮处理 |
| --- | --- |
| 输出目录已存在 | 查看原包；独立的新演示才生成新目录。生成失败可能保留部分文件，不覆盖旧目录 |
| 请求哈希不匹配 | 核对是否修改了请求；不要修改清单哈希来绕过检查。需要自定义输入时使用模板指南并单独留证 |
| 结果文件已存在 | 查看该步骤结果与原事件；不要删除文件来触发重发 |
| Test URL 不监听、生产 Webhook 未发布、HTTP 失败或超时 | 保留结果文件和原事件标识，查 n8n 执行及平台状态；超时可能已经完成部分业务写入 |
| 邮件或销售业务状态异常 | 先排查原运行；CRM 已保存后不整条回放，恢复规则见使用指南 |
| 第一次销售结果无需再次请求，只想补录画面 | 展示已保存结果，说明是本轮记录回看；只读查询可以重新执行 |
| 模型不可用 | 录制可以暂停；历史证据仅作为明确标注的历史片段，当前未完成项保持待验收 |

演示包的执行保护只覆盖本工具，不是服务端幂等替代品；客服流程本身仍没有事件去重。`.result.json` 保存原输入和实际响应，`business_verified` 初始为 false，需用本次快照填写 `recording-notes.json`。不要将 HTTP 响应成功直接填作全部业务通过。

按 [录制验收表](../demo/day55-recording-checklist.md) 核对视频和业务结果，保存本批请求、响应、快照、验收记录和视频文件。视频保留在仓库之外，可用以下命令计算真实文件的 SHA-256，再填写记录：

```powershell
# 将路径替换为本次实际录制的视频文件。
Get-FileHash -LiteralPath 'C:\Users\Administrator\Videos\day55-workflow-center-demo.mp4' -Algorithm SHA256
```

`recording-notes.json` 的状态在完成录制后可改为 `recorded_pending_review`，全部必需检查通过后再改为 `accepted`；未检查保持 null，失败填 false 并记录问题。生成器和请求执行工具不会自动标记视频完成或发布新版本。

<a id="day55-7-本次材料验证"></a>

### 7. 本次材料验证

基线为 Day 54 合并提交 `1764740`。本轮检查结果：

- 19 项离线/隔离模拟检查通过，覆盖批次唯一性、原文件保留、销售重复输入一致性、默认测试 URL、UTF-8 请求体、错误与超时留证、重发拦截、请求修改拦截、重复步骤前置条件、本机地址约束和禁止重定向。
- 请求工具在 Windows PowerShell 5.1 和 PowerShell 7.6 中使用临时本地模拟 HTTP 服务验证；11 次请求全部发给该模拟服务，未调用真实 n8n、模型、业务 API 或消息接口。
- 14 段文档 PowerShell 示例及请求脚本在两个 PowerShell 版本中通过语法解析；7 份相关文档的 142 个本地链接检查通过。
- 新增 Python 工具通过 Ruff 检查与格式检查。业务代码、部署配置和工作流导出沿用基线，没有因本轮工具准备重新进行容器部署或全量业务回归。

以上只证明演示材料与工具的相应行为。Day 55 的真实业务展示、视频文件和人工验收仍待完成，不能将模拟结果填写进正式录制验收记录。
