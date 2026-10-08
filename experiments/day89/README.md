# Day 89：Token 与模型 API 成本

当前项目使用[统一评测入口](../../evaluation-center/README.md#运行评测)读取按周资料。下面运行命令已切换到该入口，阶段编号保持不变。

今天新增 usage 采集层、按输入/输出 Token 分别计价的核算器，以及带消耗覆盖状态的评测报告。默认仍运行 fixture，不请求真实模型。真实计费采集接口已用离线 HTTP 响应验证，尚未接通评测器的真实模型模式。

## 1. 运行十二例并看清模拟调用

```powershell
Set-Location 'C:\Users\Administrator\Desktop\enterprise-ai-platform'
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$day89Out = Join-Path '.\data\day89' ('full-' + [Guid]::NewGuid().ToString('N'))
& .\experiments\day73\.venv\Scripts\python.exe -B .\scripts/evaluate.py --stage 89 run --suite full --output-dir $day89Out
$day89Exit = $LASTEXITCODE
if ($day89Exit -ne 0) { Write-Warning '执行有异常，保留目录并检查证据。' }
$day89Report = Get-Content (Join-Path $day89Out 'report.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$day89Report.usage.summary | Format-List
$day89Report.usage.rows | Format-Table case_id, status, model_attempts, provider_requests, input_tokens, output_tokens, estimated_model_api_cost
```

沿用 [Day 73 环境](../day73/README.md)，无需密钥。12 例仍走 Day 88 单调时钟计时与 Day 87 固定子进程；最外层 report.json 保存 execution 快照和 usage，完整原始运行在 execution/ 子目录。

完整 fixture 运行的预期：provider_requests=0，input_tokens/output_tokens/total_tokens=null，estimated_model_api_cost="0"。含义是**没有发起模型 API 请求，因此没有本轮模型 API 费用**；不是测到了 0 Token，也不表示本机计算、MCP 或其它服务都免费。

fixture 的 model_attempts 可能大于 0（本次共 24 次），包括注入超时和重试。它不是供应商请求数，也不能拿来乘平均 Token。未取得有效执行记录的行标记 unknown_execution_usage，整批成本会保持 null，同时保留已知部分。

## 2. 观察 usage 的完整与缺失两种核算

```powershell
$day89Demo = Join-Path '.\data\day89' ('usage-demo-' + [Guid]::NewGuid().ToString('N'))
& .\experiments\day73\.venv\Scripts\python.exe -B .\experiments\day89\demo.py --output-dir $day89Demo
if ($LASTEXITCODE -ne 0) { throw '离线示例失败' }
(Get-Content (Join-Path $day89Demo 'complete\report.json') -Raw -Encoding UTF8 | ConvertFrom-Json).summary | Format-List
(Get-Content (Join-Path $day89Demo 'partial\report.json') -Raw -Encoding UTF8 | ConvertFrom-Json).summary | Format-List
```

该示例使用 httpx.MockTransport，实际经过旧 ChatTools 客户端和新的 UsageTransport，但没有联网。前两次返回合成 usage，第三次注入超时。所有记录明确标记 synthetic_response。

| 项目 | 两次 usage 完整 | 加入一次超时 |
| --- | --- | --- |
| 请求尝试 | 2 | 3 |
| 已报告输入/输出 Token | 150 / 50 | 150 / 50 |
| 完整输入/输出总量 | 150 / 50 | null / null |
| 完整估算费用 | 0.00070 CNY | null |
| 已知估算小计 | 0.00070 CNY | 0.00070 CNY |
| 覆盖状态 | complete | partial |

示例价格是假设的输入 2 元/百万 Token、输出 8 元/百万 Token，**不是 Qwen 或其它供应商报价**：

`150 × 2 / 1,000,000 + 50 × 8 / 1,000,000 = 0.00070`

核算使用 Decimal，输入价格为字符串，避免浮点误差；不会按字符数猜 Token，不会把超时当成未计费，也不只计算重试的最后一次。

## 3. 使用显式价格快照重新核算

[illustrative-pricing.json](examples/illustrative-pricing.json) 定义 provider、model、币种、每百万 Token 输入/输出价、生效日期、来源说明和 illustrative 标记。

```powershell
$day89Replay = Join-Path '.\data\day89' ('replay-' + [Guid]::NewGuid().ToString('N'))
& .\experiments\day73\.venv\Scripts\python.exe -B .\scripts/evaluate.py --stage 89 replay --ledger (Join-Path $day89Demo 'complete-ledger.json') --prices .\experiments\day89\examples\illustrative-pricing.json --output-dir $day89Replay
if ($LASTEXITCODE -ne 0) { throw '核算失败' }
```

replay 只读取已有账本，不调用 Agent。报告保存账本摘要和完整价格快照，后续修改价格文件不会改变旧报告。没有价格、模型/供应商不匹配或计费规则超出支持范围时，费用为 null。

如以后核算真实模型，需另建价格配置，人工核对对应模型、区域、时间和计费规则；本模块不联网抓取最新价格，也不证明配置是官方报价。当前只支持固定输入/输出文本价格，不支持阶梯价、缓存折扣、多模态收费、税费或账户优惠。出现非零缓存/推理等细分字段或未知计费字段时，保留合法 Token 数，拒绝套用简单费用公式。

## 4. 采集层如何工作

旧 Day 64 ChatTools 返回标准化回答时会丢弃 usage。新 [UsageTransport](transport.py) 包在注入的 HTTP transport 外，在返回数据离开客户端前观察 usage；不改动冻结客户端或回答内容，不增加重试。

当前支持同步、非流式 JSON 请求；响应读取仍可分块。可识别 usage.prompt_tokens、completion_tokens、total_tokens，要求严格非负整数且合计一致。捕获大小限制 128 KiB，早退/读取失败/缺失 usage 保持未知。response 已有完整合法 usage、但 Agent 后续拒绝回答时，仍保留该次消耗。

账本只保存本地 attempt_id、声明模型/供应商、响应状态和 usage，不保存 API Key、请求消息、回答文本或原始错误消息。按顺序记录每次尝试，不允许重复编号、跳号或混合真实/合成来源；当前不是并发采集器。账本在内存中维护，调用方需及时保存；进程被强杀后不能假定未保存部分免费。

以后真实集成可把 UsageTransport 注入 ChatTools 的 transport 参数，使用真实 HTTP transport 并保存账本；本次产品 CLI 没有 --live，未新增真实请求。离线采集验证不能作为供应商账单验收。

## 5. 验证本轮证据

```powershell
& .\experiments\day73\.venv\Scripts\python.exe -B .\scripts/evaluate.py --stage 89 inspect --output-dir $day89Out
if ($LASTEXITCODE -ne 0) { throw 'usage、执行快照或底层证据不一致' }
```

inspect 验证主报告与 execution/ 的实际文件一致，不执行任务、不判分。replay 报告属于另一种格式，不能传给此 inspect。若在封装报告写入前中断，保留的 execution/ 可用 Day 88 inspect 查看；不覆盖、不自动恢复。

输出的 estimated_cost 是按配置估算，不是最终发票；未知总量与 known_* 小计必须区分。Day 90 将继续实现成功率，本次仍未自动判分。

[交付与验收](../../docs/week-13.md#day89)。
