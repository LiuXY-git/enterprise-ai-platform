# Week 14：企业生产化优化

路线范围：Day 92–98。本文件包含 1 个每日章节，保留完整步骤、命令、验收记录与能力边界。

本周内容按日期排列，各节保留对应日期的实施状态，当前进度以[项目首页](../README.md)为准。

目前仅收录已完成的 Day 92；Day 93–98 仍是[后续计划](week-14-plan.md)。

[返回周目录](README.md#按周阅读) · [本周计划](week-14-plan.md)

## 本周目录

- [Day 92：后端代码重构与目录整理](#day92)

---

<a id="day92"></a>

## Day 92：后端代码重构与目录整理


<a id="day92-目标与作用"></a>

### 目标与作用

将后端入口中的应用构建、启动关闭、API 文档及路由注册分开，便于后续部署、配置和日志工作定位代码。业务处理仍由原有 routers/services 完成。

重构基线为 `a5d7671d3d376d8020d9a9b37489f17ca03f598a`。本次工作沿用现有功能，HTTP 与 OpenAPI 契约保持一致。

<a id="day92-目录和调用关系"></a>

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

### 验证结果

2026-09-30 离线验证：

- 后端 514 项通过：原有 506 项 + 新增 8 项；无失败、错误或跳过。
- 发布门禁 41 项通过；无失败、错误或跳过。
- 完整 OpenAPI 与基线快照一致，包含 25 个路径；文档、健康和聊天入口保持行为。
- 新测试覆盖工厂无资源启动副作用、实例隔离、生命周期顺序、建表异常、请求异常后的关闭清理、临时 SQLite 重复初始化和 HTTP 行为。
- Evaluation Center 206 个冻结资产及历史 Agent 冻结链完整性检查通过。完整性检查自身执行测试数为零，与上面的 41 项测试分别记录。
- 改动 Python 文件 Ruff 检查及格式检查通过。

证据见 [validation.json](evidence/week-14.md#day92)、[后端 JUnit](evidence/week-14.md#day92)、[发布门禁 JUnit](evidence/week-14.md#day92)、[冻结资产检查](evidence/week-14.md#day92)。测试使用临时数据库；新测试拦截外部 socket 连接，允许 Windows 事件循环所需的本机回环。

存在一条 Chroma 使用已弃用 asyncio API 的依赖警告，本次不升级依赖。未重跑全部历史发布测试、真实模型请求或通知发送；未重建容器。现有数据库、日志路径及 Docker 入口未改动。Week 14 后续事项见 [计划](week-14-plan.md)。
