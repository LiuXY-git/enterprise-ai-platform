# Backend

FastAPI 后端提供文档上传、RAG、Dify 代理、工作流运行账本、模拟 CRM 和独立通知接口。用户操作见 [平台使用指南](../docs/week-8.md#user-guide)，数据流见 [系统架构](../docs/week-1.md#architecture)。

## 目录

| 位置 | 职责 |
| --- | --- |
| [app/main.py](app/main.py) | 稳定 ASGI 入口，导出 `app` |
| [app/application.py](app/application.py) | `create_app()` 应用工厂，组装配置和路由 |
| [app/core/lifecycle.py](app/core/lifecycle.py) | 启动加载环境、配置日志、初始化数据库；关闭清理缓存 |
| [app/core/metadata.py](app/core/metadata.py) | OpenAPI 描述与标签 |
| [app/routers/registry.py](app/routers/registry.py) | 集中注册 HTTP 路由，保持原有顺序 |
| [app/routers](app/routers) | HTTP 接口 |
| [app/models](app/models) | Pydantic 请求和响应契约 |
| [app/services](app/services) | 文档、检索、模型、工作流、CRM 和集成逻辑 |
| [app/database.py](app/database.py) | SQLite 建表与访问 |
| [app/settings.py](app/settings.py) | 分组配置、环境加载和校验 |
| [app/check_config.py](app/check_config.py) | 离线配置自检命令 |
| [app/logging_config.py](app/logging_config.py)、[app/workflow_logging.py](app/workflow_logging.py) | 应用日志和工作流 JSONL 事件 |

## 本地开发

从仓库根目录运行，先按使用指南准备 `.env` 和 `.venv`。Docker API 已占用 8000 时，请停止对应 API 或调整本地端口，避免混淆两个进程：

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

默认访问 [API 文档](http://127.0.0.1:8000/docs)。应用启动时默认加载仓库根目录 `.env`；可在启动前设置进程变量 `EAP_ENV_FILE` 选择其他文件（相对路径以仓库根目录为基准），明确选择的文件不存在时启动失败，进程已有环境变量优先；缺少未使用组件的密钥不应阻止基础健康接口。离线检查选定组件：

```powershell
.\.venv\Scripts\python.exe -m backend.app.check_config --component llm
.\.venv\Scripts\python.exe -m backend.app.check_config --component dify
```

这些命令不验证密钥有效性和真实网络。API 模型配置不会改变 Dify/n8n 内部模型，详见 [配置说明](../docs/week-8.md#day52)。Day 94 新增环境初始化、来源检查和 Compose 文件选择，使用 [环境变量管理](../docs/week-14.md#day94)；上述旧检查命令指定文件仍需显式传入 `--env-file`。

## 验证与数据

在仓库根目录执行：

```powershell
.\.venv\Scripts\python.exe -m pytest tests
.\.venv\Scripts\python.exe -m ruff check backend tests
```

SQLite 与 Chroma 默认在根目录 `data` 下，日志在根目录 `logs` 下；不是 `backend/data` 或 `backend/logs`。容器挂载与重建验收见 [Day 53](../docs/week-8.md#day53)。

详细接口及当前边界见 [API 文档](../docs/week-4.md#api)。`/chat` 是回显示例；使用 `/rag/answer` 获取知识库生成回答。

Day 92 重构保留 Uvicorn/Docker 入口、接口契约和数据路径。`create_app()` 构建应用时不启动数据库或配置日志；这些操作发生在 ASGI lifespan。测试应通过 `with TestClient(create_app())` 触发生命周期，并替换 `backend.app.core.lifecycle` 中的依赖。工厂隔离应用状态、依赖覆盖和文档标签，不承诺每个应用使用不同的进程环境或数据库，详见 [Day 92](../docs/week-14.md#day92)。

Day 95 为应用增加 JSON 日志与服务端生成的 X-Request-ID，通过同一编号关联请求和工作流事件。日志字段、保护范围及复刻步骤见 [Week 14 日志系统](../docs/week-14.md#day95)。现有接口正文保持不变；应用使用 LoggedFastAPI 在错误处理栈外记录请求，不改写原异常响应。
