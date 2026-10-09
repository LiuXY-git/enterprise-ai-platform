# Week 15：作品集打造

学习路线：Day 99–105。当前完成 Day 99；本周其他任务仍为计划。

本周把已实现的功能整理成别人能够快速理解、运行和追问的作品集。每日实施记录集中在本页，结果见 [Week 15 摘要](evidence/week-15.md)。

[总目录](README.md#按周阅读) · [上一周](week-14.md)

## 本周目录

- [计划与进度](#plan)
- [Day 99：GitHub README 与功能展示](#day99)
- [截图来源与复刻](#day99-screenshots)
- [验证范围与后续](#day99-validation)

<a id="plan"></a>

## 计划与进度

| 日期 | 路线要求 | 当前状态 |
| --- | --- | --- |
| Day 99 | 整理 GitHub，README 包含项目介绍、技术架构、功能截图和部署方式 | 已完成本地修改与验证 |
| Day 100 | 制作系统架构图 | 待开始；现有 README 图提供实际拓扑概览 |
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
