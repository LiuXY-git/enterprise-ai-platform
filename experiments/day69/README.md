# Day 69：复杂任务验收与稳定简报

对 Day 68 多工具组合进行 18 个固定场景验收，并从工具回执生成完整简报。输出固定包含虚构数据说明、来源和未完成项，避免把模型摘要遗漏的信息直接交给使用者。

在仓库根目录运行，无新增依赖，无需更新容器：

```powershell
& .\.venv\Scripts\python.exe experiments/day69/acceptance.py --check-all
& .\.venv\Scripts\python.exe experiments/day69/acceptance.py --case weather_timeout --markdown
& .\.venv\Scripts\python.exe experiments/day69/acceptance.py --recovery-check
```

默认全部离线。销售 SQL 真实查询虚构临时库；模型、知识片段和天气使用 fixture / Mock。`verdict.passed=true` 表示符合场景预期，不等于业务任务完成：预期的 `partial`、`failed`、`rejected` 也可以通过验收，退出码为 0。

不请求模型，直接将 Day 68 已保存的真实结果生成带完整说明的简报：

```powershell
& .\.venv\Scripts\python.exe experiments/day69/acceptance.py --render-day68 --markdown
```

先检查历史证据哈希再渲染，不改写原摘要或历史文件。天气是 2026-09-24 查询时的快照，不是重新获取的当前天气。[已生成的简报](../../docs/evidence/week-10.md#day69) 可直接阅读。

可选真实模型分支验证：

```powershell
& .\.venv\Scripts\python.exe experiments/day69/acceptance.py --live --case no_sales
& .\.venv\Scripts\python.exe experiments/day69/acceptance.py --live --case weather_timeout
```

沿用已有 `.env` 模型配置，可加 `--env-file .env`。前者最多 2 次 Qwen 请求，后者最多 4 次；本轮两例均通过，共 6 次请求、0 次天气网络请求。后者的**天气超时由程序模拟注入**，Qwen、SQL 和隔离知识检索真实执行；没有人为触发天气服务故障。只使用虚构销售与制度资料。

本日新增 84 项测试，连同前几天共 648 项通过：

```powershell
$day69TestDir = Join-Path $env:TEMP ('day69-tests-' + [guid]::NewGuid().ToString('N'))
& .\.venv\Scripts\python.exe -m pytest experiments/day64 experiments/day65 experiments/day66 experiments/day67 experiments/day68 experiments/day69 tests/test_retrieval_service.py -q -p no:cacheprovider --basetemp $day69TestDir
```

详见 [场景与复刻说明](../../docs/week-10.md#day69) 和 [验收清单](../../docs/evidence/week-10.md#day69)。恢复验证是检查后另建会话重跑，仍不支持断点续跑或跨进程恢复；没有自动重试和业务写入。
