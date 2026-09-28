# Day 84：Agent Center v1.0.0 候选准备

日期：2026-09-28；基线提交 `e5b1fe3e7f42bebaa189c93b9f368e610dbf3d79`。维护者暂时无法录制 Demo，授权先继续后续工作。本日准备候选与离线验收；视频待补录、正式定版、合并推送及远端标签/Release 都不因本日文档自动完成。

## 交付

- [统一入口](../agent-center/v1.0/README.md)、[版本范围](agent-center-v1.0.md)、[Week 12 总结](week-12-summary.md)、[Release 草稿](../agent-center/v1.0/release-notes.md)。
- [Day 83 演示讲稿](../demo/day83/README.md)和机器可读延期状态，无伪造视频或人工确认结果。
- [版本清单](../agent-center/release-v1.0.0.json)：`release_status=candidate`、`release_date=null`，记录录制延期及 Prompt 质量未测量。
- [完整性检查](../scripts/day84/v10_gate.py)：范围、哈希、历史源文件关联、父版本保护与录制状态。
- [分环境验收](../scripts/day84/verify_v10.py)与 [44 项发布检查](../scripts/day84/test_v10_release.py)。

## 环境准备

已有 Day 59 和 Day 73 虚拟环境时不需要安装。新检出仓库可按 [Day 77 环境说明](day77-agent-v05-release.md#2-环境准备) 创建两个独立环境；运行时依赖入口也可使用 `agent-center/v1.0/requirements-runtime.txt`，它复用被冻结的旧依赖。首次安装要联网，验收本身不安装依赖或读取 `.env`。

```powershell
Set-Location 'C:\Users\Administrator\Desktop\enterprise-ai-platform'
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
& .\experiments\day73\.venv\Scripts\python.exe -B .\scripts\day84\v10_gate.py
if ($LASTEXITCODE -ne 0) { throw '清单或历史资产不一致' }
& .\experiments\day73\.venv\Scripts\python.exe -B .\scripts\day84\verify_v10.py
if ($LASTEXITCODE -ne 0) { throw '发布验收失败，请检查输出日志' }
```

验收分组：规划器 49、基础运行时 369、Week 12 流程 259、发布检查 44，共 **721 项**，禁止失败、错误或跳过。检查声明计数与实际 JUnit 条目，并根据 classname/name 排除跨组重复计数。每组最多等待 900 秒；使用新的专用 pytest 临时目录。

可传 `--planner-python`、`--runtime-python` 和 `--output-dir`；输出目录必须不存在。成功生成 `verification.json`，包含清单摘要、各组计数、日志/JUnit 摘要、延期状态和验收时间。失败仅保存 `failure.json` 和已有输出，不生成成功报告。验收前后都检查资产，并拒绝过程中清单变化。

本次候选证据：[verification.json](evidence/day84/verification.json)和 [validation.json](evidence/day84/validation.json)。这些输出不纳入自身输入清单，避免循环哈希；验收报告记录清单摘要，文档与检查器本身纳入清单。

## 后续正式发布顺序

1. 合并候选分支到 main 并推送，确认工作区干净与远端一致。
2. 正式定版时将清单改为 `release_status=released`，填实际 `release_date`。视频可继续延期，但必须保留真实的 `demo_video` 状态；不能改成已录制。若改变资产内容，需重新审查并更新相应清单，旧版本冻结资产不可改写。
3. 用全新的目录再执行完整性与 721 项验收。保留候选证据，不覆盖它；正式 `verification.json` 必须对应正式清单摘要。
4. 提交定版改动并推送，记录完整提交 SHA。确认该提交中的清单与正式验收匹配。
5. 创建指向该提交的注释标签 `agent-center-v1.0.0` 并推送；先检查同名标签，已存在时核对而不强制覆盖。
6. 在 GitHub 选择该标签创建 Release，标题为 `Agent Center v1.0.0`。依据草稿写实际日期、完整提交和清单摘要，明确视频待补录、新 Prompt 效果未验证及能力边界，附正式 `verification.json`。
7. 核对远端标签提交和 Release 附件后，再记录“发布完成”。

以上是教程，不表示已执行。平台 API 仍为 1.0.0，本次宿主机学习实验无需重建 Docker 容器。
