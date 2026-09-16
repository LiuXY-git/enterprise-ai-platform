# Day 53 一键启动与持久化验收

Day 53 提供 Windows PowerShell 一键启动和部署检查，限制文件及容器日志容量，并通过独立测试容器的删除重建验证 SQLite 与日志保留。Dify 继续由已有独立部署管理。

## 核实后的目录

| 内容 | 宿主机 | 容器 |
| --- | --- | --- |
| SQLite | `data/enterprise_ai.db` | `/app/data/enterprise_ai.db` |
| Chroma | `data/chroma` | `/app/data/chroma` |
| 应用日志 | `logs/app.log` | `/app/logs/app.log` |
| 工作流事件 | `logs/workflow-events.jsonl` | `/app/logs/workflow-events.jsonl` |
| Embedding 缓存 | `data/chroma-cache` | `/home/app/.cache/chroma` |
| n8n 数据与凭据 | 当前 Compose 项目的 `n8n_data` 命名卷 | `/home/node/.n8n` |

Day 53 直接读取当前容器的代码路径和挂载，确认现有挂载正确。此前 Day 51/52 文档写成 `backend/logs` 或 `/app/backend/logs` 是路径层级判断错误，已更正。此次没有迁移数据库或更换数据卷；现有 SQLite 完整性检查通过。

## 一键启动

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

## 只检查已有部署

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

## 日志容量

`app.log` 与 `workflow-events.jsonl` 各使用约 5 MiB 的单文件轮转阈值，保留三份备份。每种日志通常约占 20 MiB；单条大记录和轮转时点可能造成偏差。这适用于当前单 API 进程，不宣称支持多个进程共同轮转同一文件。

API 与 n8n 的 Docker 控制台日志采用 `json-file`，`max-size=10m`、`max-file=3`。配置变更在相应容器重新创建后生效，现有容器不会因为修改 YAML 立即改变日志策略。日志有业务内容，不应直接公开上传。

## 独立容器重建验收

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

## 常用操作与故障处理

```powershell
docker compose ps
docker compose stop
docker compose start
```

需要排查失败时，先保留脚本报错，再查看 `docker compose ps`。只有需要时在本机查看 `docker compose logs --tail 50 api` 或 n8n 日志，分享前去除业务内容。不要分享完整 `docker compose config`，日常语法检查使用 `--quiet`。

构建失败保留原容器；健康检查超时则保留现场，脚本不会自动回滚或删除服务。启动脚本可在问题修复后重新运行，Compose 会按配置更新服务。`down -v` 会删除命名卷，不用于日常停止或升级。数据持久化不代替备份；跨机器迁移还需要保存数据库、Chroma、n8n 卷及原加密密钥。

## 验收状态

- 全量自动化测试：506 项通过；保留一项既有 ChromaDB 弃用警告。
- Ruff：后端、测试与新增持久化验证脚本通过。
- PowerShell 7 的启动、失败停止、错误挂载与路径带空格检查通过；Windows PowerShell 5.1 的模拟启动检查也通过。
- 真实隔离 Docker 验收通过：同一启动脚本成功启动 API，强制重建后 SQLite 记录、应用日志、工作流事件日志保留，日志驱动容量设置符合预期。
- 独立测试容器、网络和镜像已清理；原业务 API 容器 ID 与镜像保持一致，API 和 n8n 仍 healthy。

可提交证据见 [Day 53 部署验收结果](evidence/day53/deployment-validation.json)。当前业务环境的更新、分支推送和合并由维护者按交付步骤执行；本轮没有部署 Day 53 到业务容器，也没有调用真实模型或发送消息。
