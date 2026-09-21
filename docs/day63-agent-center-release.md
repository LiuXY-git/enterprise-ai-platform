# Day 63：Agent Center v0.1 发布准备与验收

## 1. 本日交付

- [统一文档入口](../agent-center/README.md)与[机器可读版本清单](../agent-center/release-v0.1.0.json)。
- [版本说明](agent-center-v0.1.md)与 [Week 9 总结](week-9-summary.md)。
- check_release.py：离线核对资产清单、哈希、历史证据关联及能力声明。
- verify_release.py：按两个已安装环境运行实验回归与发布检查，保存真实 pytest/JUnit 结果。

Day 63 原始交付是候选准备；当前内容已定版为 v0.1.0，远端状态见版本说明。发布准备不新增真实业务工具，离线脚本不创建远端发布。已有实验保持原样，历史模型证据沿用 Day 59 和 Day 62 的记录。

## 2. 准备环境

日常使用已有项目环境即可；如果是新检出目录，先按 [平台使用指南](user-guide.md)准备 `.venv` 和根目录依赖，再建立图实验环境：

```powershell
Set-Location 'C:\Users\Administrator\Desktop\enterprise-ai-platform'
if (-not (Test-Path '.\experiments\day60\.venv\Scripts\python.exe')) {
    & .\.venv\Scripts\python.exe -m venv .\experiments\day60\.venv
    if ($LASTEXITCODE -ne 0) { throw '创建图实验环境失败' }
}
& .\experiments\day60\.venv\Scripts\python.exe -m pip install -r .\experiments\day60\requirements-lock.txt
if ($LASTEXITCODE -ne 0) { throw '安装图实验依赖失败' }
& .\experiments\day60\.venv\Scripts\python.exe -m pip check
if ($LASTEXITCODE -ne 0) { throw '图实验依赖不兼容' }
```

不要把这个 lock 文件装进 API 环境。Day 60 的 lock 已覆盖 Day 58–60 本轮验收，旧 Day 58/59 独立环境可以继续保留。发布脚本不会自行安装依赖，也不会因为缺依赖就把跳过算成通过。

## 3. 只检查候选完整性

```powershell
$env:PYTHONIOENCODING = 'utf-8'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
& .\.venv\Scripts\python.exe .\scripts\day63\check_release.py
if ($LASTEXITCODE -ne 0) { throw '候选文件或证据不一致' }
```

该脚本只需 Python 标准库。它读取清单并检查：组件身份、发布状态与日期、能力声明、精确文件集合、路径是否在允许范围内、文件 SHA-256 和历史 source_hashes。

输出中的 unique_historical_tests=202 是版本记录中的去重数量，tests_executed_by_this_check=0 表示本命令没有执行测试。它也不检查 GitHub 状态、不读取 `.env`、不访问业务数据库。

清单不包含它自身和 Day 63 新生成的验收结果，避免循环哈希；这两者由 Git 版本记录管理。已冻结目录下出现新的非缓存文件、遗漏既有文件或改动内容都会导致检查失败。`.venv`、字节码和 pytest/Ruff 缓存不属于版本资产。

## 4. 执行完整离线候选验收

```powershell
& .\.venv\Scripts\python.exe .\scripts\day63\verify_release.py
if ($LASTEXITCODE -ne 0) { throw '离线候选验收失败，请查看输出目录中的日志' }
```

默认使用两个已安装解释器，依次运行：

| 分组 | 范围 | 预期测试数 |
| --- | --- | --- |
| api | Day 61 场景 + Day 62 Prompt | 116 |
| graph | Day 58 状态图 + Day 59 规划 + Day 60 状态恢复 | 86 |
| release | Day 63 清单和测试结果门禁 | 17 |

脚本先检查文件完整性，再运行 pytest；按 JUnit 统计 tests/failures/errors/skipped。三个分组都必须数量正确且无失败、错误或跳过，才能生成 status=passed 的 verification.json。每组有 180 秒超时，失败后停止，不继续制造“全部通过”的汇总。

结果存入系统临时目录下新建的 `agent-center-v01-*` 目录，包含各组 `.txt` 日志、`.xml` 和最终 verification.json，路径会输出到控制台。验收不清理该目录，便于保留故障证据；每次都用新目录，避免覆盖上次结果。

可显式选择解释器和一个尚不存在的输出目录：

```powershell
$outputPath = Join-Path $env:TEMP ('agent-v01-' + [guid]::NewGuid().ToString())
& .\.venv\Scripts\python.exe .\scripts\day63\verify_release.py --output-dir $outputPath
if ($LASTEXITCODE -ne 0) { throw '候选验收失败' }
```

另有 --api-python 和 --graph-python 参数可传绝对路径。已有输出目录会被拒绝，不会删除或覆盖文件。Day 60 测试使用本轮临时目录中的 SQLite，不碰用户的 data/day60 或业务数据库；强制退出测试只结束它自己创建的子进程。

## 5. 跑一个阶段示例

从 [Agent Center 入口](../agent-center/README.md)选择要学习的模块，不要把不同模块的输出格式混用：

- Day 59 输出 task_planning_result，可把其中的有效计划导入 Day 60。
- Day 60 输出模拟进度和 checkpoint_id，按 [恢复操作](day60-task-state.md)继续同一任务。
- Day 61 输出固定规则的场景报告。
- Day 62 输出模型报告的 accepted/rejected 与业务覆盖状态，当前不写入 Day 60 检查点。

Day 59/62 的 --live 会产生真实模型请求，完整离线验收不会启用它。已保存的 7 次历史模型记录可直接阅读，无需重新付费调用来复现发布检查。

## 6. 本轮结论

219 项离线测试通过，详情见 [validation.json](evidence/day63/validation.json)。本轮检查覆盖候选资产、依赖分组、进程恢复和报告约束；没有新增模型请求，没有重跑平台全部 API 或 Docker 验收。

历史候选已合并到 main；当前清单和文档已完成内容定版，并修正两处发布状态测试的前置条件。历史 validation.json 保留原始记录；定版后应重新运行完整验收，结果保存在新的输出目录。后续提交、标签与 GitHub Release 由维护者执行，见 [版本说明](agent-center-v0.1.md)。
