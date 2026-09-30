# Day 55 演示工具

完整步骤、分镜讲稿和业务验收标准见 [Day 55 Demo](../../docs/week-8-notes.md#day55)。以下命令在仓库根目录执行。

## 离线准备

```powershell
$demoDir = Join-Path $env:TEMP ('day55-demo-' + [guid]::NewGuid().ToString('N'))
.\.venv\Scripts\python.exe .\scripts\day55\prepare_demo.py --production --output-dir $demoDir
if ($LASTEXITCODE -ne 0) { throw '演示包生成失败' }
```

生成四份请求、一份清单和空白验收记录。目录必须不存在；每批事件独立，销售重复请求与首次请求完全一致。脚本仅用 Python 标准库及 Day 50 本地生成器，不读取 `.env`，不启动服务，也不发送请求。

省略 `--production` 时使用 Test URL。`--n8n-base-url` 可调整生成的 n8n 地址；下面的执行工具仅支持 `http://localhost:<端口>` 或 `http://127.0.0.1:<端口>`。生成请求不代表配置或网络已验证。

## 手动执行单步

```powershell
& .\scripts\day55\invoke-demo-step.ps1 -BundleDirectory $demoDir -Step 01-customer
```

步骤依次为 `01-customer`、`02-email-review`、`03-sales`、`04-sales-duplicate`，逐步核对后再继续。客服和销售会使用模型，邮件与销售会写平台数据，销售会写模拟 CRM。流程沿用现有通知预览模式。

工具验证请求文件哈希和本机 Webhook 地址，禁止 HTTP 重定向。默认请求超时 180 秒，`-TimeoutSeconds` 范围 5–300 秒。结果写到演示包中的 `<步骤>.result.json`：

| 状态 | 含义 |
| --- | --- |
| `request_started` | 已建立执行记录；中断时结果可能未知 |
| `request_failed_or_unknown` | 请求失败或超时，需查原事件 |
| `response_received_unverified` | 收到响应，尚未核对业务成功 |

已有结果文件会阻止再次发送，包括错误和中断记录；不要通过删除结果文件重试。销售重复步骤额外要求原请求字节一致，首次结果属于本批且为成功的通知预览。只有该步骤用于显式重复演示，不能作为失败回放工具。

请求结果保留业务输入和响应，不自动标记验收通过；生成时的 manifest 也不会追踪后续状态。正式录制结果填写到 `recording-notes.json`，并按 [验收表](../../demo/day55-recording-checklist.md) 核对。
