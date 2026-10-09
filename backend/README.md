# Backend

FastAPI 后端提供文档上传、RAG、Dify 代理、工作流账本、模拟 CRM 与独立通知接口。当前使用说明见 [Week 14 技术手册](../docs/week-14.md#day97)，完整接口字段见 [API 参考](../docs/week-4.md#api)。

## 目录与请求流程

| 位置 | 职责 |
| --- | --- |
| [app/main.py](app/main.py) | 稳定 ASGI 入口，导出 app |
| [app/application.py](app/application.py) | create_app()，组装 LoggedFastAPI、配置与路由 |
| [app/core/lifecycle.py](app/core/lifecycle.py) | 启动加载环境、配置日志、初始化数据库；关闭清理缓存 |
| [app/core/environment.py](app/core/environment.py) | API 环境文件选择 |
| [app/core/metadata.py](app/core/metadata.py)、[app/routers/registry.py](app/routers/registry.py) | OpenAPI 元数据与路由注册 |
| [app/routers](app/routers)、[app/models](app/models) | HTTP 输入、响应契约与错误映射 |
| [app/services](app/services) | 文档、检索、生成模型、工作流、CRM 与集成逻辑 |
| [app/database.py](app/database.py) | SQLite 建表与访问 |
| [app/settings.py](app/settings.py)、[app/check_config.py](app/check_config.py) | 分组配置、环境加载及离线自检 |
| [app/core/request_logging.py](app/core/request_logging.py)、[app/observability.py](app/observability.py) | 请求关联、固定事件字段与安全日志处理 |
| [app/logging_config.py](app/logging_config.py)、[app/workflow_logging.py](app/workflow_logging.py) | 应用 JSON 日志与工作流 JSONL 事件 |

HTTP 请求经 routers → services → 数据层/外部适配；models 声明输入输出契约。上传解析、保存元数据、切片和索引后返回 indexed；检索和生成回答是两个不同入口。

create_app() 构造时不启动数据库或配置日志，这些副作用发生在 lifespan。测试需要生命周期时使用 `with TestClient(create_app())`，替换 `backend.app.core.lifecycle` 中依赖。工厂隔离应用状态和依赖覆盖，不承诺每个应用自动拥有独立进程环境、数据库或日志，详见 [Day 92](../docs/week-14.md#day92)。

## 本地开发

从仓库根目录执行，先按 [环境准备](../docs/week-14.md#day97-setup) 建立 .venv 和私有环境文件。使用 8001 避开 Docker API 的 8000：

```powershell
$env:EAP_ENV_FILE = '.env.local'
.\.venv\Scripts\python.exe -B -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8001 --reload
```

打开 [开发 API 文档](http://127.0.0.1:8001/docs)。未设置 EAP_ENV_FILE 时默认加载仓库根 .env；明确选择的文件不存在时启动失败，相对路径按仓库根解析，进程已有变量优先。配置变化后重启进程；未使用组件缺少密钥不应阻止基础健康接口。

结束后按需运行 `Remove-Item Env:EAP_ENV_FILE -ErrorAction SilentlyContinue`。Compose 前端仍连其 api 容器，不会自动改连开发端口。

脱敏配置检查显式选择同一文件：

```powershell
.\.venv\Scripts\python.exe -B -m scripts.manage_env check --target local --env-file .env.local --component llm
if ($LASTEXITCODE -ne 0) { throw 'LLM 配置检查未通过' }
```

此命令不验证密钥有效性、外部网络或模型质量。API 的模型配置也不会更改 Dify/n8n 内部模型，详见 [Day 94](../docs/week-14.md#day94)。

## 验证与数据

统一入口为 API 组保存报告，其他 Agent 环境分别选择：

```powershell
.\.venv\Scripts\python.exe -B scripts/test_platform.py run --suite api
if ($LASTEXITCODE -ne 0) { throw 'API 回归未全部通过' }
.\.venv\Scripts\python.exe -B -m ruff check backend tests
if ($LASTEXITCODE -ne 0) { throw '代码检查未通过' }
```

单个用例调试仍可使用 python -m pytest，完整分组和结果格式见 [Day 96](../docs/week-14.md#day96)。

SQLite 为根目录 data/enterprise_ai.db，Chroma 为 data/chroma/，日志为 logs/；不是 backend/data 或 backend/logs。容器挂载、模型缓存与维护范围见 [当前操作手册](../docs/week-14.md#day97-operations)。

/health 只表明 API 运行，/chat 为回显示例；/rag/query 检索片段，/rag/answer 生成回答。平台没有 Agent HTTP API。当前无完整调用方鉴权，/retrieval 单独使用专用 Bearer Key，不能直接视为已完成生产安全部署。

## 日志定位

应用生成 X-Request-ID 响应头，并以相同 request_id 关联 HTTP 与工作流记录。JSON 请求摘要记录状态、耗时、固定事件、error_type/source；错误处理栈外的 LoggedFastAPI 保留原接口响应。日志故障不应改变业务结果。

工作流日志仍可能保留有限业务快照，不能直接作为公开数据。字段、轮转、后台错误与排障见 [Day 95](../docs/week-14.md#day95)；隔离 HTTP 验收入口是 [verify_logging.py](../scripts/verify_logging.py)。
