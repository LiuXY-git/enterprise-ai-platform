# Agent Center v1.0.0 候选版

Week 12（Day 78–84）学习成果的统一入口：固定销售任务的日志、错误恢复、人工审批、业务验收和 Prompt 对照。v1.0 是学习路线的阶段版本，不表示已具备通用企业 Agent 的全部能力。

当前清单为 **candidate**，尚未正式定版或创建该版本标签/Release。以 [机器清单](../release-v1.0.0.json) 为准。Day 83 视频按维护者要求延期，新版 Prompt 的真实模型改善尚未测量。

- [能力范围](../../docs/agent-center-v1.0.md)
- [Week 12 总结](../../docs/week-12-summary.md)
- [Demo 讲稿与补录步骤](../../demo/day83/README.md)
- [离线验收与后续发布流程](../../docs/week-12-notes.md#day84)
- [Release 说明草稿](release-notes.md)

## 快速体验

在项目根目录、已有 Day 73 环境时执行：

```powershell
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$v10Task = Join-Path '.\data\day83' ('try-' + [Guid]::NewGuid().ToString('N'))
& .\experiments\day73\.venv\Scripts\python.exe -B .\experiments\day82\prompt_lab.py prepare --case monthly --output-dir $v10Task
```

预期为虚构销售额 3000.00 元和待审批事项，未执行发送。继续操作使用 [演示讲稿](../../demo/day83/README.md)，不要把 `pending` 当成已完成。

## 离线发布验收

```powershell
& .\experiments\day73\.venv\Scripts\python.exe -B .\scripts\day84\v10_gate.py
if ($LASTEXITCODE -ne 0) { throw '版本完整性检查失败' }
& .\experiments\day73\.venv\Scripts\python.exe -B .\scripts\day84\verify_v10.py
if ($LASTEXITCODE -ne 0) { throw '离线发布验收失败' }
```

要求 **721 项**全部通过：规划器 49、MCP/会话等基础回归 369、Week 12 回归 259、发布检查 44。各组 JUnit 必须与实际条目一致，测试编号不得跨组重复，无失败、错误或跳过；验收前后清单和资产必须一致。

解释器分别使用 Day 59 与 Day 73 的现有环境。新检出仓库参照 [环境准备](../../docs/week-12-notes.md#day84)，不要将独立实验依赖安装进 API 环境。验收不安装包，不启用 live，不创建 Git 标签或 Release。

MCP、独立会话记忆和规划器的 v0.5 内容继续受父版本完整性检查保护；本次测试覆盖上述明确列出的集合，不重新运行全部历史工具/API/Docker 测试。
