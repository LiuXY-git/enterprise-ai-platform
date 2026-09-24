# Day 77：Agent Center v0.5.0 发布准备

日期：2026-09-24；起点 `6336e3b45d21f9d7ae4b382b52aa19da6519e02d`。本日整理候选版本与离线验收。正式定版、main 合并推送、标签和 GitHub Release 是后续独立步骤，本日不自动执行。

## 1. 交付

- [统一入口](../agent-center/v0.5/README.md)、[版本边界](agent-center-v0.5.md)、[Week 11 总结](week-11-summary.md)与 [Release 说明草稿](../agent-center/v0.5/release-notes.md)。
- [机器清单](../agent-center/release-v0.5.0.json)，状态 `candidate`，`release_date=null`。
- [完整性检查](../scripts/day77/release_gate.py)：文件清单、哈希、历史关联和父版本检查。
- [离线验收](../scripts/day77/verify_v05.py)：使用不同 Python 环境运行去重测试，核对 JUnit 的声明计数和实际条目，拒绝失败、跳过、日志缺失或验收期间清单变化。
- [发布检查测试](../scripts/day77/test_v05_release.py)：候选和定版状态、错误日期、篡改、清单漏项、旧版本漂移、伪造计数和失败记录等。

## 2. 环境准备

已完成 Day 59/73/75 的本机可直接使用现有环境。新检出仓库分别安装，避免将 LangGraph 规划器和 MCP 依赖混装进 API 环境：

```powershell
Set-Location 'C:\Users\Administrator\Desktop\enterprise-ai-platform'
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'

# 仅当对应目录不存在时创建虚拟环境
& .\.venv\Scripts\python.exe -m venv .\experiments\day59\.venv
& .\experiments\day59\.venv\Scripts\python.exe -m pip install -r .\experiments\day59\requirements-lock.txt
& .\experiments\day59\.venv\Scripts\python.exe -m pip check

& .\.venv\Scripts\python.exe -m venv .\experiments\day73\.venv
& .\experiments\day73\.venv\Scripts\python.exe -m pip install -r .\agent-center\v0.5\requirements-runtime.txt
& .\experiments\day73\.venv\Scripts\python.exe -m pip check
```

首次安装要联网；验收不安装包、不加载 `.env`、不启用 `--live`。运行发布脚本的 Python 只需标准库，测试由显式选定的两个解释器运行。Day 75 单独操作可按其说明安装环境；发布验收复用 Day 73 环境运行其测试。

## 3. 离线验收

```powershell
& .\experiments\day73\.venv\Scripts\python.exe -B .\scripts\day77\release_gate.py
if ($LASTEXITCODE -ne 0) { throw '清单或历史证据不一致' }
& .\experiments\day73\.venv\Scripts\python.exe -B .\scripts\day77\verify_v05.py
if ($LASTEXITCODE -ne 0) { throw '发布验收失败，查看输出目录日志' }
```

验收要求：规划器 49、运行时 369、发布检查 38，共 456 项全部通过。输出 `verification.json` 记录清单哈希和每组计数；失败则保留 `failure.json` 与已产生的日志，不写成功报告。超时每组最多等待 300 秒。

可用 `--runtime-python`、`--planner-python` 指定对应环境；`--output-dir` 必须是尚不存在的目录。不要指向原有证据目录，避免覆盖候选记录。完整性检查本身不运行测试。

本日证据见 [验证记录](evidence/day77/validation.json)和 [候选验收](evidence/day77/verification.json)。模型验证沿用 Day 73/75 的历史虚构输入证据，本次新增模型请求为 0。

## 4. 后续正式发布顺序

本节为待执行流程，不表示已完成。

1. 合并候选分支到 main 并推送，确认工作区干净及两端提交一致。
2. 正式定版时，只将 v0.5 清单的 `release_status` 改为 `released`，`release_date` 填实际日期。日期变更本身不要求重算资产哈希；若资产也改动，应重新审查、更新清单并验收。
3. 用新的输出目录重新执行上述完整性与离线验收，必须 456 项通过。候选证据保留不改，正式验收文件另存。
4. 提交定版改动并推送 main，记录完整提交 SHA。确认正式验收对应的清单哈希等于该提交中的清单；此时再准备标签。
5. 将注释标签 `agent-center-v0.5.0` 指向刚核对的定版提交并推送；先核查同名标签不存在，存在则核对而不强制覆盖。
6. 在 GitHub 创建 Release，选择该标签，标题 `Agent Center v0.5.0`，填写实际日期、完整提交 SHA、清单哈希和已核对的 [Release 说明](../agent-center/v0.5/release-notes.md)，附正式 `verification.json`。发布后核对标签提交与页面。

正式发布前不要把候选状态或占位文字当作最终元数据。平台 API 仍为 `1.0.0`，不用重建 Docker 容器来获得这些宿主机学习实验。
