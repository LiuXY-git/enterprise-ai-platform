# Week 15：作品集打造

学习路线：Day 99–105。当前完成 Day 99–100；本周其他任务仍为计划。

本周把已实现的功能整理成别人能够快速理解、运行和追问的作品集。每日实施记录集中在本页，结果见 [Week 15 摘要](evidence/week-15.md)。

[总目录](README.md#按周阅读) · [上一周](week-14.md)

## 本周目录

- [计划与进度](#plan)
- [Day 99：GitHub README 与功能展示](#day99)
- [截图来源与复刻](#day99-screenshots)
- [验证范围与后续](#day99-validation)
- [Day 100：系统架构图](#day100)
- [架构与数据流怎么读](#day100-reading)
- [图中节点对应哪些代码](#day100-code)
- [复刻与验证](#day100-reproduce)
- [一分钟项目架构讲解](#day100-talk)

<a id="plan"></a>

## 计划与进度

| 日期 | 路线要求 | 当前状态 |
| --- | --- | --- |
| Day 99 | 整理 GitHub，README 包含项目介绍、技术架构、功能截图和部署方式 | 已完成本地修改与验证 |
| Day 100 | 制作系统架构图 | 已完成总图、RAG 数据流、代码映射、SVG 与 PNG 导出 |
| Day 101 | 制作 3–5 分钟项目 Demo 视频 | 待开始；录制时间由维护者安排 |
| Day 102 | 项目介绍文档：为什么做、解决什么问题 | 待开始 |
| Day 103 | 准备 RAG、Agent、评估、部署与监控技术问题 | 待开始 |
| Day 104 | 模拟 FDE 项目面试 | 待开始 |
| Day 105 | 整理简历中的项目描述 | 待开始 |

维护者选择先进入 Day 99；Day 98 的正式标签与 Release 继续作为待办。候选成果可定位到 Day 98 合并提交 abe0c64d7cc3c77695f33e6912662e6b01040ada；本日未修改该版本清单。当前主线继续迭代作品集，正式发布时需明确选择要发布的提交及对应验收。

<a id="day99"></a>

## Day 99：GitHub README 与功能展示

### 做了什么，有什么用

[项目 README](../README.md) 现在按初次阅读顺序说明：项目解决什么问题、每个模块在哪里使用、界面是什么样、组件如何连接，以及如何部署和测试。

- 以资料检索、流程追踪和 Agent 改动比较三个问题介绍项目。
- 保留模块能力与边界，明确网页、API、CLI 的不同入口。
- 用现有前端的桌面与移动端截图展示上传回执、检索问题、文件来源和制度原文。
- 用 Mermaid 概览实际拓扑：三个 Compose 服务、嵌入式 SQLite/Chroma、独立 Dify 和宿主机 Agent/MCP/评测。
- 给出新实例、已有配置、本地 API 开发与 API 回归的操作入口。
- 说明 Day 98 测试数字的执行时间与范围，避免把离线通过率当作真实模型质量。
- 保留 README 既有章节链接，增加本周入口；无需翻阅零散 Day 文件。

这些改动让阅读者从首页就能区分“可演示能力”“运行方法”和“后续待办”。本日没有修改前后端业务行为，没有修改 GitHub 仓库可见性、About、Topics 或创建远端 Release；合并推送后 README 和图片才会出现在远端分支中。

<a id="day99-screenshots"></a>

### 截图来源与复刻

素材：

- [桌面截图](assets/week-15/knowledge-desktop.png)
- [移动端截图](assets/week-15/knowledge-mobile.png)
- [采集脚本](../scripts/portfolio/capture_readme.cjs)
- [虚构制度文档](../demo/nebula-it-policy.md)

脚本用临时回环 HTTP 服务提供真实 frontend/public 文件，随后在无头浏览器中上传虚构 Markdown、填写问题并点击检索。返回的制度原文从仓库演示文档的 P1 小节读取；上传回执和检索接口为固定响应，不运行解析、索引、Embedding、Chroma 查询或生成模型。

因此截图证明的是**现有页面如何呈现这些响应**，不证明后端语义检索质量。README 的图片前已注明这一范围。图中“后端已连接”来自临时 fixture 健康响应，不代表现有业务容器正在运行。

本次采集使用 Node.js 24.19.0、Playwright 1.62.1 和 Microsoft Edge。复刻需要 Node.js >=20、可用的 Playwright 与其浏览器。已有工具环境可直接使用；如需独立安装截图工具，在仓库外建立工具目录：

~~~powershell
$shotTools = Join-Path $env:TEMP 'eap-readme-capture-tools'
New-Item -ItemType Directory -Force -Path $shotTools | Out-Null
npm install --prefix $shotTools playwright@1.62.1
if ($LASTEXITCODE -ne 0) { throw '截图工具安装失败' }
$env:PLAYWRIGHT_MODULE = Join-Path $shotTools 'node_modules\playwright'
# 使用本机已安装的 Microsoft Edge；也可使用 Playwright 已安装的 Chromium。
$env:BROWSER_CHANNEL = 'msedge'
~~~

在仓库根目录执行：

~~~powershell
$shotOutput = Join-Path 'logs' ('readme-capture-' + [guid]::NewGuid().ToString('N'))
node scripts/portfolio/capture_readme.cjs $shotOutput
if ($LASTEXITCODE -ne 0) { throw '截图未完成，请查看错误信息' }
~~~

输出两个 PNG 和 capture.json。运行目录必须是新目录；脚本拒绝覆盖已有截图。确认画面与来源后，才把两个 PNG 更新到 docs/assets/week-15/ 并在 README 保留说明。

capture.json 记录页面/脚本/演示文档的内容摘要、图片摘要、问题、请求路径和验证范围；本次记录收在 Week 15 数据包中。脚本只访问临时本机服务器，结束后关闭浏览器和临时服务，不启动此前关闭的项目首页。

<a id="day99-validation"></a>

### 验证范围与后续

本日重新运行截图流程：检查健康状态、上传交互、固定来源与原文、桌面/移动布局及请求范围，未出现浏览器脚本错误。人工查看了两张完整截图，文字、输入和结果区域可见，移动端无横向溢出。

另外检查 README、Week 15 和目录的本地链接与原有 README 锚点；解析 PowerShell 命令块，并运行既有 README 文档契约测试。运行时代码不变，没有重新执行 Day 98 的 1,615 项回归；部署命令按现有工具核对，没有在本日重新部署服务。

Day 100 再围绕系统架构图补充更完整的项目表达。Day 101 的视频、Day 98 的正式发布以及原有视频与真实模型评测等待办均未自动完成。

<a id="day100"></a>

## Day 100：系统架构图

### 做了什么，有什么用

本日把系统结构变成两张可直接放进 README、讲解材料或演示视频的图。架构图回答“组件在哪里运行、谁调用谁、数据保存在哪里”；RAG 图回答“上传、检索和生成回答分别经过哪些步骤”。

| 素材 | 可缩放原图 | 分享或插入文档 |
| --- | --- | --- |
| 系统架构 | [SVG](assets/week-15/system-architecture.svg) | [PNG](assets/week-15/system-architecture.png) |
| RAG 数据流 | [SVG](assets/week-15/rag-data-flow.svg) | [PNG](assets/week-15/rag-data-flow.png) |

素材由 [Python 生成脚本](../scripts/portfolio/build_architecture.py)维护，[浏览器导出脚本](../scripts/portfolio/export_architecture.cjs)生成 PNG。SVG 使用文字、矩形与连线，便于放大；没有远程字体、脚本或外链图片。PNG 用于需要位图的工具。修改结构时更新生成脚本，再生成两种格式，避免图文分叉。

本日交付是架构表达与学习材料；没有增加业务接口或更改执行流程。

<a id="day100-reading"></a>

### 架构与数据流怎么读

![当前系统架构](assets/week-15/system-architecture.svg)

先看上半部分的三个 Compose 服务：

1. **浏览器 → frontend**：8080 端口提供静态页面。页面把上传和查询发到同源的 `/api/` 路径，Nginx 去掉这个前缀，再代理到 API。它没有承担完整的身份认证、限流或通用 API Gateway 职责。
2. **API 客户端 → api**：8000 端口提供 FastAPI。路由处理 HTTP 契约，业务服务处理索引、检索和工作流，数据访问模块保存记录。SQLite 和 Chroma 是嵌入式组件，不能把每个方框都理解为独立容器或微服务。
3. **n8n → api**：n8n 在 5678 端口编排已导入的 HTTP 工作流。图表示模板的可配置调用关系，不表示启动容器后所有模板已发布或持续运行。
4. **API ↔ Dify**：平台可以代理 Dify 工作流；Dify 也可以通过 `/retrieval` 调用平台知识检索。两条箭头对应不同接口。Dify 独立部署，其模型配置与平台 API 分开。
5. **API → 生成模型**：知识库生成式回答按 API 的配置选择模型。片段检索使用本地嵌入模型，不消耗生成模型请求；首次嵌入可能下载模型。CRM、飞书和企业微信还有独立 API 入口，完整清单看 [接口职责](week-14.md#day97-api)。

再看下半部分的宿主机 CLI：

- Evaluation Center 选择固定测试用例，隔离子进程调用 Day 82 候选入口。该路径使用固定模型响应，实际通过本地 stdio MCP 查询本次运行目录内的虚构销售 SQLite。
- Agent 提出工具请求，由程序校验范围和参数，MCP 执行固定只读查询；工具结果回填后，程序核对金额、来源和完成状态。
- 合格简报可以生成待审批提案。人工确认是单独的本地操作；批准后写入模拟发件箱。本评测准备入口不会替人批准，也不会真实通知销售人员。
- 执行证据供独立规则评分和报告读取；耗时、调用次数及已知 usage 随报告保存。评测框架的“通过”只针对这些固定用例。
- Planning、Memory 仍是独立实验；图中不把它们连成一个任意目标自动执行系统。任务日志回放用于查看发生过什么，不等于自动接续所有未完成步骤。

### RAG：上传和提问的具体路径

![上传、片段检索与生成回答的数据流](assets/week-15/rag-data-flow.svg)

以虚构 IT 制度中的“P1 故障如何升级”为例：

1. 上传 Markdown：API 解析文本，在 SQLite 建立 `indexing` 文档记录，按默认 200 字符、50 字符重叠切分，计算嵌入并 upsert 到 Chroma。成功后更新为 `indexed`；索引阶段失败会更新为 `index_failed`。
2. 网页提问：`/rag/query` 将问题嵌入，在 Chroma 中取 top_k 片段，返回原文、来源等。页面展示的是检索材料，没有自动进入生成模型。
3. 需要生成回答时：API 客户端调用 `/rag/answer`，后端先执行同一检索函数。有片段才调用配置的生成模型；没有片段时直接返回“无法从当前知识库确定。”。返回来源便于核对，但来源标签本身不能保证内容正确。

流程图展示的是同步索引路径，没有额外的消息队列或后台索引服务。以上是代码路径说明，本日未重新执行上传或模型请求。

### 数据与证据保存在哪里

| 数据 | 当前存储 | 用途与边界 |
| --- | --- | --- |
| API 文档、工作流及业务记录 | `data/enterprise_ai.db`（SQLite） | 文档状态与业务记录；不是 Agent 的运行库 |
| 文档片段、向量和元数据 | `data/chroma/` | Chroma 持久化；嵌入模型缓存另有 Compose 挂载 |
| 请求和工作流日志 | `logs/` | 故障追踪；Compose 日志另有大小与文件数限制 |
| n8n 配置与执行数据 | `n8n_data` 命名卷 | 迁移需保留匹配的加密密钥 |
| 当前评测调用的 Agent 数据 | 本次用例的 `artifacts/fictional.sqlite`、`tasks.sqlite`、`approvals.sqlite` 等 | 虚构源数据、任务日志与审批记录；与 API 库分开 |
| 评测输出 | 本次运行目录中的 JSON、SQLite、逐例结果与评分报告 | 保留上下文才能复核；不是只看最终百分比 |

<a id="day100-code"></a>

### 图中节点对应哪些代码

| 图中内容 | 代码入口 | 阅读重点 |
| --- | --- | --- |
| 三服务部署与挂载 | [compose.yaml](../compose.yaml) | services、ports、volumes 与服务依赖 |
| 浏览器调用与同源代理 | [app.js](../frontend/public/app.js)、[nginx.conf](../frontend/nginx.conf) | `/api/` 请求与 `proxy_pass` 的路径转换 |
| API 组装与路由 | [application.py](../backend/app/application.py)、[registry.py](../backend/app/routers/registry.py) | 工厂、生命周期与路由注册 |
| 上传与索引状态 | [upload.py](../backend/app/routers/upload.py) | 解析、文档记录、索引与失败分支 |
| 切分与嵌入 | [indexing_service.py](../backend/app/services/indexing_service.py)、[embedding_service.py](../backend/app/services/embedding_service.py) | 默认参数、批量嵌入与写入元数据 |
| Chroma 和 SQLite | [vector_store.py](../backend/app/services/vector_store.py)、[database.py](../backend/app/database.py) | 嵌入式客户端和磁盘路径 |
| 检索与生成分支 | [rag.py](../backend/app/routers/rag.py)、[retrieval_service.py](../backend/app/services/retrieval_service.py)、[rag_service.py](../backend/app/services/rag_service.py) | query / answer 分工、无片段时短路 |
| Dify 双向接口 | [dify.py](../backend/app/routers/dify.py)、[external_knowledge.py](../backend/app/routers/external_knowledge.py) | 工作流代理与外部知识库检索 |
| 评测执行与隔离 | [runner.py](../experiments/day87/runner.py)、[worker.py](../experiments/day87/worker.py) | 固定用例映射、子进程与观察值 |
| Agent 候选准备 | [prompt_lab.py](../experiments/day82/prompt_lab.py) | `prepare` 固定响应、运行数据和审批提案 |
| MCP 工具服务 | [sales_mcp_server.py](../experiments/day72/sales_mcp_server.py) | 固定只读工具与 stdio |
| 人工确认 | [hitl_agent.py](../experiments/day80/hitl_agent.py)、[approval_store.py](../experiments/day80/approval_store.py) | 提案摘要、批准/拒绝、模拟发件箱 |
| 评分与报告 | [scoring.py](../experiments/day90/scoring.py)、[runner.py](../experiments/day90/runner.py) | 标准答案、规则、分母和完整性检查 |
| 独立记忆与规划材料 | [会话记忆](../experiments/day75/README.md)、[规划示例](../experiments/day76/README.md) | 尚未与销售执行流程自动串联 |

<a id="day100-reproduce"></a>

### 复刻与验证

生成 SVG 只使用 Python 标准库，不需要启动平台或安装绘图服务。在仓库根目录执行，使用新目录保留上一次输出：

~~~powershell
$diagramRun = Join-Path 'logs' ('architecture-' + [guid]::NewGuid().ToString('N'))
$diagramSvg = Join-Path $diagramRun 'svg'
$diagramPng = Join-Path $diagramRun 'png'
.\.venv\Scripts\python.exe -B scripts/portfolio/build_architecture.py $diagramSvg
if ($LASTEXITCODE -ne 0) { throw '架构 SVG 生成失败' }
~~~

导出 PNG 需要 Node.js >=20、Playwright 与可用的 Chromium 或 Microsoft Edge。可以复用 [Day 99 的工具准备](#day99-screenshots)。将 PLAYWRIGHT_MODULE 指向已安装的 Playwright；使用系统 Edge 时：

~~~powershell
$env:BROWSER_CHANNEL = 'msedge'
node scripts/portfolio/export_architecture.cjs $diagramSvg $diagramPng
if ($LASTEXITCODE -ne 0) { throw '架构图导出失败，请查看字体或图形边界错误' }
~~~

脚本只读取上述两个固定名称的本地 SVG，在无头浏览器中核对文字与卡片边界、检查画布范围并导出 PNG。它拒绝外部资源并阻止网络请求，结束时关闭浏览器。输出包括两个 PNG 和 render.json；字体不同可能改变 PNG 外观或触发溢出，需要先查看图片再更新仓库素材。SVG 生成结果应可重复。

本次验证包括：核对 Compose 与调用路径、两张 SVG 重复生成一致、导出后的文字边界检查、两张 PNG 人工查看、文档链接及旧 README 锚点检查、命令块语法解析，以及既有文档契约测试。结果集中在 [Week 15 摘要](evidence/week-15.md#day100)。

本日没有变更应用、容器或评测逻辑，没有重跑完整业务回归或测量真实模型质量；Day 98 正式发布、Day 101 视频与此前待办继续保留。

<a id="day100-talk"></a>

### 一分钟项目架构讲解

> 我做的是一个用于学习和演示的企业 AI 平台，包含知识库、工作流、Agent 和评测四部分。
>
> 用户从网页上传文档并检索原文。前端由 Nginx 提供，同源请求代理到 FastAPI。文档解析后被切分并转换为向量，原文和向量保存在 Chroma，文档状态与业务记录保存在 SQLite。需要生成回答时，再通过独立 API 把检索片段交给模型。
>
> 工作流由 n8n 和独立部署的 Dify 编排。销售 Agent 运行在宿主机 CLI，通过 MCP 调用固定只读查询，生成简报后进入人工确认，批准后进行本地模拟发送。
>
> 评测中心用固定用例执行这条 Agent 路径，保存证据并按独立规则评分，帮助比较后续改动。当前网页没有接入 Agent，真实模型评测和生产身份认证也是后续工作。

下一步 Day 101 可直接把两张图用作 Demo 的开场和流程说明；录制时间由维护者安排。
