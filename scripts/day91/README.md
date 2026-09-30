# Day 91：发布验收和正式标签

本次交付 Evaluation Center v0.1.0 发布候选。当前阶段先本地提交；合并、推送、正式标签与 GitHub Release 分别处理。清单 `release_status`、Git 标签、GitHub Release 是不同状态。

## 1. 环境

复用 [Day 73 环境](../../experiments/day73/README.md)，Windows Python 3.14.2；完整依赖锁位于 `experiments/day73/requirements-lock.txt`，包含 pytest、jsonschema、Pydantic 与 MCP SDK。无需真实模型密钥。已有环境先运行 pip check；新机器按 Day 73 教程安装，不必改 API/Docker 环境。

```powershell
Set-Location 'C:\Users\Administrator\Desktop\enterprise-ai-platform'
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$day91Python = '.\experiments\day73\.venv\Scripts\python.exe'
& $day91Python -B -m pip check
if ($LASTEXITCODE -ne 0) { throw '环境依赖检查失败' }
```

## 2. 只检查清单，不执行测试

```powershell
& $day91Python -B .\scripts\day91\release_gate.py
if ($LASTEXITCODE -ne 0) { throw '发布完整性检查失败' }
```

检查内容：完整文件库存、CRLF→LF 后的 SHA-256、Day 85–90 历史来源与证据关联、Day 90 历史逐例评分，以及 Agent Center v1.0/v0.5/v0.2/v0.1 完整性链。

Day 86 验收与 Day 87 合并交付，因此独立 validation 索引为 Day 85、87、88、89、90。Day 85 的 `evaluation-center/README.md` 已随学习进度更新，清单单独保留其原历史哈希并排除当前导航页比较；不存在普遍忽略文档的规则。Week 13 导航页可继续更新，已冻结的每日源码、教程和证据保持不变。

此命令返回 `tests_executed_by_this_check=0`，不是本次重新通过了历史全部测试，也不联网核对标签或 Release。

## 3. 重新执行候选验收

```powershell
$day91Candidate = Join-Path '.\data\day91' ('candidate-' + [Guid]::NewGuid().ToString('N'))
& $day91Python -B .\scripts\day91\verify_release.py --output-dir $day91Candidate
if ($LASTEXITCODE -ne 0) { throw '候选验收失败，请检查输出目录中的 failure.json 和日志' }
Get-Content (Join-Path $day91Candidate 'verification.json') -Raw -Encoding UTF8
```

验收会顺序运行：

1. 342 项既有回归：Day 64 传输 56、Day 85 框架 59、Day 86 数据集 32、Day 87 执行 35、Day 88 延迟 28、Day 89 消耗 34、Day 90 评分 54、旧发布保护 44。
2. 41 项 Day 91 发布测试。
3. 新运行 12 个 fixture 场景，通过 Day 90 inspect 重新核对 SQLite、回执、评分和来源。

共 383 项测试，编号去重，无失败、错误或跳过；另有 12 例集成运行，不能把它们加成 395 项 pytest 测试。验收前后检查清单和全部冻结文件未变化。每个测试组/集成命令有 900 秒外层上限；超时会尝试停止本次创建的进程树，清理无法确认时不得宣布通过。终端会逐组打印进度，详细输出在各组 stdout.log/stderr.log。

成功写 `verification.json`，失败写 `failure.json`，已有目录不会覆盖。不能修改记录来让失败变成通过；修复问题后使用新目录重跑。未重新执行全部 721 项历史 Agent 发布测试。

```text
candidate-<id>/
  verification.json
  regression/tests.xml
  release/tests.xml
  integration/full/run/                  完整原始证据
  integration/full/evaluation/report.json
```

本次维护者验收目录为 `data/day91/candidate-20260930`；提交到 Git 的摘要位于 [docs/evidence/day91](../../docs/evidence/day91/README.md)。本机原始 SQLite 留在忽略目录，新的克隆请自行运行验收。

## 4. 合并 main 之后正式定版

下面是后续正式发布时由维护者执行的流程，不是候选交付时自动执行的动作。先确认 Day 91 已合并推送、当前 main 干净，且尚无同名标签；不要覆盖既有正式标签。

