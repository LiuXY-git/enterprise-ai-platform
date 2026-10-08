# Day 75：Conversation Memory 可复刻操作

本实验让同一会话的后续请求使用已保存的部门信息。SQLite 保存会话和消息，关闭 Python 进程后可继续；当前部门来自用户明确输入，并保留来源请求 ID。模型根据恢复的上下文生成受约束的日报模板。

## 1. 环境与一键演示

首次安装独立环境：

```powershell
Set-Location 'C:\Users\Administrator\Desktop\enterprise-ai-platform'
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
& .\.venv\Scripts\python.exe -m venv .\experiments\day75\.venv
& .\experiments\day75\.venv\Scripts\python.exe -m pip install -r .\experiments\day75\requirements-lock.txt
& .\experiments\day75\.venv\Scripts\python.exe -m pip check
```

随后可直接运行：

```powershell
& .\experiments\day75\.venv\Scripts\python.exe -B .\experiments\day75\demo.py
```

此演示使用模拟模型、真实 SQLite 和 14 个分别启动的子进程；临时数据库用完清理。`passed=true` 表示保存、跨进程读取、更新、清除和隔离等预期结果均符合检查。`new_model_requests=0` 表示未请求模型服务。

## 2. 自己创建一个可继续的会话

下面使用默认数据库 `data/day75/memory.sqlite`，已加入 Git 忽略。`init` 只在首次执行，已有文件会拒绝覆盖；以后从 `new` 或 `show` 开始。

```powershell
$day75Python = '.\experiments\day75\.venv\Scripts\python.exe'
$day75Script = '.\experiments\day75\conversation.py'
& $day75Python -B $day75Script init
$day75Created = & $day75Python -B $day75Script new --user learner | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) { throw '创建会话失败' }
$day75Session = $day75Created.session_id
Write-Host "请保存会话 ID：$day75Session"

& $day75Python -B $day75Script say --user learner --session $day75Session --request-id fact-1 --text '我负责销售部门'
& $day75Python -B $day75Script say --user learner --session $day75Session --request-id ask-1 --text '给我生成日报'
& $day75Python -B $day75Script say --user learner --session $day75Session --request-id template-1 --text '给我生成日报模板'
```

预期：记录销售部门；实际日报请求仍询问日期与数据；模板请求返回“销售日报模板”，栏目为客户跟进、订单进展、问题与计划，内容均待填写。

这些调用每次都启动新的 Python 进程。信息来自磁盘，不依赖 Python 中尚未清空的变量。关闭 PowerShell 后，只需恢复目录、环境变量、上述 `$day75Python` 和 `$day75Script` 路径，并把保存的 ID 填回 `$day75Session`：

```powershell
$day75Session = '填入刚才保存的会话ID'
& $day75Python -B $day75Script show --user learner --session $day75Session
& $day75Python -B $day75Script say --user learner --session $day75Session --request-id template-2 --text '给我生成日报模板'
```

如需指定数据库，`--db` 必须写在子命令前；恢复时需使用同一数据库路径。

## 3. 更新、清除与隔离

```powershell
& $day75Python -B $day75Script say --user learner --session $day75Session --request-id fact-2 --text '改为财务部门'
& $day75Python -B $day75Script say --user learner --session $day75Session --request-id template-3 --text '给我生成日报模板'
& $day75Python -B $day75Script clear --user learner --session $day75Session
& $day75Python -B $day75Script say --user learner --session $day75Session --request-id template-4 --text '给我生成日报模板'
```

更新后生成财务模板，来源指向 `fact-2`；清除后再次询问部门。

`clear` 清空当前部门、消息正文与已保存结果，同时让在途旧请求失效。为防止旧请求重复执行，保留请求 ID、输入指纹和状态等标记。它不承诺物理抹除 SQLite 页、外部备份、终端输出或模型服务端曾收到的内容。

用 `new --user learner` 创建新会话，不会继承旧部门。用另一演示用户读取本会话会返回 `session_unavailable`。本地 `--user` 是自报的演示标识，不能替代登录认证；持有数据库文件的人也可能直接读取它。

## 4. 输入范围与上下文策略

为便于验证，当前只接受以下固定中文输入，可带常见句末标点：

