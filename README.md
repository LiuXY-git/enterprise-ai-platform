# Enterprise AI Platform

面向企业知识库、工作流、Agent 与评测的学习项目。**当前完成 Day 97：技术文档整理；Day 98 发布仍待进行。**

从 [当前操作手册](docs/week-14.md#day97) 开始，按需要查看 [架构](docs/week-14.md#day97-architecture)、[启动与配置](docs/week-14.md#day97-setup)、[维护与排障](docs/week-14.md#day97-operations) 或 [逐周学习记录](docs/README.md#按周阅读)。

## 项目目标

| 模块 | 已实现入口 | 当前边界 |
| --- | --- | --- |
| Knowledge Hub | 知识库前端、FastAPI 上传/检索/生成回答 | 前端提供上传与片段检索；生成回答使用 /rag/answer |
| Workflow Center | n8n 模板、Dify 代理、运行账本与模拟 CRM | Dify 独立部署；销售通知为预览，邮件流程生成草稿 |
| Agent Center | 宿主机 Python CLI、本地 stdio MCP、任务日志与人工确认 | 固定虚构销售场景；审批后仅本地模拟发送；没有 Agent HTTP API |
| Evaluation Center | CLI 执行、耗时、usage、规则评分与报告 | 12 个固定 fixture 场景；真实模型评测入口尚未接入 |

## 当前进度

- Week 14 已完成代码重构、Compose 前后端部署、环境管理、日志追踪、统一测试及技术文档。
- 最新操作说明集中在 [Week 14](docs/week-14.md#day97)；过去每日交付、复刻过程和运行结果分别保留在 [Week 文档](docs/README.md)和 [结果摘要](docs/evidence/README.md)。
- 平台 API 元数据版本仍为 1.0.0。Agent Center v1.0.0、Evaluation Center v0.1.0 是各自的阶段版本；版本号相同不表示属于同一产品发布。
- Day 55/83 视频补录、Workflow Center v1.0 标签与 Release、企业微信真实发送、Day 82 真实 Prompt 改善测量等待办继续保留。Day 97 没有创建新标签或发布版本。

## 项目结构

| 目录/文件 | 用途 |
| --- | --- |
| [backend/](backend/README.md) | FastAPI、业务服务、配置与日志 |
| [frontend/](frontend/) | 静态 HTML/CSS/JavaScript 和 Nginx 同源代理 |
| [compose.yaml](compose.yaml)、[docker/](docker/README.md) | API、前端、n8n 的构建与运行配置 |
| [n8n/](n8n/) | 工作流导出、可复用模板和组件清单 |
| [experiments/](experiments/)、[agent-center/](agent-center/README.md) | 独立 Agent 实验与阶段版本入口 |
| [evaluation-center/](evaluation-center/README.md) | 固定测试集、Agent 描述与评测入口 |
| [scripts/](scripts/) | 环境初始化、部署检查、测试及评测工具 |
| [tests/](tests/README.md) | API 与维护工具回归用例 |
| [docs/](docs/README.md)、[demo/](demo/README.md) | 按周手册、运行摘要及演示资料 |
| data/、logs/ | 本机数据库、向量索引、实验输出与日志；见 [保留范围](docs/week-14.md#day97-operations) |

## 快速启动

以下命令在仓库根目录执行，假定已有 Python 环境和正确的私有 .env。首次使用请先按 [环境准备](docs/week-14.md#day97-setup) 完成初始化；已有 n8n 数据卷必须保留原加密键。

### 本地运行

用 8001 避开默认 Docker API 的 8000。此进程不接管 Compose 前端的 API 连接：

```powershell
$env:EAP_ENV_FILE = '.env.local'
.\.venv\Scripts\python.exe -B -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8001 --reload
```

先准备 .env.local，再打开 [本地开发 API 文档](http://127.0.0.1:8001/docs)。结束服务后按需清除本终端选择：`Remove-Item Env:EAP_ENV_FILE -ErrorAction SilentlyContinue`。

### Docker 运行

选择需要的范围，三种模式互斥：

| 目标 | 命令 |
| --- | --- |
| 只更新 API | `& .\scripts\start.ps1 -EnvFile '.env' -ApiOnly` |
| 更新 API 与前端，保留 n8n 现状 | `& .\scripts\start.ps1 -EnvFile '.env' -WithoutN8n` |
| 更新 API、前端、n8n | `& .\scripts\start.ps1 -EnvFile '.env'` |

启动对应服务后访问：[知识库前端](http://127.0.0.1:8080/)、[API 文档](http://127.0.0.1:8000/docs)、[n8n](http://127.0.0.1:5678/)。这些端口只绑定本机。

`-ApiOnly` 不会启动已经关闭的前端，也不会关闭已经运行的前端。仅停止前端可在项目根目录执行 `docker compose --env-file .env stop frontend`；完整状态检查及停止方法见 [操作手册](docs/week-14.md#day97-setup)。

## 项目文档

- [当前架构与数据流](docs/week-14.md#day97-architecture)
- [配置与部署](docs/week-14.md#day97-setup)
- [接口职责与调用边界](docs/week-14.md#day97-api)
- [数据、日志与维护](docs/week-14.md#day97-operations)
- [测试与评测怎么选](docs/week-14.md#day97-testing)
- [按周学习目录](docs/README.md)、[演示材料](demo/README.md)

## 技术栈

API 使用 Python 3.14、FastAPI、Pydantic、SQLite 与本地 Chroma；前端为静态资源和 Nginx；n8n 编排工作流，Dify 独立管理其应用和模型。Agent 实验使用 LangGraph、本地 stdio MCP 与 SQLite，规划器/API/MCP 依赖分别安装。实际锁定版本以 [依赖文件](requirements.txt)、[Compose 配置](compose.yaml)和各实验锁文件为准；技术选择过程见 [Week 1](docs/week-1.md#tech-stack)。

## API 接口

平台保持 25 个 OpenAPI 路径、26 个 HTTP 操作；在线规格为运行服务的 /openapi.json。`/chat` 是回显示例，`/rag/query` 返回知识片段，`/rag/answer` 才调用生成模型。独立通知接口在配置齐全时会真实发送，不作为健康探针使用。

本项目尚未提供完整的调用方身份认证；/retrieval 使用专用 Bearer Key。具体路径、输入和结果见 [接口手册](docs/week-14.md#day97-api)与 [完整 API 参考](docs/week-4.md#api)。

## 开发状态

代码修改后使用统一回归入口：

```powershell
.\.venv\Scripts\python.exe -B scripts/test_platform.py list
.\.venv\Scripts\python.exe -B scripts/test_platform.py run --suite all
if ($LASTEXITCODE -ne 0) { throw '回归未全部通过，请查看本次 summary.json' }
```

all 指 API、规划器、工具/记忆、销售流程及评测框架五组；其他旧实验仍按其专用说明验证。报告默认保存到 logs/test-runs/ 的新目录，详见 [测试范围](docs/week-14.md#day96)。代码回归不等于真实模型质量或生产可用性。

<a id="week-5企业工作流中心"></a>
<a id="week-6n8n-工作流自动化"></a>
<a id="week-7企业平台集成"></a>

阶段入口：[Week 5 企业工作流](docs/week-5.md)、[Workflow Center v0.1](docs/week-6.md#workflow-center-v0.1)、[Week 6 总结](docs/week-6.md#summary)、[Week 7 集成](docs/week-7.md)、[Workflow Center v1.0 候选](docs/week-8.md#workflow-center-v1.0)、[Agent v1.0](docs/week-12.md#agent-center-v1.0)、[Evaluation v0.1](docs/week-13.md#evaluation-center-v0.1)。
