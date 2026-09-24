# Day 70 Agent v0.2 发布准备与验收

用户提供的《FDE 16 周企业 AI 平台学习路线 优化版》将 Day 70 定为“发布 Agent v0.2”，Week 11 从 Day 71 开始学习 MCP。本日将 Week 10 已完成的工具能力整理为 Agent Center v0.2.0 发布候选，版本号与平台 API 的 1.0.0 分开管理。

## 交付内容

- [统一使用入口](../agent-center/v0.2/README.md)、[版本说明](agent-center-v0.2.md)、[Week 10 总结](week-10-summary.md)和[Release 正文草稿](../agent-center/v0.2/release-notes.md)。
- [版本清单](../agent-center/release-v0.2.0.json)：精确资产集合、能力声明、历史证据与哈希。
- [release_gate.py](../scripts/day70/release_gate.py)：标准库离线完整性检查，不执行 pytest。
- [verify_v02.py](../scripts/day70/verify_v02.py)：用当前 Python 运行两组离线测试，保留日志和 JUnit。
- [test_v02_release.py](../scripts/day70/test_v02_release.py)：40 项发布检查，覆盖内容漂移、遗漏、历史关联、状态转换、失败和超时处理。

v0.1 的 `agent-center/README.md` 已在原清单中冻结，故使用独立的 `agent-center/v0.2/` 入口，不改写旧版文件。

## 准备与快速体验

从仓库根目录运行已有 `.venv`。新检出目录可以显式创建环境并安装固定的测试依赖；依赖安装需要网络，但后续离线验收不调用模型或天气服务：

```powershell
Set-Location 'C:\Users\Administrator\Desktop\enterprise-ai-platform'
$env:PYTHONUTF8 = '1'
# 仅在没有 .venv 的新检出目录执行以下创建命令：
# py -3.14 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r agent-center/v0.2/requirements-test.txt
if ($LASTEXITCODE -ne 0) { throw '测试依赖安装失败' }
& .\.venv\Scripts\python.exe -m pip check
if ($LASTEXITCODE -ne 0) { throw '依赖不兼容' }
```

本轮验证使用已有 Python 3.14.2 环境，没有重新安装依赖；未验证干净机器的在线安装。离线测试不需要真实 Key 和 ONNX 下载，Hub 的测试使用替代实现。真实知识库检索的本地缓存要求仍按 Day 66 文档准备。

先按 [v0.2 入口](../agent-center/v0.2/README.md)体验完整、天气失败、无销售三种简报，再执行版本验收。

## 只检查文件完整性

```powershell
& .\.venv\Scripts\python.exe scripts/day70/release_gate.py
if ($LASTEXITCODE -ne 0) { throw '版本文件或历史证据不一致' }
```

检查身份、状态与日期、能力声明、完整文件集合、SHA-256、历史 source_hashes 和 evidence_hashes，并调用原 v0.1 检查核对 70 个冻结文件与 41 个历史源码关联。CRLF 统一转换为 LF 后计算哈希，兼容 Windows 检出。

清单覆盖 Day 64–69 实验和历史证据、实际复用的后端服务、测试配置与依赖、Day 70 发布代码和版本说明。出现额外文件、删除文件、重复记录、越界路径或哈希不符均会失败；缓存和虚拟环境不属于版本资产。历史校验还会阻止只修改单个文件并更新当前清单哈希来绕过旧记录。

清单自身与新生成的 Day 70 验收证据不纳入清单，避免循环哈希。验证结果另存清单哈希和输出哈希，Git 提交保留来源。该机制用于发现意外漂移，不是签名或对抗任意仓库篡改的安全认证。`unique_historical_tests=648` 是历史清单计数，`tests_executed_by_this_check=0` 才是这条命令实际执行的测试数。

## 完整离线验收

```powershell
& .\.venv\Scripts\python.exe scripts/day70/verify_v02.py
if ($LASTEXITCODE -ne 0) { throw '离线验收失败，请查看输出目录' }
```

默认在系统临时目录创建新目录。也可以指定一个尚不存在的目录，脚本拒绝覆盖旧结果：

```powershell
$day70Output = Join-Path $env:TEMP ('agent-v02-' + [guid]::NewGuid().ToString())
& .\.venv\Scripts\python.exe scripts/day70/verify_v02.py --output-dir $day70Output
if ($LASTEXITCODE -ne 0) { throw '离线验收失败' }
```

| 分组 | 测试范围 | 要求 |
| --- | --- | --- |
| tools | Day 64–69 加既有检索回归 | 648 项 |
| release | Day 70 发布检查 | 40 项 |

脚本在前后各查一次完整性并比较清单哈希；每组最多 300 秒，必须退出码为 0、JUnit 汇总与实际 testcase 一致、数量正确且无失败、错误或跳过。移除外部 PYTEST_ADDOPTS、关闭第三方插件自动加载，使用独立 pytest 临时目录。

成功生成 `verification.json`，包含分组计数、环境、清单及 XML/日志哈希。测试失败或超时保留已有输出，生成 `failure.json`，不生成通过记录。既有输出目录会在执行前拒绝，原文件保持原样。日志仅作为测试诊断，不打印 `.env`。

## 本轮记录与发布状态

验收记录放在 [docs/evidence/day70/validation.json](evidence/day70/validation.json)，原始机器结果为 [verification.json](evidence/day70/verification.json)。本日不修改原工具执行代码，不新增真实外部调用，不更新容器；验证范围为工具实验回归、发布检查和 v0.1 完整性。

本轮候选完成后，main 合并、分支推送、正式定版、组件标签与 GitHub Release 仍需分别完成和核实。工作流程如下：

1. 审阅候选清单、能力边界与本轮结果，提交并合并到 main，推送对应分支。
2. 正式定版时将清单 `release_status` 改为 `released`，`release_date` 填实际定版日期。这个状态描述内容定版，不代表 GitHub 发布已完成。
3. 重新运行 `verify_v02.py`，保留新的结果目录，不覆盖本轮候选历史。清单可同时通过 candidate 和 released 状态检查，测试不依赖某个固定状态。
4. 提交并推送定版改动，确认工作区干净、main 与远端一致，记录该提交 SHA。
5. 在这个确定的 SHA 上创建 `agent-center-v0.2.0` 标签并推送；若标签已存在，先核实其目标，不能强制移动。
6. 用 [Release 正文草稿](../agent-center/v0.2/release-notes.md)填写实际日期、SHA 和最终验收结果，创建 `Agent Center v0.2.0` GitHub Release。分别核对标签目标与发布页面，不能把页面可见等同于已验证全部业务能力。

Day 55 视频、Workflow Center v1.0 标签和 Release、企业微信真实发送仍按原待办处理。Day 71 将按路线进入 MCP，当前版本不提前宣称具备 MCP 能力。
