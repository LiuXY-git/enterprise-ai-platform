# Evaluation Center：Agent 评测学习模块

Week 13 输入 Agent 描述和版本化测试集，逐步构建可追溯的评测报告。

## 运行评测

评测结果已整理为[按周摘要](../docs/evidence/README.md)。当前目录使用下面的统一入口；它自动读取周数据包，在临时工作目录运行现有评测实现，结果保存到你指定的位置。

在仓库根目录执行，每次使用新的输出目录：

```powershell
$runDir = "data/evaluation/run-$([guid]::NewGuid().ToString('N'))"
.\experiments\day73\.venv\Scripts\python.exe -B scripts/evaluate.py run --suite full --output-dir $runDir
.\experiments\day73\.venv\Scripts\python.exe -B scripts/evaluate.py inspect --input-dir "$runDir/run" --report "$runDir/evaluation/report.json"
```

`full` 运行 12 个固定 fixture 场景；使用 `--suite smoke` 可先运行小批次。默认包含运行、延迟、usage 和规则评分，未接入真实模型评测。重复使用已有输出目录会被拒绝。

分阶段学习可在命令中加入 `--stage 87`、`--stage 88` 或 `--stage 89`，分别观察执行、延迟、usage；默认 `--stage 90`。例如 `scripts/evaluate.py --stage 88 run --suite smoke --output-dir data/evaluation/latency-demo`。

新入口使用当前检出的实现代码，解包资料只用于兼容记录读取；不会向项目中重新生成 Day 文档或 Day 证据目录，也不会把当前代码替换成旧版本。

执行配套测试：`python scripts/evaluate.py test`；只运行某阶段可用 `python scripts/evaluate.py --stage 88 test`。这里的 `python` 应使用上面同一个 Day 73 环境。

## 学习材料

- [Day 85 框架设计](design.md)：描述契约与未执行预检，旧示例保留。
- [Day 86 正式测试集](datasets/README.md)：12 个固定虚构销售场景和独立标准答案。
- [Day 87 自动执行教程](../experiments/day87/README.md)：固定 fixture Agent、真实本地 MCP、隔离目录、逐例运行与证据检查。
- [Day 88 延迟教程](../experiments/day88/README.md)：单例耗时、分组均值和 P50/P95，异常样本单列。
- [Day 89 Token 与成本](../experiments/day89/README.md)：usage 采集、显式价格、完整/部分账本与 fixture 计费边界。
- [Day 90 成功率](../experiments/day90/README.md)：独立规则判分、失败原因、分类统计及分母。
- [Evaluation Center v0.1.0 发布候选](v0.1/README.md)：版本范围、验收与正式发布操作。
- [Week 13 计划](../docs/week-13.md#plan)。

当前可以自动执行并保留结果。执行状态与业务状态分别记录；已增加单例延迟和 usage/成本核算；Day 90 已增加独立判分与成功率，真实模型评测尚未接入。Evaluation Center v0.1.0 已正式发布，旧阶段文档保留当时的说明。

第一次使用先执行 Day 86 check / preview，再运行 Day 87 smoke 或 full。预检的 not_run、执行的 completed、Day 90 评分的 passed 分属三个不同阶段，不能混为“全部测试通过”。