- `我负责销售部门` / `改为销售部门`，部门还支持“财务”“运营”。
- `给我生成日报`：读取部门后提示补齐实际日报所需信息。
- `给我生成日报模板`：有部门时生成不含业绩数字的模板；无部门时询问。

其它内容返回 `unsupported_message`，不会保存。本实验不是自由聊天或自动画像抽取器；用户原话保留，部门由明确语句解析，助手回复不能修改部门。

上下文保留最近 4 组成功的用户/助手消息，另加最新部门及来源。成功的澄清轮次也计入历史；失败轮次只供 `show` 检查，不送回模型。被截断的组数通过 `omitted_pairs` 展示，因此旧原话离开窗口后，当前已确认部门仍可以使用。所有消息角色均为 system/user/assistant，没有需要配对裁剪的工具消息。

每个会话最多 200 个请求 ID，清除后标记仍计数，达到上限需新建会话。模型输入另设 12000 字符上限，每轮至多 1 次模型请求；字符限制不等于 token 精确计数，也不是生产容量规划。

## 5. 重复请求与失败处理

| 情况 | 行为 |
| --- | --- |
| 相同会话、请求 ID、输入和模式再次执行 | 返回已保存结果，`replayed=true`，本次模型请求数为 0 |
| 同一请求 ID 改了输入或切换 live/fixture | 拒绝 `request_id_conflict` |
| 模型超时或输出与当前部门不符 | 保存失败状态，不加入可用历史；同 ID 不自动重试 |
| 保存前程序退出 | 请求可能保持 `pending`，后续同 ID 不重新执行 |
| 同一会话有 pending 请求 | 拒绝另一请求，避免并发更新相互覆盖 |
| 模型返回后写库失败 | 不展示为成功，返回 `persistence_outcome=not_confirmed` |

新操作使用新的请求 ID。若某请求因进程中断长期停在 `pending`，先查看，再显式取消：

```powershell
& $day75Python -B $day75Script show --user learner --session $day75Session
& $day75Python -B $day75Script cancel --user learner --session $day75Session --request-id '填入pending请求ID'
```

取消只改变本地状态，不能撤回可能已发出的模型请求；迟到的写入会被拒绝。取消后如需重新操作，使用新 ID。

## 6. 可选：真实 Qwen 验证

显式开启才请求模型服务：

```powershell
& .\experiments\day75\.venv\Scripts\python.exe -B .\experiments\day75\demo.py --live --env-file .\.env
```

完整演示最多 2 次模型请求：销售模板一次、纠正为财务后的模板一次。记录部门、展示、清除、缺少部门的澄清都由程序完成，不消耗模型额度。已有有效项目配置时可执行，程序不把 `.env` 内容存入记忆。

本次 Qwen `qwen3.7-plus` 两次均成功；每步独立进程，证明新进程实际读取了保存内容。模型返回的部门、来源、模板类型、固定栏目与“未查询数据”标记逐项核对后，程序再渲染中文答案。此验收只证明限定模板任务，不证明任意自由文本理解。

## 7. 测试与代码入口

```powershell
& .\experiments\day75\.venv\Scripts\python.exe -B -m pytest .\experiments\day64 .\experiments\day75 -q
& .\experiments\day75\.venv\Scripts\python.exe -m ruff check .\experiments\day75
& .\experiments\day75\.venv\Scripts\python.exe -m ruff format .\experiments\day75 --check
& .\experiments\day75\.venv\Scripts\python.exe -B .\scripts\day70\release_gate.py
```

191 项离线测试通过：新增 50 项，复用的 Day 64 模型传输与协议回归 141 项。另有离线与真实模型各 14 步独立进程演示。代码入口：[存储与请求状态](memory_store.py)、[上下文组装与回答](conversation.py)、[跨进程演示](demo.py)、[测试](test_conversation.py)。验证记录见 [Day 75 证据](../../docs/evidence/week-11.md#day75)。

这是独立 CLI 实验；没有接入 FastAPI、Docker、MCP 或 LangGraph，也没有修改既有 Day 60/73 实现。保存的是同一会话范围的短期记忆，不是跨会话长期用户档案。