```powershell
function Invoke-Day91Git {
    & git @args
    if ($LASTEXITCODE -ne 0) { throw ('Git 失败：' + ($args -join ' ')) }
}
Invoke-Day91Git switch main
Invoke-Day91Git pull --ff-only origin main
if (Invoke-Day91Git status --porcelain) { throw '请先处理工作区变更' }
$day91Tag = 'evaluation-center-v0.1.0'
if (Invoke-Day91Git tag --list $day91Tag) { throw '本地正式标签已存在，不能覆盖' }
if (Invoke-Day91Git ls-remote --tags origin ('refs/tags/' + $day91Tag)) { throw '远端正式标签已存在，不能覆盖' }
& $day91Python -B .\scripts\day91\release_gate.py
if ($LASTEXITCODE -ne 0) { throw '定版前清单检查失败' }

& $day91Python -B -c "from pathlib import Path; import json; from datetime import date; p=Path('evaluation-center/release-v0.1.0.json'); d=json.loads(p.read_text(encoding='utf-8')); assert d['release_status']=='candidate'; d.update(release_status='released', release_date=date.today().isoformat()); p.write_text(json.dumps(d, ensure_ascii=False, indent=2)+chr(10), encoding='utf-8')"
if ($LASTEXITCODE -ne 0) { throw '正式状态更新失败' }

$day91Formal = Join-Path '.\data\day91' ('release-' + [Guid]::NewGuid().ToString('N'))
& $day91Python -B .\scripts\day91\verify_release.py --output-dir $day91Formal
if ($LASTEXITCODE -ne 0) { throw '正式验收失败，保留现场，不提交或打标签' }

Invoke-Day91Git add -- evaluation-center/release-v0.1.0.json
Invoke-Day91Git diff --cached --check
Invoke-Day91Git commit -m 'release: finalize Evaluation Center v0.1.0'
& $day91Python -B .\scripts\day91\release_notes.py --verification-dir $day91Formal --output-file (Join-Path $day91Formal 'release-body.md')
if ($LASTEXITCODE -ne 0) { throw '正式发布正文核对失败，不打标签' }

Invoke-Day91Git tag -a $day91Tag -m 'Evaluation Center v0.1.0'
Invoke-Day91Git push --atomic origin main ('refs/tags/' + $day91Tag)
Invoke-Day91Git status --short --branch
Invoke-Day91Git ls-remote --tags origin ('refs/tags/' + $day91Tag + '*')
Write-Host ('Release 正文：' + (Resolve-Path (Join-Path $day91Formal 'release-body.md')).Path)
Write-Host ('验收附件：' + (Resolve-Path (Join-Path $day91Formal 'verification.json')).Path)
```

如果正式验收失败，manifest 可能已处于 released 但尚未提交：该状态不证明发布完成。排查后从“新建 `$day91Formal` 目录并重跑验收”继续，不要再次覆盖历史输出。若代码必须改变，应重新评审发布清单，不要直接重算所有哈希绕过检查。

release_notes.py 只接受 released 状态、相同 manifest 哈希、通过的 XML 和完整评分证据，并要求工作区干净且 Git 提交里的清单一致。生成的正文自动填充日期、完整 SHA 与清单哈希，不需要手工填占位符。它不创建 Git 标签、不联网发布。

## 5. 创建 GitHub Release

1. 打开仓库 Releases，创建新 Release。
2. 选择已有标签 `evaluation-center-v0.1.0`。
3. 标题填写 `Evaluation Center v0.1.0`，正文复制本轮 `$day91Formal/release-body.md`。
4. 上传同一目录的 `verification.json`。候选验收附件不能冒充正式定版验收。
5. 核对正文中的提交 SHA、版本、日期与标签，然后发布。是否标记 Latest 按维护者希望展示的组件决定；无需影响已有 Agent Center 标签。

发布后再核对页面顶部、标签及 Assets。正文引用的本机完整 SQLite 目录不会随单个 verification.json 附件自动上传；附件是带哈希和测试统计的验收摘要，不是整个运行归档。
