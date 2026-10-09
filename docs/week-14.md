# Week 14：企业生产化优化

学习路线：Day 92–98。

按学习路线归档，计划、实施记录与阶段总结集中在本页。记录中的版本、验收结果和“当前”均对应各节写作时点；后续修订会单独注明。

目前完成 Day 92–97；Day 98 发布仍为计划。Compose 部署、环境变量管理与日志排障的操作步骤见本页。

[总目录](README.md#按周阅读) · [上一周](week-13.md)

<a id="contents"></a>

## 本周目录

- [本周计划与进度](#plan)
- [Day 92：后端代码重构与目录整理](#day92)
- [Day 93：Compose 前后端与持久化部署](#day93)
- [Day 94：环境变量管理](#day94)
- [Day 95：日志系统与请求追踪](#day95)
- [Day 96：API 与 Agent 统一测试](#day96)
- [Day 97：当前技术与操作手册](#day97)

---

<a id="plan"></a>

## 本周计划与进度

依据维护者提供的《FDE_16周企业AI平台学习路线_优化版.docx》，Day 92–98 聚焦代码、部署、配置、日志、测试和文档。学习方式为生产化清单与一键环境实践。

| 日期 | 路线要求 | 计划交付与验收方向 |
| --- | --- | --- |
| Day 92 | 代码重构、优化目录结构、删除无用代码 | 拆分后端应用构建职责，保留接口和启动入口；回归与冻结资产检查 |
| Day 93 | Docker Compose：Backend、Database、Vector DB、Frontend | 盘点现有组件，明确部署拓扑和持久化，验证环境启动；新增组件需落实实际接入 |
| Day 94 | 环境变量管理 | 整理配置入口、示例和校验，明确不同环境及密钥管理 |
| Day 95 | 日志系统，理解 ELK 思路，无需实际部署 ELK | 统一必要日志字段与追踪、排障流程，验证日志边界 |
| Day 96 | API 与 Agent 测试 | 整理分环境测试入口与回归范围，保留失败和验收证据 |
| Day 97 | 技术文档 | 更新架构、部署、操作与维护说明，核对文档和实现 |
| Day 98 | Enterprise AI Platform v1.0 发布 | 汇总实际交付，验收后创建版本清单、发布说明与标签 |

每日开始前结合代码状态细化范围；Day 92–97 实施记录见下方，Day 98 仍为计划。平台已有 API `1.0.0` 和历史 `v1.0.0` 标签，Day 98 发布前需核对命名，不能覆盖旧标签。

<a id="plan-当前起点"></a>

### 当前起点

- Evaluation Center v0.1.0 已定版；维护者提供的 GitHub 截图确认标题、标签和 `verification.json` 附件，截图不等于重新下载核验附件。
- 已发布的 Agent/Evaluation 文件按清单冻结。重构公共后端时先检查清单引用，避免改写历史验收依据。
- Day 83 视频延期、真实模型评测未接入、Day 82 真实 Prompt 改善未测量等既有边界继续保留。
- [Day 92 实施与学习记录](#day92)：从应用入口拆分开始，随后逐日推进。

---

<a id="days"></a>

## 每日实施记录

<a id="day92"></a>

<a id="days-day-92后端代码重构与目录整理"></a>

## Day 92：后端代码重构与目录整理


<a id="day92-目标与作用"></a>

<a id="days-目标与作用"></a>

### 目标与作用

将后端入口中的应用构建、启动关闭、API 文档及路由注册分开，便于后续部署、配置和日志工作定位代码。业务处理仍由原有 routers/services 完成。

重构基线为 `a5d7671d3d376d8020d9a9b37489f17ca03f598a`。本次工作沿用现有功能，HTTP 与 OpenAPI 契约保持一致。

<a id="day92-目录和调用关系"></a>

<a id="days-目录和调用关系"></a>

### 目录和调用关系

```text
backend/app/
  main.py               Uvicorn/Docker 导入 app 的稳定入口
  application.py        create_app() 组装一个 FastAPI 应用
  core/
    lifecycle.py        环境加载、日志配置、建表、关闭清理
    metadata.py         API 描述与标签
  routers/
    registry.py         集中维护 10 个 router 的注册顺序
    ...                 原有接口处理
  services/             原有业务服务
  database.py            原有 SQLite 路径及表结构
  settings.py            原有配置读取和校验
```

启动链路：`main:app` → `create_app()` → 文档参数与路由注册 → ASGI lifespan → 加载环境、配置日志、初始化数据库 → 接受请求 → 关闭时清理应用缓存。

`create_app()` 允许测试创建独立应用。不同实例的 `app.state`、依赖覆盖、文档标签互不污染；数据库路径、进程环境和日志仍是现有配置，并未变成每实例独立资源。

删除了无引用的空文件 `backend/app/utils/__init__.py`。没有将历史实验、发布清单或仍使用的 `/chat` 回显示例当作无用代码删除。

<a id="day92-学习与复刻"></a>

<a id="days-学习与复刻"></a>

### 学习与复刻

1. 阅读 [main.py](../backend/app/main.py)，确认入口只负责导出应用。
2. 阅读 [application.py](../backend/app/application.py)，观察应用参数和路由如何组合。
3. 阅读 [lifecycle.py](../backend/app/core/lifecycle.py)，理解为什么数据库初始化放在启动阶段；初始化失败必须阻止服务启动。
4. 阅读 [registry.py](../backend/app/routers/registry.py)，定位新增接口时需要登记的位置。
5. 运行下面的测试，观察完整契约和故障路径如何保护重构。

在仓库根目录执行：

```powershell
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
.\.venv\Scripts\python.exe -B -m pytest tests/test_day92_application.py -q -p no:cacheprovider
.\.venv\Scripts\python.exe -B -m pytest tests -q -p no:cacheprovider
```

这里使用项目已有的后端环境；独立 Agent/Evaluation 实验使用各自环境，不能将所有实验混在一次根目录 pytest 收集中。

本地服务启动命令仍为：

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

<a id="day92-验证结果"></a>

<a id="days-验证结果"></a>

### 验证结果

2026-09-30 离线验证：

- 后端 514 项通过：原有 506 项 + 新增 8 项；无失败、错误或跳过。
- 发布门禁 41 项通过；无失败、错误或跳过。
- 完整 OpenAPI 与基线快照一致，包含 25 个路径；文档、健康和聊天入口保持行为。
- 新测试覆盖工厂无资源启动副作用、实例隔离、生命周期顺序、建表异常、请求异常后的关闭清理、临时 SQLite 重复初始化和 HTTP 行为。
- Evaluation Center 206 个冻结资产及历史 Agent 冻结链完整性检查通过。完整性检查自身执行测试数为零，与上面的 41 项测试分别记录。
- 改动 Python 文件 Ruff 检查及格式检查通过。

证据见 [validation.json](evidence/week-14.md#day92)、[后端 JUnit](evidence/week-14.md#day92)、[发布门禁 JUnit](evidence/week-14.md#day92)、[冻结资产检查](evidence/week-14.md#day92)。测试使用临时数据库；新测试拦截外部 socket 连接，允许 Windows 事件循环所需的本机回环。

存在一条 Chroma 使用已弃用 asyncio API 的依赖警告，本次不升级依赖。未重跑全部历史发布测试、真实模型请求或通知发送；未重建容器。现有数据库、日志路径及 Docker 入口未改动。Week 14 后续事项见 [计划](#plan)。


---

<a id="day93"></a>

## Day 93：Compose 前后端与持久化部署

### 目标与作用

把现有 API、业务数据库、向量库和新前端组成可启动、可检查的本机环境。浏览器可以上传文档并检索来源片段；部署脚本负责构建镜像、等待健康状态和检查反向代理。

四个角色不等于四个独立容器：后端已使用 SQLite 与嵌入式 Chroma，因此两种数据库继续随 API 进程运行，数据持久化到宿主机。前端新增独立 Nginx 容器，原有 n8n 服务继续保留。没有迁移到 PostgreSQL 或 Chroma Server，也不把 Dify 自己的数据库视为本平台的业务库。

### 实际拓扑

~~~text
浏览器 http://127.0.0.1:8080
  └─ frontend（Nginx 静态页面）
       └─ /api/* → api:8000/*（同源反向代理）
            ├─ SQLite：/app/data/enterprise_ai.db
            ├─ Chroma：/app/data/chroma/
            └─ Embedding 缓存：/home/app/.cache/chroma/
n8n：http://127.0.0.1:5678，保留现有工作流和独立命名卷
~~~

| 角色 | 实现与持久化 | 访问方式 |
| --- | --- | --- |
| Frontend | 原生 HTML/CSS/JavaScript，构建时复制到 Nginx；无业务数据卷 | 127.0.0.1:8080 |
| Backend | FastAPI，原 API 与 OpenAPI 契约保持 | 容器间 api:8000；宿主机 127.0.0.1:8000 |
| Database | SQLite，./data → /app/data | API 内部文件访问，不开放数据库端口 |
| Vector DB | Chroma PersistentClient，./data/chroma | API 内部文件访问，不新增 Chroma HTTP 服务 |
| 模型缓存与日志 | ./data/chroma-cache 与 ./logs | bind mount，重建容器后保留 |
| n8n | 原 n8n_data 命名卷 | 127.0.0.1:5678 |

frontend 等待 api 健康后启动。Nginx 使用 Docker 服务名解析，并在 API 地址变化后刷新 DNS；检查脚本有有限重试，持续失败仍会报错。服务端口均只绑定本机回环地址，前端使用非 root 用户、只读根文件系统与临时 /tmp。

前端不接收模型密钥，镜像构建上下文仅为 frontend/，排除测试文件。页面通过 /api 调用已有 /health、/upload 和 /rag/query：上传保存文档信息并建立索引，检索显示来源与片段。首次索引可能需要下载本地 Embedding 模型；页面不调用生成式模型，也不提供 Agent 会话入口。

### 代码入口

- [Compose](../compose.yaml)：三项服务、启动依赖与持久化路径。
- [前端页面](../frontend/public/index.html)、[交互](../frontend/public/app.js)、[Nginx 配置](../frontend/nginx.conf)。
- [启动脚本](../scripts/start.ps1)与[部署检查](../scripts/check-deployment.ps1)。
- [隔离持久化验收](../scripts/verify_persistence.py)：独立镜像、目录和项目，不发布宿主机端口。
- [部署测试](../tests/test_day93_compose.py)、[隔离边界测试](../tests/test_day93_persistence.py)、[浏览器测试](../frontend/tests/browser.cjs)。

### 学习与复刻

在项目根目录操作，先启动 Docker Desktop。已有 .env 可继续使用；首次部署需从 .env.example 复制并设置 N8N_ENCRYPTION_KEY。脚本验证配置时使用 config --quiet，不打印展开后的密钥。

~~~powershell
Set-Location 'C:\Users\Administrator\Desktop\enterprise-ai-platform'

# API + 前端 + n8n
& .\scripts\start.ps1

# 只检查，不重建
& .\scripts\check-deployment.ps1

# API + 前端；不启动或更新 n8n
& .\scripts\start.ps1 -WithoutN8n

# 只更新 API（原入口仍可用）
& .\scripts\start.ps1 -ApiOnly
~~~

-ApiOnly 与 -WithoutN8n 二选一。它们控制启动/检查的服务范围，不停止已有的其他服务；当前完整 Compose 配置仍要求 .env 中存在 n8n 加密键。需要检查已有模型配置格式时，在启动命令追加 -CheckComponents llm,dify，该检查不验证真实网络与凭据。

启动成功后访问 http://127.0.0.1:8080：

1. 确认“后端已连接”。
2. 选择一份非空、少于 10 MB 的 PDF、DOCX 或 MD 测试文档，点击“上传并建立索引”。
3. 等待出现文档编号与片段数，再输入与该文档有关的问题。
4. 查看返回的来源文件与片段原文。向量检索不等于模型已经生成答案。
5. 如上传超时，先检查服务日志与处理状态，不自动重复发送文件。

容器中的数据目录映射到宿主机，普通 start.ps1 不执行 down、删卷或清理数据；不要为了更新镜像删除 data 或执行 down -v。

### 隔离验收与排障

~~~powershell
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'

# 使用假配置、临时 SQLite/Chroma、独立镜像；不更新现有容器
.\.venv\Scripts\python.exe -B scripts/verify_persistence.py --with-frontend

# 后端、脚本与接口契约测试
.\.venv\Scripts\python.exe -B -m pytest tests -q -p no:cacheprovider

# 查看本次部署状态与最近日志
docker compose ps
docker compose logs --tail 80 frontend api
~~~

隔离脚本先运行启动与部署检查，写入一条虚构 workflow 记录及预先给定向量的 Chroma 测试集合，然后强制重建测试容器，再核对 SQLite 记录、向量查询和日志。使用预先给定向量避免下载模型，不能据此声称已验证真实 Embedding 或语义检索质量。脚本结束会移除本次独立容器及镜像，结果保留在 logs/deployment-checks/<随机项目>/result.json；n8n 不纳入这项重建测试。

浏览器测试使用本机 HTTP 测试响应，覆盖表单和界面行为，与实际容器验收分开记录。已有 Node.js、Playwright 和 Chrome 的环境可运行：

~~~powershell
$env:BROWSER_CHANNEL = 'chrome'
# 若 Playwright 未在 Node 搜索路径中，指定本机已安装的模块目录
# $env:PLAYWRIGHT_MODULE = '本机 node_modules\playwright 的绝对路径'
node frontend/tests/browser.cjs
~~~

若没有 Playwright，先在开发工具环境中安装它；生产镜像和页面不需要 Node.js 或 npm。截图与浏览器结果写到 logs/day93-browser/，不包含真实文档。

| 现象 | 检查方向 |
| --- | --- |
| Docker 返回无法启动 | 先恢复 Docker Desktop 的 Engine；脚本测试通过不等于容器已运行 |
| 8080 被占用 | 检查占用进程，调整本机端口后再部署 |
| 页面正常但后端不可达 | 检查 api 健康和前端日志，等待 DNS 刷新后重新检查 |
| 上传/检索一直等待 | 检查向量模型首次下载与缓存、文档格式、API 日志 |
| API 只更新后页面短暂不可达 | Nginx 会重新解析 api；若持续失败，运行部署检查 |

### 验证结果与范围

2026-10-08 验证：

- 后端回归 528 项全部通过，含 Day 93 新增 14 项；无失败、错误或跳过。
- 本机 Chrome 浏览器 9 组交互与布局检查通过，使用 HTTP 测试响应，包含表单请求、空结果、错误恢复、重复提交和不可信文本渲染。
- Compose CLI 配置验证通过；真实构建 API 与前端镜像，容器健康、Nginx 语法、页面资源及反向代理检查通过。
- 隔离容器强制重建后，SQLite 测试记录、Chroma 固定测试向量及应用/工作流日志保留；临时容器和测试镜像已清理。
- 真实容器验收不下载 Embedding 模型，不发送模型请求，不测量检索语义质量；n8n 重建不在本次范围内。
- Ruff 检查通过；保留原 Chroma 依赖的一条 asyncio 弃用警告。

结果归入 [Week 14 运行摘要](evidence/week-14.md#day93)及本周数据包。现有 API、n8n 和业务数据未被验收脚本替换。

### 学习要点

Dockerfile 决定每个镜像装什么、如何启动；Compose 决定多个服务怎样连接、先启动谁、把数据放在哪里。前端通过服务名访问后端，宿主机通过端口访问页面。SQLite 和 Chroma 的文件挂载到宿主机，所以“重新创建容器”和“删除业务数据”是两个不同操作。

本次交付适用于本机学习环境。生产身份认证、HTTPS、多副本共享存储及 Agent HTTP 接入仍未提供。环境文件的选择与检查见 [Day 94](#day94)。

参考：[Compose 启动顺序](https://docs.docker.com/compose/how-tos/startup-order/)、[Nginx 官方镜像](https://hub.docker.com/_/nginx)。

---

<a id="day94"></a>

## Day 94：环境变量管理

### 完成了什么，有什么用

2026-10-08 完成。Day 52 已把模型、Dify、通知等配置集中起来；Day 94 增加环境文件选择、初始化、配置来源检查和私有文件忽略规则。需要换配置时，可以明确指定文件，并检查究竟使用了文件值、终端环境变量还是 Compose 默认值，减少“改了文件却没有生效”的排障时间。

- 新增 [环境管理命令](../scripts/manage_env.py)：初始化文件、检查格式和所选组件，只输出配置状态及来源。
- [本地 API 环境入口](../backend/app/core/environment.py)：用进程变量 `EAP_ENV_FILE` 选择文件；未设置时继续读取根目录 `.env`。
- [启动](../scripts/start.ps1)与[部署检查](../scripts/check-deployment.ps1)增加 `-EnvFile`，所有 Compose 操作使用同一文件。
- 更新 [.env.example](../.env.example)；[.gitignore](../.gitignore) 忽略 `.env` 和 `.env.*`，保留模板。已有 Docker 忽略规则也排除私有环境文件。
- 增加 [环境管理测试](../tests/test_day94_environment.py)，覆盖文件选择、失败处理、脱敏、空值、特殊字符和脚本传参。

### 三个入口的区别

| 使用场景 | 指定方式 | 未指定时 |
| --- | --- | --- |
| 本地 API 启动 | 先设置进程变量 `EAP_ENV_FILE` | 可选读取项目根目录 `.env` |
| Compose 启动与检查 | PowerShell 参数 `-EnvFile` | 要求项目根目录 `.env` 存在 |
| 新环境管理命令 | `--env-file`，并明确 `--target local` 或 `compose` | 检查项目根目录 `.env` |

新入口的相对路径都以项目根目录为基准。明确选择的文件不存在时直接报错，不退回读取默认文件；也不会把两个文件叠加。文件路径不应含密钥。

`EAP_ENV_FILE` 是启动前设置的进程变量，不写进环境文件，也不负责选择 Compose 文件。已有 Day 52 的 `backend.app.check_config` 命令继续使用它自己的 `--env-file` 参数，不读取这个选择器。

### 先检查已有配置

已有部署继续用原来的 `.env`，无需重新初始化。以下命令不启动容器，不连接模型或业务服务：

~~~powershell
Set-Location 'C:\Users\Administrator\Desktop\enterprise-ai-platform'

# 查看格式、配置来源和是否为空；不检查组件凭据是否齐全
.\.venv\Scripts\python.exe -B -m scripts.manage_env check --target local --env-file .env

# 按实际使用的组件检查；不需要配置所有供应商
.\.venv\Scripts\python.exe -B -m scripts.manage_env check --target compose --env-file .env --component llm --component dify --component n8n
~~~

`compose` 检查需要已安装的 Docker Compose CLI，使用实际 Compose 展开结果判断默认值；这一步不启动 Docker 服务或容器。当前完整 Compose 配置要求 `N8N_ENCRYPTION_KEY` 非空，即使仅检查 API 配置也一样。

输出含义：

| 字段或值 | 含义 |
| --- | --- |
| `environment_file_valid` | 文件检查通过；没有请求组件检查 |
| `configuration_valid` | 所选组件的本地配置规则通过 |
| `configuration_invalid` | 格式、Compose 配置或组件规则不满足；进程退出码为 1 |
| `source: process` | 使用本次终端/进程里的变量 |
| `source: env_file` | 使用选中文件里的变量 |
| `source: compose_default` | Compose 补充了值或使用空值回退规则 |
| `source: code_default_or_unset` | 本地入口没有显式值；是否可缺省由组件规则判断 |
| `state: configured / empty / not_set` | 显式值非空 / 为空 / 未显式设置 |

检查结果隐藏密钥、URL 和模型名称，只保留已知变量名、状态及固定错误规则；LLM 供应商显示已知名称或 unsupported。配置有效只表示格式与必填项符合规则，不验证密钥可用性、连通性或 Dify/n8n 内部模型。

### 新环境初始化与选择

只有第一次建立新环境时才初始化；文件存在就报错，不覆盖：

~~~powershell
# 本地 API 的新文件：Dify 地址默认指向 localhost
.\.venv\Scripts\python.exe -B -m scripts.manage_env init --target local --env-file .env.local

# 全新 Compose 环境：为新的 n8n 数据卷生成随机加密键
.\.venv\Scripts\python.exe -B -m scripts.manage_env init --target compose --env-file .env.compose
~~~

初始化允许 `.env` 或 `.env.*` 文件名，拒绝改写 `.env.example`。模板里的外部服务密钥仍为空，需要按实际使用填写。

**已有 n8n 数据卷必须继续使用原 `N8N_ENCRYPTION_KEY`。** 新文件生成的随机键仅适用于新的 n8n 数据卷；已有部署若增加配置文件，应保留原文件里的加密键，否则旧 Credentials 可能无法解密。原文件和密钥应自行妥善备份，不贴进聊天、文档、截图或 Git。

填写本地文件后：

~~~powershell
.\.venv\Scripts\python.exe -B -m scripts.manage_env check --target local --env-file .env.local --component llm
$env:EAP_ENV_FILE = '.env.local'

# 若 Docker API 已占用 8000，使用 8001 避免端口冲突
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8001

# 停止本地 API 后，清除当前终端的选择器；下次启动恢复默认 .env
Remove-Item Env:EAP_ENV_FILE -ErrorAction SilentlyContinue
~~~

填写 Compose 文件并确认数据卷加密键匹配后，按需执行：

~~~powershell
.\.venv\Scripts\python.exe -B -m scripts.manage_env check --target compose --env-file .env.compose --component llm --component n8n

# 仅更新 API；现有前端不会因此被启动
& .\scripts\start.ps1 -EnvFile .env.compose -ApiOnly

# 只检查 API 容器，使用相同环境文件
& .\scripts\check-deployment.ps1 -EnvFile .env.compose -ApiOnly

# 需要启动完整页面与 n8n 时，去掉 -ApiOnly
# & .\scripts\start.ps1 -EnvFile .env.compose
~~~

这些是按需操作命令，本次 Day 94 实施没有执行现有部署的更新。选文件只改变配置来源，**不会自动创建独立测试环境**：Compose 项目、容器名、端口及数据目录仍然相同。本地 API 也继续使用现有数据路径。需要环境隔离时另行设计项目与存储，不把切换文件当作隔离。

### 覆盖顺序、空值和特殊字符

本地 API 的规则为“进程变量 > 所选文件 > 代码默认值”。进程变量即使为空也优先，可能触发组件校验失败。环境文件只在进程启动时加载；改文件后重启 API。一个已加载配置的 Python 进程中不要通过再次加载另一个文件模拟切换环境。

Compose 先用进程变量覆盖文件值，再按 compose.yaml 中的表达式展开。本项目使用 `${NAME:-default}`，所以空值也会触发默认值。例如空 `QWEN_MODEL` 在本地可能校验失败，在 Compose 中则会采用 Compose 声明的默认模型。改文件后需要重新创建相关容器；只运行检查不会更新运行中的容器配置。

本地 API 逐字读取变量值，不把 `${NAME}` 当作引用。Compose 会展开未加引号或双引号中的美元表达式。因此，共用文件中含美元符号的字面值使用单引号：

~~~dotenv
# 演示值，不能作为真实密钥
DASHSCOPE_API_KEY='synthetic-${literal}'
~~~

检查工具会拒绝重复键、未知变量、缺少等号、错误引号以及未用单引号保护的美元值。它在内存里处理 Compose 配置输出的美元转义，不把密钥或 Docker 原始输出打印出来。

新命令的这些严格文件检查需显式执行；`start.ps1` 仍执行 Compose 结构检查，以及按 `-CheckComponents` 选择的容器内组件检查，不自动运行新命令的全部规则。部署检查读取运行中容器的状态，不承诺运行配置已与刚修改的文件一致。

### 排障与密钥管理

| 问题 | 处理方式 |
| --- | --- |
| 改了文件没有生效 | 确认选中了正确文件，查看 source 是否为 process，然后重启对应 API 或重新创建容器 |
| `environment_file_already_exists` | 使用已有文件；初始化命令不覆盖配置 |
| `environment_file_unreadable` | 核对文件是否存在、UTF-8 编码和读取权限 |
| `unknown_variable` / `duplicate_variable` | 根据行号检查拼写或重复定义，不输出该行秘密值 |
| `compose_configuration_invalid` | 检查必填的 n8n 加密键和 Compose 文件结构；避免直接打印展开后的配置 |
| 配置有效但请求失败 | 继续核对实际网络、授权范围及外部服务状态；格式检查无法证明服务可用 |

`.gitignore` 和 `.dockerignore` 防止意外纳入文件，但不会撤回已经提交过的秘密，也不是密钥保险库。环境文件留在本机，设置适当的访问权限并自行备份；生产密钥托管、轮换与审计不在本次实现范围内。前端不读取这些私有文件。

### 验证结果

- 后端及部署脚本 **554 项测试全部通过**，其中新增 Day 94 测试 26 项；无失败、错误或跳过。
- 实际 Compose CLI 与新 Python 进程完成 8 项集成检查，涵盖选文件、不混入默认文件、进程优先、空值、配置脱敏及美元符号。
- 使用一个无端口、无挂载、无网络的临时容器核对 1–3 个连续美元符号，检查后容器已移除。
- Ruff 检查通过。测试使用虚构配置，未读取或覆盖现有私有环境文件，未新增模型请求，也未重启现有 API、n8n 或前端。
- 结果收在 [Week 14 运行摘要](evidence/week-14.md#day94)；原有 Chroma 依赖的一条 asyncio 弃用警告继续保留。

学习要点：配置文件负责提供值，启动入口负责选择文件，组件校验负责判断能否使用。了解这三层，才能解释“文件改了、程序却还用旧值”的原因。日志系统与排障实践见 [Day 95](#day95)。

参考：[Compose 变量插值](https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/)、[环境变量优先级](https://docs.docker.com/compose/how-tos/environment-variables/envvars-precedence/)。

---

<a id="day95"></a>

## Day 95：日志系统与请求追踪

### 完成了什么，有什么用

2026-10-08 完成。每次进入 API 的 HTTP 请求都会生成一个 request_id，并通过响应头 X-Request-ID 返回。应用日志和工作流事件带上同一编号，便于从一次请求找到对应的状态、耗时及业务处理记录。

例如上传文档失败后，可以用响应里的编号查找 `upload_received`、`document_processing_failed` 和 `http_request_failed`，再按异常类型与源码位置定位问题。查询时不需要把文件内容、密钥或异常原文写进应用日志。

本次交付：

- [结构化日志](../backend/app/observability.py)：统一 JSON 字段、固定事件名、安全的文件与控制台写入。
- [请求追踪](../backend/app/core/request_logging.py)：覆盖正常响应、参数错误、404、500、并发、取消和流式响应。
- [应用工厂](../backend/app/application.py)：在 FastAPI 的完整错误处理栈外关联请求，保留原有响应和异常行为。
- [工作流事件](../backend/app/workflow_logging.py)：保留原有业务字段，追加 service、level 和 request_id。
- [隔离验收脚本](../scripts/verify_logging.py)及[测试](../tests/test_day95_observability.py)。
- ELK 的学习与后续接入思路；本次没有安装或运行 Elasticsearch、Logstash、Kibana。

~~~mermaid
flowchart LR
    A["客户端请求"] --> B["API 生成 request_id"]
    B --> C["响应头 X-Request-ID"]
    B --> D["app.log：请求与应用事件"]
    B --> E["workflow-events.jsonl：业务事件"]
    D --> F["按编号关联排障"]
    E --> F
~~~

### 日志放在哪里

| 位置 | 用途 | 保留方式 |
| --- | --- | --- |
| `logs/app.log` | API 请求摘要、应用事件 | 每个文件约 5 MiB，最多 3 个备份 |
| `logs/workflow-events.jsonl` | 工作流开始、重复请求、检查点、完成和 Dify 等业务事件 | 每个文件约 5 MiB，最多 3 个备份 |
| API 控制台 / `docker compose logs api` | 运行时观察；输出与文件日志有重叠 | Compose 沿用 max-size=10m、max-file=3 |
| `logs/logging-checks/day95-<随机编号>/` | 隔离验收的临时数据库、日志和 result.json | 每次新目录，复核后按需自行清理 |

文件轮转沿用已有大小限制，不依赖日期自动删除。多个 Uvicorn 进程不应同时写同一个轮转文件；当前实现适用于项目现有的单进程 API。后续多副本部署应统一采集控制台日志或使用独立文件，再设计集中保留策略。

已有 app.log 中的文本行不会被删除或改写，新日志追加为 JSON；过渡期间可能同时存在两种格式。下面的查看命令会跳过旧文本行。

### 字段怎样理解

以下为字段演示，编号与耗时不是实际运行证据：

~~~json
{
  "schema_version": 1,
  "timestamp": "2026-10-08T09:00:00+00:00",
  "service": "enterprise-ai-platform-api",
  "level": "INFO",
  "logger": "enterprise_ai_platform.http",
  "event": "http_request_completed",
  "request_id": "11111111111111111111111111111111",
  "source": {"module": "request_logging", "line": 79},
  "method": "GET",
  "route": "/health",
  "status_code": 200,
  "duration_ms": 3.2,
  "response_complete": true
}
~~~

| 字段 | 含义 |
| --- | --- |
| timestamp | UTC 时间；显示在本地界面时可转换为北京时间 |
| service / level / logger | 服务、日志级别和代码记录器 |
| event | 固定应用事件名；未登记的消息用 application_log |
| request_id | 单次 HTTP 请求的关联编号；启动或直接调用函数时可为 null |
| route | 路由模板，例如 /workflow-runs/{run_id}，不会写入实际路径参数；未匹配时为 unmatched |
| status_code | 服务端实际发送的响应状态；未发送响应时为 null |
| duration_ms | 使用单调时钟记录 API 处理时间，包括流式处理及同请求后台任务；不是模型耗时或浏览器总耗时 |
| response_complete | 服务端已发送最后一个响应体消息；不证明客户端最终收到 |
| error_type / source | 异常类别及记录日志的代码模块、行号；不记录异常原文或堆栈 |

请求摘要中：正常和重定向为 INFO，4xx 为 WARNING，5xx、异常或未完成响应为 ERROR。后台任务若在响应发送后失败，仍保留已发送的 200，同时记录 `http_request_failed`；不能把已经发出的响应伪改为 500。

三个编号分别解决不同问题：

- `request_id`：本次 HTTP 尝试。重试会产生新编号，不承担身份认证或去重职责。
- `run_id`：业务工作流。一个工作流的多次请求可共用此编号。
- `log_event_id`：原有工作流日志的单条事件编号。

本服务始终生成自己的请求编号，不直接采用客户端传来的 X-Request-ID。关联范围是本 API 内部及同请求触发的工作流记录，不代表已建立跨 Dify、n8n、Agent 进程的分布式链路。

### 无需更新现有服务的复刻方式

在项目根目录、已有后端虚拟环境中执行：

~~~powershell
Set-Location 'C:\Users\Administrator\Desktop\enterprise-ai-platform'
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'

.\.venv\Scripts\python.exe -B scripts/verify_logging.py
~~~

脚本会：

1. 创建独立输出目录和虚构 SQLite 数据，不读取当前 .env。
2. 启动仅绑定 127.0.0.1 随机端口的临时 Uvicorn 服务。
3. 执行 9 个 HTTP 请求，覆盖健康、聊天、422、404、500、后台失败、工作流重复请求和关闭。
4. 核对响应编号与日志编号、耗时、失败状态及敏感测试标记是否遗漏到日志中。
5. 停止临时服务，输出 result.json 的位置；失败时也清理子进程并返回非零退出码。

`/fixture-error`、`/fixture-background`、`/fixture-stop` 只存在于这个临时验收进程，不会注册到生产应用。脚本不修改已有容器，不发送模型请求或通知，也不会启动前端。

### 在自己的 API 上按编号排障

已有容器仍运行旧镜像时，不会自动获得新日志功能。需要启用时按需更新 API；前端继续关闭即可：

~~~powershell
# 与之前部署使用同一个环境文件；自定义文件加 -EnvFile
& .\scripts\start.ps1 -ApiOnly

$response = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/health' -UseBasicParsing
$requestId = [string]$response.Headers['X-Request-ID']
Write-Host "本次请求编号：$requestId"

# 同时检查当前文件和轮转备份；跳过升级前的文本行
Get-ChildItem -LiteralPath '.\logs' -File |
    Where-Object { $_.Name -like 'app.log*' -or $_.Name -like 'workflow-events.jsonl*' } |
    ForEach-Object {
        Get-Content -LiteralPath $_.FullName -Encoding UTF8 | ForEach-Object {
            try {
                $entry = $_ | ConvertFrom-Json -ErrorAction Stop
                if ($entry.request_id -eq $requestId) { $entry }
            } catch { }
        }
    } |
    Select-Object timestamp, level, event, operation, status_code, duration_ms, run_id, error_type, source
~~~

浏览器里可在开发者工具的 Network 面板查看 API 响应头。前端代理正常转发 API 响应时会保留 X-Request-ID；若请求被代理直接拒绝或未到达 API，可能没有编号。

建议按以下顺序定位：

1. 用 request_id 查单次请求，检查状态码与路由。
2. 看同编号的应用事件和 error_type/source，确定失败环节。
3. 对工作流，再按 run_id 查看其他阶段或重复请求。
4. 检查是否响应已发出后后台任务才报错，避免把 HTTP 200 当成所有处理已成功。
5. 若日志出现 `log_sink_failed`，检查日志目录权限、磁盘空间或轮转文件占用。这个固定告警不含原始日志内容；日志写入失败也意味着记录可能不完整。

这些命令用于本地排障，不构成完整审计工具；不要因为筛选结果为空就判断没有发生过请求。

### 哪些内容会记录，哪些不会

应用 JSON 日志仅输出固定事件及必要元数据。文件名、动态日志参数、请求正文、查询字符串、Authorization/Cookie、异常原文和异常堆栈不进入这一日志流。原始消息不再作为可自由拼接的 message 输出；新增事件需在 `observability.EVENTS` 中登记固定模板，定位错误使用 error_type/source。

应用启动完成后，用新请求摘要替代 Uvicorn 原始访问日志，避免 URL 查询参数重复输出；HTTPX/HTTPCore 默认请求日志关闭，Uvicorn 异常日志改用同样的安全格式。启动配置之前的服务消息以及其他第三方、Nginx、n8n 日志不承诺使用这个格式。

**原有 workflow-events.jsonl 仍保留 Day 51 的有限输入输出快照和脱敏规则，可能包含业务内容。** 新增 request_id 不会使这些记录自动变成可公开数据。集中采集前应明确授权、字段删减、访问权限和保留期；不要把整个日志目录直接公开。

### ELK 在这里能发挥什么作用

| 组件 | 职责 | 对应本项目的作用 |
| --- | --- | --- |
| Logstash | 接收、解析和转换日志，再输出到目标 | 把各服务的日志整理为可检索字段 |
| Elasticsearch | 存储、搜索与聚合 | 按 request_id、路由、错误类型或时间范围查询 |
| Kibana | 查询界面与可视化 | 查看错误分布、慢请求及趋势 |

以后可让采集器读取 JSON 日志，经 Logstash 处理后写入 Elasticsearch，再由 Kibana 查询。Logstash 的处理管线分为输入、过滤和输出阶段；本次只把应用日志准备为易于解析的 JSON，不提供采集管线或仪表板。[官方处理流程](https://www.elastic.co/docs/reference/logstash/how-logstash-works)、[Elastic Stack 组件说明](https://www.elastic.co/elastic-stack)。

采集时文件与控制台应选定一个主要来源，避免把同一请求重复计算；耗时统计也应只选择 HTTP 摘要事件，不能把工作流事件混作第二次 HTTP 请求。错误率与告警阈值需要明确统计口径，Day 95 没有声称已经部署监控告警系统。

### 验证结果与学习顺序

- 后端回归 **580 项全部通过**，含 Day 95 新增 26 项；无失败、错误或跳过。原有接口与 OpenAPI 契约测试通过。
- 真实临时 Uvicorn 服务完成 **9 个 HTTP 请求、2 条工作流事件、8 项集成检查**；验证普通错误、未处理异常、后台错误、关联编号及敏感测试标记保护。
- Ruff 检查通过；保留 Chroma 依赖已有的一条 asyncio 弃用警告。
- 临时服务已停止，已有 API/n8n 容器及数据未修改，前端保持关闭。本次不部署 ELK、不新增模型请求或通知发送。
- 结果归入 [Week 14 运行摘要](evidence/week-14.md#day95)。

学习时先运行隔离脚本，打开 result.json 和同目录 app.log，对照响应与记录字段；理解单次请求如何关联后，再阅读请求中间件及 JSON 格式化代码。后续 Day 96 继续整理 API 与 Agent 测试入口和回归范围。


<a id="day96"></a>

## Day 96：API 与 Agent 统一测试

### 今天解决什么问题

之前已经积累了接口、Agent 和评测测试，但运行命令散落在不同目录，依赖也不属于同一个 Python 环境。修改公共模块后容易只跑到一部分，或把“没有收集到测试”“跳过依赖检查”误当作通过。

现在使用 [统一测试脚本](../scripts/test_platform.py)，按明确范围选择已有环境，运行当前工作区代码，并留下可复核的结果。它也包含 [入口自身的失败控制测试](../tests/test_day96_test_runner.py)。例如修改人工确认逻辑后，先跑 workflow；准备合并前再跑 all，检查接口和其他 Agent 能力是否退化。

### 五组测试和各自的环境

| suite | 默认 Python 环境 | 覆盖范围 |
| --- | --- | --- |
| api | 根目录 .venv | tests/：FastAPI、OpenAPI 契约、配置、SQLite、RAG、工作流、通知、部署脚本模拟、日志及统一测试入口 |
| planner | experiments/day60/.venv | Day 58–60：LangGraph 分支、计划校验、SQLite 检查点与独立进程恢复 |
| agent | experiments/day73/.venv | Day 64 工具调用、Day 65 只读 SQL 核心、Day 72–73 本地 MCP、Day 75 会话记忆 |
| workflow | experiments/day73/.venv | Day 78–82：任务日志、重试和恢复、人工确认、销售场景与 Prompt 候选控制 |
| evaluation | experiments/day73/.venv | Day 85–90：测试集契约、执行、耗时、usage、规则评分与报告复核 |

`all` 表示上表五组，不表示收集仓库内所有实验。Day 61–62、旧版 SQL Agent、Day 66–69 的知识/天气/多工具实验及各正式版本的发布专用测试不在本入口内。变更这些模块时，仍按对应 Week 的说明补跑其专用测试。CLI 的 list 会输出精确文件路径；API 组收集 tests/，其他组使用显式文件清单，避免重复计数和跨环境混装。

API 中异步用例需要 AnyIO 插件，脚本显式加载它；其他自动发现插件关闭，不继承 PYTEST_ADDOPTS 等外部筛选参数。Windows 部署脚本测试需要 PowerShell；缺少它导致 skip 时，本次回归会判为未通过。

### 直接复刻

在项目根目录使用已有环境：

~~~powershell
Set-Location 'C:\Users\Administrator\Desktop\enterprise-ai-platform'
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'

# 查看范围、Python 路径和解释器文件是否存在，不运行测试
.\.venv\Scripts\python.exe -B scripts/test_platform.py list

# 日常修改后选择相关组；可重复写 --suite 选择多个不同组
.\.venv\Scripts\python.exe -B scripts/test_platform.py run --suite api
.\.venv\Scripts\python.exe -B scripts/test_platform.py run --suite agent --suite workflow

# 合并前运行五组回归；省略 --suite 也会运行这五组
.\.venv\Scripts\python.exe -B scripts/test_platform.py run --suite all
if ($LASTEXITCODE -ne 0) { throw '测试未全部通过，请查看本次 summary.json 和日志' }
~~~

每次自动创建 `logs/test-runs/<UTC时间>-<随机编号>/`，最后一行显示该目录。也可指定一个**尚不存在**的输出目录。仓库内的输出限于 logs/test-runs/ 下，避免把测试产物再次当作源码收集；也可指定仓库外的新目录：

~~~powershell
$runDir = Join-Path 'logs/test-runs' ('check-' + [guid]::NewGuid().ToString('N'))
.\.venv\Scripts\python.exe -B scripts/test_platform.py run --suite workflow --output-dir $runDir
$testExit = $LASTEXITCODE
Get-Content (Join-Path $runDir 'summary.json') -Raw -Encoding UTF8
if ($testExit -ne 0) { throw 'Workflow 回归未通过；失败记录已保留' }
~~~

可用 `--api-python`、`--planner-python`、`--runtime-python` 指定其他已安装的解释器，路径有空格时加引号。`list` 的 available 只代表文件存在，不证明依赖齐全；缺失模块会在对应组日志中报错。脚本不自动安装依赖。重新建立环境时，API 参考 requirements-dev.txt，规划器参考 experiments/day60/requirements-lock.txt，Agent/MCP 参考 experiments/day73/requirements-lock.txt，分别安装，避免混装。

每组默认最多运行 900 秒，可用 `--timeout 1200` 调整。超时或 Ctrl+C 时尝试停止本次启动的测试进程树；无法确认清理完成会明确报告，并停止启动后续组。普通测试失败仍继续其他已选组，让一次运行保留完整的回归范围结果。

### 报告怎样看

| 文件 | 用途 |
| --- | --- |
| summary.json | 整次状态、各组状态、统计、耗时、解释器、失败原因、未通过测试编号与源码清单哈希 |
| api/、planner/、agent/、workflow/、evaluation/ 下的 tests.xml | JUnit 格式结果，保留失败断言及错误详情，可供后续 CI 使用 |
| 同目录 stdout.log / stderr.log | 对应测试进程的完整标准输出和错误输出 |
| 同目录 inventory.json | 收集与实际执行的测试编号、Python/pytest 版本和退出码 |
| 同目录 source-manifest.json | 被测源码、配置和 fixture 文件的内容哈希，用于区分测试针对哪个工作区版本 |
| 同目录 temp/ | pytest 的隔离临时数据库和子进程测试材料，便于失败后排查 |

源码清单不是版本签名或依赖锁定替代品；目录、依赖和测试范围都有各自边界。运行期间请勿同时修改代码，每组会从当前工作区另建临时副本。

只有全部已选组同时满足下列条件，整体才返回退出码 0：

1. pytest 返回 0，JUnit 结构和统计一致。
2. 至少执行一项测试，无 failure、error 或 skip。
3. 收集编号与执行编号一致，数量与 JUnit 一致，没有重复测试编号。
4. 所有选中组均已执行，没有超时、运行中断、缺失报告或环境错误。

`failed` 是本次未通过；`not_run` 表示组尚未执行，不能当成 0 项通过。`observed_counts` 仅汇总实际取得且可解析的 JUnit 数据；若报告缺失，数字并不代表本次完整覆盖。优先查看整体 status，再查看各组 problems 和测试日志。修复后新建目录重跑，原失败证据保留，脚本不会覆盖旧结果。

### 隔离和结果边界

测试在当前代码的临时副本中执行，包括未提交修改；不复制仓库 .env、私有 .env.*、已有 data/、logs/ 或虚拟环境。根测试配置会保留，外部业务凭据和测试筛选参数不传给测试进程。默认依赖现有用例的 mock/fixture 和本地 stdio MCP，无需启动前端或业务容器，也不会更新现有部署。

这里的隔离不是操作系统网络沙箱。未来新增测试仍需保持离线约束，不能直接把真实外部服务调用放进这些组。JUnit、日志及 temp/ 可能包含测试输入和断言；使用业务样例时先判断是否适合分享，完整运行目录不自动提交 Git。确认不需要排查后可按目录清理，汇总材料继续按 Week 保存。

**代码回归通过与 Agent 业务效果是两层结论。** 例如拒绝审批是正确行为，相关测试通过；它不代表消息已经发送。此入口也不替代浏览器交互、真实 Docker 重建、真实模型质量或生产验收。

需要重新执行 12 个固定销售场景并生成评分时，继续使用 [Evaluation Center 的运行入口](../evaluation-center/README.md#运行评测)。它回答“这些固定案例是否符合预期”；本入口回答“当前实现是否通过所选自动化回归”。本次不新增真实模型调用，不改变既有演示视频与真实质量评测待办。

### 本次验证

- 五组共 **1,574 项独立测试通过**：API 618、规划器 86、工具与记忆 369、销售流程 259、评测框架 242；无失败、错误或跳过。
- 其中 Day 96 新增 **38 项入口控制测试**，包含真实 pytest 失败/跳过子进程和真实超时清理；这些刻意制造的失败按预期被识别，未被算成业务成功。
- Ruff 检查通过，保留 Chroma 依赖已有的一条 asyncio 弃用警告。
- 所有测试使用临时源码副本和虚构输入；没有更新业务容器或启动前端。

学习顺序：先执行 list 理解分组，再跑 api 并查看 summary.json；修改 Agent 时选择对应组，最后用 all 检查是否影响其他模块。结果摘要见 [Week 14 测试记录](evidence/week-14.md#day96)。Day 97 继续整理技术文档。


<a id="day97"></a>

## Day 97：当前技术与操作手册

本节按 **2026-10-09、Day 96 已合并代码**整理，作为当前操作入口。Day 97 更新说明与导航，不改变 API、数据库结构或部署状态。早期 Week 章节继续记录当时的设计与复刻过程，日常操作从本节开始。

[架构](#day97-architecture) · [准备与启动](#day97-setup) · [API 与页面](#day97-api) · [维护与排障](#day97-operations) · [测试与评测](#day97-testing) · [交付边界](#day97-boundaries)

<a id="day97-architecture"></a>

### 1. 当前架构与代码位置

~~~mermaid
flowchart LR
    Browser[浏览器 8080] --> Frontend[frontend: Nginx + 静态页面]
    Frontend -->|/api/ 去掉前缀| API[api: FastAPI 8000]
    Operator[本机 API 文档 8000] --> API
    N8N[n8n 5678] -->|HTTP 工作流| API
    API --> DB[(data/enterprise_ai.db)]
    API --> Vector[(data/chroma)]
    API -->|RAG 生成| LLM[API 配置的生成模型]
    API -->|工作流请求| Dify[独立 Dify]
    Dify -->|外部知识库 /retrieval| API
    API --> Log[logs/ 请求与工作流记录]
    subgraph HostCLI[宿主机 CLI：独立于 Compose API]
        Planner[规划与进度实验]
        Memory[会话记忆实验]
        Agent[固定销售任务与本地审批] --> MCP[stdio MCP 子进程]
        MCP --> Sales[(虚构销售 SQLite)]
        Eval[固定场景评测] --> Agent
    end
~~~

Compose 中只有 **frontend、api、n8n 三个服务**。SQLite 和 Chroma 嵌入 API 进程并写本机挂载目录，没有独立 Database/Vector DB 容器。Dify 的部署与数据不归本项目 Compose 管理。Agent/MCP/评测使用宿主机独立 Python 环境，当前没有 Agent HTTP API，也没有与网页自动串联；图中的规划、记忆仍是独立实验。

| 位置 | 维护职责 |
| --- | --- |
| [main.py](../backend/app/main.py) → [application.py](../backend/app/application.py) | 保持 Uvicorn 入口、创建 FastAPI 和注册路由 |
| [core/lifecycle.py](../backend/app/core/lifecycle.py) | 启动时加载环境、配置日志、建表；关闭清理进程内缓存 |
| [routers](../backend/app/routers)、[models](../backend/app/models)、[services](../backend/app/services) | HTTP 输入/输出、业务处理、数据及外部服务适配 |
| [frontend/public](../frontend/public)、[nginx.conf](../frontend/nginx.conf) | 静态 UI、相对地址 /api 请求、反向代理 |
| [n8n/templates](../n8n/templates/README.md) | 客服、邮件和销售流程的导入、Credentials 与实例绑定说明 |
| [experiments](../experiments)、[Agent Center](../agent-center/README.md) | 各独立 CLI 的实现、版本入口与能力限制 |
| [Evaluation Center](../evaluation-center/README.md#运行评测) | 固定测试集、执行、计时、usage 和规则判分 |
| [scripts](../scripts)、[tests](../tests/README.md) | 环境/部署/日志验收/回归工具与对应测试 |

`create_app()` 仅构造应用；真正启动需执行 lifespan。改变环境文件后重启相应进程，不能依赖已导入模块自动重新加载。部署镜像只包含 backend 和运行依赖，不包含宿主机的 Agent 实验、测试环境或私有环境文件。

<a id="day97-setup"></a>

### 2. 准备、配置与启动

#### 首次准备

现有开发环境可跳过安装。新机器准备 Git、PowerShell、Python 3.14；容器运行使用 Docker Desktop 的 Linux 容器模式，部署脚本要求 Compose >= 2.20.0。前端是静态文件，无需 npm 构建。当前 API 环境验证使用 Python 3.14.2，不把该结果推广到未测试的 Python 版本。

以下命令在项目根目录执行，只为 API 建立环境；规划器与 MCP 的环境准备见 [Day 96](#day96)，不要混装它们的依赖。

~~~powershell
Set-Location 'C:\Users\Administrator\Desktop\enterprise-ai-platform'
py -3.14 -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'API 虚拟环境创建失败' }
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) { throw 'API 依赖安装失败' }
~~~

**下面的 Compose 配置初始化仅用于没有旧 n8n 数据卷的新实例。** 它会生成新的 n8n 加密键。已有部署应继续选择原文件，或迁移时保留原 N8N_ENCRYPTION_KEY，不能为旧卷换成随机新键。

~~~powershell
.\.venv\Scripts\python.exe -B -m scripts.manage_env init --target compose --env-file .env
if ($LASTEXITCODE -ne 0) { throw '初始化未完成；已有文件不会被覆盖' }
~~~

环境管理统一使用 `python -m scripts.manage_env` 从仓库根目录运行，避免依赖额外的 PYTHONPATH。按用途编辑私有文件，变量名参考 [.env.example](../.env.example)。配置初始化只创建模板，并不配置模型、Dify 或通知密钥。细节见 [Day 94](#day94)。

| 功能 | 配置归属 |
| --- | --- |
| API 生成回答 | 私有环境文件中的 LLM_PROVIDER 与对应 DeepSeek/Qwen 变量 |
| API 调 Dify 工作流 | DIFY_API_BASE_URL、DIFY_WORKFLOW_API_KEY；Dify 应用需另行发布 |
| Dify 回查 API 知识库 | DIFY_EXTERNAL_KNOWLEDGE_API_KEY 与知识库 ID；与工作流应用 Key 不同 |
| n8n 自身模型节点 | n8n Credentials 与节点参数；不会自动采用 API 的模型 Key |
| n8n 原有 Credentials 解密 | 原 N8N_ENCRYPTION_KEY 必须与该数据卷匹配 |
| 独立 Agent live 实验 | 使用该 CLI 明确支持的参数和配置；不从网页触发 |

#### 已有配置：检查后选择启动范围

~~~powershell
$platformEnv = '.env'  # 若先前部署使用其他文件，改为那个文件
.\.venv\Scripts\python.exe -B -m scripts.manage_env check --target compose --env-file $platformEnv --component n8n
if ($LASTEXITCODE -ne 0) { throw '配置检查未通过，先查看固定错误代码' }
~~~

只检查配置格式不证明密钥有效、外部网络或模型可用。进程变量会优先于文件；不要贴出完整 `docker compose config` 展开的环境值。需要核对来源时使用上面的脱敏检查。

| 目的 | 启动/更新 | 检查同一范围 |
| --- | --- | --- |
| 只更新 API | `& .\scripts\start.ps1 -EnvFile $platformEnv -ApiOnly` | `& .\scripts\check-deployment.ps1 -EnvFile $platformEnv -ApiOnly` |
| API + 前端 | `& .\scripts\start.ps1 -EnvFile $platformEnv -WithoutN8n` | `& .\scripts\check-deployment.ps1 -EnvFile $platformEnv -WithoutN8n` |
| 三个服务 | `& .\scripts\start.ps1 -EnvFile $platformEnv` | `& .\scripts\check-deployment.ps1 -EnvFile $platformEnv` |

每次选择一行执行。ApiOnly 与 WithoutN8n 不能同时使用；未选择的服务保留现状，并不会被自动停止。即使 ApiOnly，当前脚本仍验证完整 Compose 文件，因此选中文件仍须有有效的 N8N_ENCRYPTION_KEY。

脚本先构建，再更新选中的容器，等待健康并核对 API、SQLite、日志和挂载；选择前端时还检查页面资源与 /api/health 代理。可增加 `-CheckComponents llm,dify` 检查相关配置；只有 start.ps1 支持 `-WaitTimeoutSeconds`。构建失败会停止后续动作，更新后检查失败也会报错，**没有自动回滚保证**。

| 访问方 | 地址 | 含义 |
| --- | --- | --- |
| 本机浏览器 | http://127.0.0.1:8080/ | 知识库上传与片段检索 |
| 本机调用者 | http://127.0.0.1:8000/docs、/openapi.json | Swagger UI 与实际运行服务的规格 |
| 本机维护者 | http://127.0.0.1:5678/ | n8n 编辑器 |
| 前端/n8n 容器 | http://api:8000 | Compose 网络中的 API 服务名 |
| API → 独立 Dify | DIFY_API_BASE_URL | Docker Desktop 默认 host.docker.internal/v1，按实际端口调整 |

所有宿主机端口只绑定 127.0.0.1。容器中的 localhost 指向容器本身，不能把本机开发地址直接当作另一个服务地址。

查看状态、仅关闭前端或停止全部服务：

~~~powershell
docker compose --env-file $platformEnv ps
docker compose --env-file $platformEnv stop frontend
~~~

确实需要停止全部服务时，另行执行 `docker compose --env-file $platformEnv stop`。

这些命令不删除数据。修改自定义环境文件后，使用带同一 EnvFile 的 start.ps1 更新容器；单独 restart 不会重新应用 Compose 环境配置。

#### 本地 API 开发

为宿主机生成独立文件（已有文件不要重新初始化），再显式选择它：

~~~powershell
.\.venv\Scripts\python.exe -B -m scripts.manage_env init --target local --env-file .env.local
if ($LASTEXITCODE -ne 0) { throw '请检查文件是否已存在，保留已有配置' }
$env:EAP_ENV_FILE = '.env.local'
.\.venv\Scripts\python.exe -B -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8001 --reload
~~~

本地文档地址为 http://127.0.0.1:8001/docs。Compose 前端仍连接其 api 容器的 8000，不会自动改连这个开发进程。EAP_ENV_FILE 只选择 API 启动时读取的文件；它不等同于 Compose 的 --env-file，也不替代独立检查命令的 --env-file。路径规则与变量优先级见 [Day 94](#day94)。

<a id="day97-api"></a>

### 3. 页面、接口与外部影响

当前 OpenAPI 有 **25 个路径、26 个操作**，完整字段和错误响应见 [API 参考](week-4.md#api)和运行服务的 /docs。若旧镜像尚未更新，网页规格描述的是旧镜像；不能因本地 Git 已更新就认为部署也更新了。

| 入口 | 执行内容 | 操作前应了解 |
| --- | --- | --- |
| GET /health | 返回 API 运行状态 | 不验证外部模型、Dify、知识质量或通知通道 |
| POST /chat | 回显基础消息 | 不是大模型问答 |
| POST /upload | 解析、保存元数据、切片、Embedding、写入 Chroma | 修改知识库；首次 Embedding 可能下载本地模型；上传重试可能形成新记录 |
| POST /rag/query | 检索片段、来源与距离 | 使用本地 Embedding；不会调用生成模型 |
| POST /rag/answer | 检索后生成带来源回答 | 需要 API 生成模型配置，可能产生供应商用量 |
| POST /retrieval | 提供 Dify 外部知识库检索 | 专用 Bearer Key；与 API 调用 Dify 的凭据方向相反 |
| POST /dify/workflow | 调用已发布 Dify 工作流 | Dify 的模型、节点和费用由其应用配置决定 |
| /workflow-runs、/crm 下的操作 | 运行状态、检查点、恢复信息、模拟 CRM 与通知状态 | 部分操作写库；保存通知结果不等于已经发送消息 |
| POST /integrations/feishu/messages、/integrations/wecom/messages | 独立通知发送 | 配置齐全时可能真实发送，不用它们作健康探针 |

前端实际只调用 /health、/upload、/rag/query，展示检索片段，不含生成回答、审批或评测面板。页面接受非空 PDF、DOCX、MD，文件小于 10 MiB；代理限制整个请求体为 10 MiB，临近上限还需为 multipart 包装留出空间。API 还支持 .markdown；直接访问 8000 会绕过前端/代理的体积限制，不能据此认为 API 已实现同样的上传配额。

安全的运行状态检查示例（先确认选定服务已启动）：

~~~powershell
$response = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/health' -UseBasicParsing
$response.Content
$response.Headers['X-Request-ID']
~~~

接口尚无完整的调用方身份认证，/retrieval 的专用 Key 也不构成全平台鉴权。当前绑定本机；对外开放前需要另行设计认证、授权、传输保护与访问限制。本节不宣称完成生产安全部署。

<a id="day97-operations"></a>

### 4. 数据、日志与日常维护

| 位置 | 内容与保留建议 |
| --- | --- |
| data/enterprise_ai.db | 文档元数据、工作流运行、模拟 CRM；业务恢复需要保留 |
| data/chroma/ | 向量与文档片段，容器挂载 /app/data；与元数据配套备份 |
| data/chroma-cache/ | Compose API 的 Embedding 缓存；删除可能触发重新下载，不代替向量索引 |
| n8n_data 命名卷 | n8n 工作流、执行与 Credentials 数据；同时保留对应加密键 |
| 私有 .env 或选定环境文件 | 实例配置与密钥；单独安全备份，不提交 Git |
| logs/app.log、workflow-events.jsonl | API 排障和工作流记录；有轮转，工作流快照可能含业务内容 |
| data/ 下的 Agent SQLite 和评测输出 | 是否可删取决于是否还需恢复审批、会话或复核评测；不能按日期目录一概删除 |
| logs/test-runs/ | 每次独立测试的报告与临时材料；复核后可按运行目录清理 |

本地 API 的模型缓存由其 Embedding 库和用户缓存目录管理，不能假定与 Docker 的 data/chroma-cache 相同。上传接口不建立原文件档案，应自行保留原始资料。只保存 Git 不会备份业务数据库、n8n Credentials 或运行记录。

需要备份或回滚时：先停止会写数据的 API/工作流/本地进程；在同一静止时点保存 SQLite、Chroma、n8n 卷、对应配置与原始资料，并记录代码提交和镜像 ID；在独立目录、卷与端口上验证恢复后再考虑替换现有实例。Dify 的存储另行处理。当前没有自动备份、迁移或回滚工具，文档步骤不表示已完成一次真实恢复演练。

镜像标签 enterprise-ai-platform:1.0.0 会被后续构建复用；仅记录这个标签不足以确定旧镜像内容。回退 Git 或镜像也不会自动回退数据库/向量状态，不能把 `docker compose down -v` 当作日常修复命令。

#### 根据症状排查

| 现象 | 检查顺序 |
| --- | --- |
| 前端打不开 | ps 确认 frontend 是否运行、访问 8080；ApiOnly 不会自动启动它 |
| 页面可打开但 API 不通 | 检查 API 健康、frontend /api/health 代理及 DNS；核对是否在看 8001 的本地开发进程 |
| 配置来源不符合预期 | 使用 manage_env check；检查选中文件与进程变量覆盖，不打印密钥 |
| 上传慢或 413 | 核对文件和代理请求体限制、首次模型下载、缓存及日志；超时后不要立即重复提交 |
| 检索结果为空 | 确认上传返回 indexed、使用同一数据库/索引、检查查询条件；换模型 Key 不会自动重建索引 |
| API 4xx/5xx 或后台失败 | 记录响应 X-Request-ID，按 [Day 95](#day95) 查 app.log；再按 run_id 关联工作流 |
| 模型或 Dify 失败 | 分别核对 API 和外部实例配置；configuration_valid 不证明外部调用成功 |
| 容器重建后找不到数据 | 核对项目目录、bind mounts、n8n 卷及环境文件，不急于重新初始化 |
| Agent pending 或通知 unknown | 按该 CLI 的审批/核对流程处理；不要把等待或不确定状态改成已发送 |

日志优先使用请求编号、固定事件、error_type 和 source 定位。应用摘要不保留任意异常原文；原有工作流输入输出快照仍可能包含业务信息。当前没有 ELK 部署，单进程文件轮转不应直接推广为多副本日志方案。

<a id="day97-testing"></a>

### 5. 修改后怎样验证

| 验证目标 | 使用入口 | 结果解释 |
| --- | --- | --- |
| API 或 Agent 代码回归 | scripts/test_platform.py list / run | 五组范围与指定环境见 [Day 96](#day96)，失败/跳过/缺失报告不会通过 |
| 固定销售案例的行为、耗时与评分 | scripts/evaluate.py run / inspect | [Evaluation Center](../evaluation-center/README.md#运行评测) 的 12 例 fixture，不等于真实模型质量 |
| 隔离 HTTP 日志流程 | scripts/verify_logging.py | 临时回环服务与虚构输入；[Day 95](#day95) |
| Compose 和持久化 | start.ps1 / check-deployment.ps1，必要时独立重建验收 | 检查范围按服务选择；操作步骤见 [Day 93](#day93) |
| 前端交互 | frontend/tests/browser.cjs | 使用该阶段浏览器环境与流程；[Day 93](#day93) |

统一回归：

~~~powershell
.\.venv\Scripts\python.exe -B scripts/test_platform.py run --suite all
if ($LASTEXITCODE -ne 0) { throw '所选回归未全部通过，请查看本次报告' }
~~~

若需要重新跑固定业务场景，输出使用新目录，并在运行失败时停止：

~~~powershell
$evaluationOutput = Join-Path 'data/evaluation' ('run-' + [guid]::NewGuid().ToString('N'))
.\experiments\day73\.venv\Scripts\python.exe -B scripts/evaluate.py run --suite full --output-dir $evaluationOutput
if ($LASTEXITCODE -ne 0) { throw '固定场景运行未通过，先检查保留的结果' }
.\experiments\day73\.venv\Scripts\python.exe -B scripts/evaluate.py inspect --input-dir (Join-Path $evaluationOutput 'run') --report (Join-Path $evaluationOutput 'evaluation/report.json')
if ($LASTEXITCODE -ne 0) { throw '评测报告复核未通过' }
~~~

评测 fixture 的 Token 保留未知，显式成本估算不等于供应商账单。不要把测试状态 passed、业务状态 completed、审批状态 approved 与真实发送成功混为同一个结论。

<a id="day97-boundaries"></a>

### 6. 后续交付边界

Day 98 仍需整理版本范围、选择新标签名并执行对应验收。平台已有 v1.0.0 和各组件独立标签，不覆盖旧标签。当前 API 元数据仍为 1.0.0，文档更新不会升级已运行容器。

Day 55/83 视频、Workflow Center v1.0 正式标签与 Release、企业微信真实发送、Day 82 真实 Prompt 质量测量继续作为待办。没有通用 Agent 目标执行、跨会话长期画像、真实模型评测入口或生产身份认证；本地审批只产生模拟发送记录。

<a id="day97-verification"></a>

### 7. 本次文档核对

- API 清单逐项对齐：25 个路径、26 个 HTTP 操作；本次没有调用业务接口。
- 16 项文档与实现核对通过，包括 Compose 服务/端口/挂载、前端实际 API 范围、命令帮助和隔离环境初始化/检查。
- 16 个当前入口的 PowerShell 代码块语法通过，部署开关与实际脚本参数一致；没有执行部署或停止服务。
- 503 处本地链接通过（修改文档中的 450 处、其他文档指向这些文件的 53 处），README 原章节锚点保留。
- 既有文档索引契约测试 1 项通过。业务代码、测试与部署脚本保持不变，本次未重新跑 Day 96 全部回归，也未启动前端或更新现有服务。

学习时先按架构图分清网页/API、n8n/Dify 与宿主机 CLI，再选一个入口执行其检查命令。维护时以实现文件和当前服务规格确认事实，运行摘要见 [Week 14 结果](evidence/week-14.md#day97)。
