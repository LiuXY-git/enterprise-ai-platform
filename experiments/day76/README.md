# Day 76：Planning 学习操作

本目录只增加人工编写的 [planning-examples.json](planning-examples.json)，复用 Day 59 的规划器和环境。完整讲解见 [Day 76 学习文档](../../docs/week-11-notes.md#day76)。示例不执行季度查询，不新增模型请求。

## 1. 观察计划、澄清和失败

已有 Day 59 环境时直接执行；缺少环境则按 [Day 59 安装说明](../../docs/week-9-notes.md#day59)安装到其独立 `.venv`。

```powershell
Set-Location 'C:\Users\Administrator\Desktop\enterprise-ai-platform'
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$day76Python = '.\experiments\day59\.venv\Scripts\python.exe'
$day76Planner = '.\experiments\day59\task_planner.py'
& $day76Python -B $day76Planner --mock-case normal
& $day76Python -B $day76Planner --mock-case clarify
& $day76Python -B $day76Planner --mock-case invalid
& $day76Python -B $day76Planner --mock-case provider-error
```

| 场景 | 预期状态 | 退出码 |
| --- | --- | --- |
| normal | `planned` | 0 |
| clarify | `waiting_for_input` | 0 |
| invalid | `failed`，原因 `invalid_model_output` | 1 |
| provider-error | `failed`，原因 `provider_timeout` | 1 |

后两条返回非零是演示的预期结果。四种场景均应显示 `model_requests=0`、`task_executed=false`、`tools_executed=false`。`planning_attempts=1` 是本地生成函数被调用一次，不代表一次网络请求。

`normal` 使用 Day 59 固定的故障响应/差旅审批例子，并非季度销售计划。Mock 生成器不会根据 `--goal` 改写固定输出，因此本练习不要把修改目标文字后仍收到固定计划误认为模型理解了新目标。

## 2. 校验季度计划的字段与依赖

以下代码读取人工样例，用现有 `parse_plan()` 检查结构：

```powershell
@'
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path("experiments/day59").resolve()))
from plan_schema import parse_plan

examples = json.loads(Path("experiments/day76/planning-examples.json").read_text(encoding="utf-8"))
for item in examples["examples"]:
    decision = parse_plan(json.dumps(item["decision"], ensure_ascii=False))
    print(item["name"], decision.decision, "steps=", len(decision.steps))
'@ | & $day76Python -B -
```

预期显示 `clarify_quarter clarify steps=0` 和 `quarter_plan plan steps=4`。这里只检查人工写好的对象，没有调用模型推导步骤，也没有检验季度目标与所有描述的语义一致性。

再阅读 `quarter_plan`：`description` 是要做的事，`expected_output` 是完成标准，`depends_on` 是依赖。S1 包含三个单月数据需求，并不是一次现有 MCP 调用。

## 3. 在副本上思考

- 将 S1 的依赖改成 S2：应因前向依赖而拒绝。
- 将 action 改成 `send_email`：应因不在允许的分类中而拒绝。
- 保持格式，把描述改成无关内容：可能通过结构检查，说明还需要业务语义检查。
- 只有“分析本季度销售情况”时：先列出缺失范围，避免直接编造销售数字。

本日保存了四个原有 Mock 场景和两个新人工样例的实际离线校验结果，见 [offline-review.json](../../docs/evidence/day76/offline-review.json)。六次观察不是新增单元测试，也不等于业务任务执行成功。

你可以继续复跑 Day 59 的既有测试，但本日没有修改其代码，也没有重跑整套旧版测试。原模型实验、发布版本和历史证据保持不变。
