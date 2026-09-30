# Day 64：Function Calling 实验

交付状态：代码、离线验收和单个虚构订单的 Qwen 真实验证完成。教学目标是观察模型如何提出工具调用，以及本地程序如何校验、执行并回传结果。完整说明见 [Day 64 操作流程](../../docs/week-10-notes.md#day64)，后续安排见 [Week 10 计划](../../docs/week-10-plan.md)。

唯一工具为 `calculate_order_total`，接收整数单价（分）、数量和减免百分比，返回确定的金额。示例中 199 元 × 3 件 × 九折 = 537.30 元。`discount_percent=10` 表示减免 10%，即九折。

## 离线运行

以下命令均在仓库根目录执行，使用现有 API 环境：

```powershell
& .\.venv\Scripts\python.exe experiments/day64/function_calling.py
& .\.venv\Scripts\python.exe experiments/day64/function_calling.py --case quote
& .\.venv\Scripts\python.exe experiments/day64/function_calling.py --case clarification
& .\.venv\Scripts\python.exe experiments/day64/function_calling.py --case no_tool
& .\.venv\Scripts\python.exe experiments/day64/function_calling.py --check-all
& .\.venv\Scripts\python.exe experiments/day64/function_calling.py --show-tools
```

默认案例是 `quote`。三个 fixture 分别覆盖工具计算、缺少参数时澄清和无需工具的直接回答。结果均以 JSON 输出；离线模式不请求模型接口，不需要密钥。本地金额函数仍会实际执行。

## 真实模型运行

```powershell
& .\.venv\Scripts\python.exe experiments/day64/function_calling.py --live --case quote
```

可加 `--env-file .env` 指定现有配置文件。仅显式使用 `--live` 才发送模型请求；单次运行最多两次模型请求、一次本地函数执行。当前 `qwen3.7-plus` 的 `quote` 成功复验使用两次模型请求、一次纯函数执行，金额为 537.30 元；澄清与无需工具分支目前只验证了 fixture。

第一轮设置 `tool_choice=auto`。程序检查工具名、参数和调用 ID，执行函数后将结果作为 `tool` 消息关联回原 `tool_call_id`，第二轮设置 `tool_choice=none`。非法参数、未知工具、多个工具请求和第二轮追加工具请求均受控停止。

模型自然语言仅是教学回答，尚未全面校验其语义；金额依据是本地工具的计算结果。fixture 成功与模型适配成功是两种证据。

传输响应限制为 128 KiB；连接超时为 10 秒，读取、写入和连接池等待阶段各 30 秒。这些是分阶段超时，不是整次运行的墙钟截止时间。

## 本日验收

```powershell
& .\.venv\Scripts\python.exe -m pytest experiments/day64 -q -p no:cacheprovider
```

本轮通过 141 项测试（核心 85 项、传输 56 项），三个 fixture 均通过且未发模型请求。真实调用首次因 `invalid_tool_call` 被拒绝，使用一次请求且未执行工具；补充官方工具调用 `index` 元数据和 `function_call: null` 的兼容处理及 Mock 端到端测试后复验通过。首次未保留原始响应，不将兼容修复描述为已逐字段还原该次失败。总新增模型请求为 3 次，包含失败尝试 1 次和成功复验 2 次。

核对 [验收记录](../../docs/evidence/day64/validation.json)、[fixture 结果](../../docs/evidence/day64/fixtures.json)、[首次真实尝试](../../docs/evidence/day64/live-first-attempt.json)和[成功复验](../../docs/evidence/day64/live-quote.json)。

## 范围

不接 SQL、RAG 或业务 API，不新增 Agent HTTP 接口，也不接入 LangGraph、SQLite 检查点或跨线程记忆。无需重建容器或修改依赖。真实业务工具与多工具组合继续按 Day 65–68 推进。

工具协议参考 [阿里云百炼 Function Calling](https://help.aliyun.com/zh/model-studio/qwen-function-calling)；本实验的严格参数限制、单工具预算和停止规则由应用代码落实。
