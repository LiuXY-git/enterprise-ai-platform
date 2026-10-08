# Tests

该目录覆盖 FastAPI 接口、配置、SQLite、RAG 服务、工作流、通知、部署脚本及 n8n 导出结构。外部模型、通知和 Docker 操作由对应测试替身隔离；通过本套测试不代表完成真实服务联调。

在仓库根目录使用后端环境运行：

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

Agent/Evaluation 的独立实验和发布检查位于 `experiments`、`scripts`，使用各阶段说明指定的环境和命令，避免从仓库根目录无范围收集所有实验。

按周资料布局下，Evaluation 测试使用 Day 73 环境执行 `python scripts/evaluate.py test`；该入口自动准备程序所需的资料路径。不要直接用原测试路径读取已经归档的 Day 目录。

Day 92 新增 [应用工厂与生命周期测试](test_day92_application.py)，覆盖启动失败、关闭清理、应用实例隔离、临时 SQLite 初始化、原有 HTTP 行为以及完整 OpenAPI 契约。

[OpenAPI 快照](fixtures/day92-openapi.json)取自重构前提交 `a5d7671d3d376d8020d9a9b37489f17ca03f598a` 的后端环境。接口有意变更时需审核路径、模型和响应差异，再更新快照；不能仅为消除测试失败而覆盖基线。依赖升级造成的 schema 差异也需要审查。

Day 92 验证范围和复刻步骤见 [记录](../docs/week-14.md#day92)。

Day 93 新增 [Compose 与接口测试](test_day93_compose.py)、[隔离持久化脚本测试](test_day93_persistence.py)。浏览器测试和真实 Docker 重建验收分别执行，入口见 [Week 14](../docs/week-14.md#day93)。

Day 94 的 [环境管理测试](test_day94_environment.py)覆盖文件选择、配置来源、脱敏、特殊字符和 PowerShell 参数传递；实际 Compose CLI 与隔离容器检查的范围见 [Week 14](../docs/week-14.md#day94)。
