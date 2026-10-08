# Week 14：企业生产化优化

学习路线：Day 92–98。

按学习路线归档，计划、实施记录与阶段总结集中在本页。记录中的版本、验收结果和“当前”均对应各节写作时点；后续修订会单独注明。

目前完成 Day 92–93；Day 94–98 仍为计划。Day 93 的部署步骤与验证结果见本页。

[总目录](README.md#按周阅读) · [上一周](week-13.md)

<a id="contents"></a>

## 本周目录

- [本周计划与进度](#plan)
- [Day 92：后端代码重构与目录整理](#day92)
- [Day 93：Compose 前后端与持久化部署](#day93)

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

每日开始前结合代码状态细化范围；Day 93 实施记录见下方，Day 94–98 仍为计划。平台已有 API `1.0.0` 和历史 `v1.0.0` 标签，Day 98 发布前需核对命名，不能覆盖旧标签。

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

本次交付适用于本机学习环境。生产身份认证、HTTPS、多副本共享存储及 Agent HTTP 接入仍未提供。后续 Day 94 继续处理环境变量管理。

参考：[Compose 启动顺序](https://docs.docker.com/compose/how-tos/startup-order/)、[Nginx 官方镜像](https://hub.docker.com/_/nginx)。
