# Workflow Center v0.1.0 发布说明

状态：Day 42 发布候选验收完成，等待 Git 提交与组件标签。

## 版本定位

Workflow Center v0.1.0 是 Enterprise AI Platform v1.0.0 内的工作流自动化
组件版本，不改变平台 API 的 `1.0.0` 版本号。

仓库中已经存在平台早期标签 `v0.1.0`，因此本组件正式标签使用：

```text
workflow-center-v0.1.0
```

这样可以明确区分“平台版本”和“Workflow Center 组件版本”。

## 发布范围

v0.1.0 收录 Day 36 至 Day 41 的 7 个版本化工作流：

| 工作流 | 发布层级 | 用途 |
| --- | --- | --- |
| `W6D36 - n8n Foundation Check` | reference | 验证手动触发和运行环境 |
| `W6D37 - Customer Request Webhook` | reference | 演示 Webhook 请求响应闭环 |
| `W6D38 - AI Customer Request Processing` | reference | 演示 n8n 调用 FastAPI/Dify |
| `W6D39 - AI Email Assistant` | reference | 演示邮件分类和人工审核分支 |
| `W6D40 - Daily Workflow Report` | optional | 生成运营日报，需要单独绑定模型凭据 |
| `W6D41 - Workflow Error Handler` | release | 自动保存生产执行失败 |
| `W6D41 - Persistent AI Email Assistant` | release | v0.1.0 主业务入口 |

机器可读清单位于 `n8n/workflow-center-v0.1.0.json`，它固定组件版本、n8n
版本、API 版本、工作流文件、导入顺序、发布顺序、手动绑定项和质量门禁。

## 核心能力

- Docker Compose 部署固定版本 n8n
- Webhook 测试与生产请求入口
- 调用 FastAPI/Dify 企业 AI 工作流
- 邮件请求规范化、分类、AI 回复和人工审核
- 定时或手动生成运营日报
- SQLite 保存工作流输入、输出、请求者、状态、时间和 Token
- 使用业务事件 ID 拦截重复执行
- 使用 Error Trigger 自动保存失败
- 最多 3 次显式失败回放，并复用首次输入

## 运行依赖

| 依赖 | 固定值或要求 |
| --- | --- |
| Enterprise AI Platform API | `1.0.0` |
| n8n | `2.36.8` |
| Docker Compose 服务 | `api`、`n8n` |
| 必需环境变量 | `N8N_ENCRYPTION_KEY`、`DIFY_WORKFLOW_API_KEY` |
| 时区 | `Asia/Shanghai` |
| 持久化 | `./data`、`./logs`、`n8n_data` 命名卷 |

真实密钥只允许保存在本地 `.env` 或 n8n Credential 中，不得写入工作流 JSON、
文档、测试或 Git 历史。

## 启动发布候选

在项目根目录执行：

```powershell
docker compose up -d --build api n8n
docker compose ps
```

预期 API 和 n8n 容器均为 `healthy`。继续检查版本和双向连通性：

```powershell
docker compose exec n8n n8n --version

Invoke-RestMethod `
    -Uri "http://127.0.0.1:8000/health" `
    -Method Get

docker compose exec n8n `
    wget -qO- http://api:8000/health
```

预期 n8n 版本为 `2.36.8`，两次健康检查均返回 `{"status":"ok"}`。

## 导入与发布顺序

在 n8n 编辑器中使用 Import from File，按发布清单顺序导入。核心链路必须：

1. 先导入 `W6D41 - Workflow Error Handler`
2. 再导入 `W6D41 - Persistent AI Email Assistant`
3. 打开主工作流 Settings
4. 将 Error Workflow 绑定到 `W6D41 - Workflow Error Handler`
5. 先发布错误处理工作流
6. 再发布主工作流

仓库导出文件保持 `active: false`，并移除了实例 ID、Webhook ID、项目元数据和
Credential 引用。导入后必须在目标实例重新完成绑定与发布，不能假设导入等于
生产启用。

Day 40 日报是可选组件。导入后需要为 `Qwen Chat Model` 重新选择
OpenAI-compatible 通义千问 Credential，并确认实例时区后才能发布调度。

## 发布验收

### 自动化检查

```powershell
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m ruff check --no-cache .
git diff --check
```

发布清单测试会自动验证：

- 清单覆盖全部 7 个工作流文件
- 工作流名称与清单一致且不重复
- 所有导出文件保持未激活
- 不包含实例 ID、Webhook ID 或 Credential 引用
- 不包含常见明文 Token
- 错误处理器在主工作流之前导入和发布
- 主工作流声明 Error Workflow 手动绑定

### 真实场景

| 场景 | 通过标准 |
| --- | --- |
| AI 成功 | 数据库状态为 `succeeded`，保存输出、耗时和 Token |
| 人工审核 | 数据库状态为 `needs_human_review` |
| 重复事件 | 不再次调用 AI，`duplicate_count` 加 1 |
| 自动失败 | Error Trigger 将状态更新为 `failed` 并保存错误 |
| 失败回放 | 复用原 `run_id`，`retry_count` 加 1，成功后清空错误 |

### 最终门禁结果

2026-09-04 的发布候选检查结果：

- 自动化测试：`81 passed`
- Ruff：全部通过
- Git diff 格式检查：通过
- API 容器：`healthy`
- n8n 容器：`healthy`
- n8n 版本：`2.36.8`
- n8n 到 FastAPI：`{"status":"ok"}`
- FastAPI OpenAPI：版本 `1.0.0`，包含 5 个工作流路径

### n8n 安全审计

执行 `docker compose exec n8n n8n audit` 后确认：

- HTTP Request 与 Code 节点被识别为高能力节点，发布前必须继续进行参数审查
- 主工作流 Webhook 当前没有认证，只允许用于本机或可信网络
- 本机存在一个未被激活工作流使用的 `OpenAI account` Credential，应由实例管理员确认是否仍需保留
- 审计提示存在较新的 n8n 补丁版本；v0.1.0 暂时冻结已完成真实验收的 `2.36.8`，升级需要单独执行兼容性回归

上述结果没有改变仓库工作流已移除 Credential 引用和明文 Token 的结论。

## 发布流程

质量门禁全部通过后：

```powershell
git add README.md CHANGELOG.md backend docs n8n tests
git commit -m "release: publish Workflow Center v0.1.0"
git tag -a workflow-center-v0.1.0 -m "Workflow Center v0.1.0"
git push -u origin feature/workflow-center-v0.1-release
git push origin workflow-center-v0.1.0
```

正式发布前必须再次确认 `git status --short` 没有未提交文件，并核对标签指向
最终验收提交。

## 当前限制

- 工作流运行接口尚未增加调用方认证和租户隔离
- 发布包不会携带 Credential，导入目标实例后必须重新绑定
- Error Workflow 使用实例内工作流 ID 关联，不能跨实例直接保留
- Day 40 当前仍使用固定测试记录，而不是直接查询 `workflow_runs`
- 失败回放由调用方显式传入 `replay: true`，尚未实现定时自动重试
- 当前是单机 SQLite 与 n8n 命名卷部署，不是高可用生产集群
- Webhook 尚未增加签名、限流和重放窗口校验
- n8n 2.36.8 不是审计时的最新补丁版本，外部部署前应先评估升级并执行全量回归

## 参考资料

- [n8n CLI commands](https://docs.n8n.io/hosting/cli-commands/)
- [n8n source control environments](https://docs.n8n.io/source-control-environments/create-environments/)
- [n8n security audit](https://docs.n8n.io/hosting/securing/security-audit/)
- [Day 41：n8n 工作流数据库持久化](n8n-workflow-persistence.md)
