# Tests

该目录覆盖 FastAPI 接口、配置、SQLite、RAG 服务、工作流、通知、部署脚本及 n8n 导出结构。外部模型、通知和 Docker 操作由对应测试替身隔离；通过本套测试不代表完成真实服务联调。

在仓库根目录使用后端环境运行：

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

Agent/Evaluation 的独立实验和发布检查位于 `experiments`、`scripts`，使用各阶段说明指定的环境和命令，避免从仓库根目录无范围收集所有实验。

Day 92 新增 [应用工厂与生命周期测试](test_day92_application.py)，覆盖启动失败、关闭清理、应用实例隔离、临时 SQLite 初始化、原有 HTTP 行为以及完整 OpenAPI 契约。

[OpenAPI 快照](fixtures/day92-openapi.json)取自重构前提交 `a5d7671d3d376d8020d9a9b37489f17ca03f598a` 的后端环境。接口有意变更时需审核路径、模型和响应差异，再更新快照；不能仅为消除测试失败而覆盖基线。依赖升级造成的 schema 差异也需要审查。

Day 92 验证范围和复刻步骤见 [记录](../docs/week-14-notes.md#day92)。
