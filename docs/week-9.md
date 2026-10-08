# Week 9：Agent 基础与状态管理

学习路线：Day 57–63。

按学习路线归档，计划、实施记录与阶段总结集中在本页。记录中的版本、验收结果和“当前”均对应各节写作时点；后续修订会单独注明。

[总目录](README.md#按周阅读) · [上一周](week-8.md) · [下一周](week-10.md)

<a id="contents"></a>

## 本周目录

- [本周计划与进度](#plan)
- [Day 57：Agent Center 架构入门](#day57)
- [Day 58：LangGraph 的 State、Node、Edge](#day58)
- [Day 59：第一个任务规划 Agent](#day59)
- [Day 60：任务状态保存与重启恢复](#day60)
- [Day 61：销售跟进分析 Agent 场景设计](#day61)
- [Day 62：销售跟进分析 Agent Prompt](#day62)
- [Day 63：Agent Center v0.1 发布准备与验收](#day63)
- [Agent Center v0.1.0 版本说明](#agent-center-v0.1)
- [本周总结（阶段记录）](#summary)

---

<a id="plan"></a>

## 本周计划与进度

本周主题：先画状态图，再写代码。目标是在明确边界下完成任务规划、状态保存和 Agent Center v0.1 的阶段交付。

起点：Day 55–56 成果已合并到 `main`，基线提交 `0499806`。Workflow Center v1.0.0 仍为发布候选；视频延期补录不阻塞本周学习。现有 FastAPI、RAG 和 n8n 服务继续按原方式运行。

<a id="plan-每日顺序与验收依据"></a>

### 每日顺序与验收依据

| 日期 | 原计划主题 | 本项目实施范围 | 可核对的完成依据 | 状态 |
| --- | --- | --- | --- | --- |
| Day 57 | 学习 Agent 架构 | 职责、循环、状态、停止条件和静态推演 | 能说明下一步如何选、证据不足为何不能算成功 | 设计完成 |
| Day 58 | 学习 LangGraph | 理解 State、Node、Edge；固定输入和模拟节点的最小图 | 图可运行；条件边和结束分支可复现；记录依赖兼容性 | [实验完成](#day58) |
| Day 59 | 创建第一个 Agent | 简单任务规划，校验结构化计划；验证当前模型适配 | 明确目标能产生有效计划；缺少目标或非法输出有明确处理 | [规划实验与 Qwen 验证完成](#day59) |
| Day 60 | 状态管理 | 保存任务进度；明确任务、线程和检查点的关系 | 进程重启后的恢复实验；不把仅内存保存当作持久化 | [SQLite 检查点与异常退出恢复完成](#day60) |
| Day 61 | 设计企业 Agent 场景 | 选择销售跟进分析场景，明确输入、资料和输出边界 | 场景说明、数据契约、正常与失败样例 | [场景设计与离线规则验收完成](#day61) |
| Day 62 | 编写 Agent Prompt | 角色、结构化输出、证据与终止约束 | 固定样例可重复检查；仅输出计划与结论，不要求内部思维过程 | [Prompt、离线校验与 Qwen 验证完成](#day62) |
| Day 63 | 发布 Agent Center v0.1 | 汇总实际实现和验证结果，冻结阶段范围 | 运行说明、测试证据、版本清单、限制和 Week 9 总结 | [候选验收完成；内容已定版；远端发布单独核实](#day63) |

Day 57 的制度问答用于教学推演，不提前锁定 Day 61 的业务场景。Day 58 的固定节点图也不等于已经接入模型的 Agent。

<a id="plan-实施边界"></a>

### 实施边界

首周围绕规划和任务状态完成最小闭环，工具结果可以采用明确标记的模拟数据。原路线中的真实 Tool Calling、SQLTool、KnowledgeTool 和 APITool 分别属于 Week 10；MCP 与记忆机制继续按后续阶段推进。

拟议的只读工具接口、预算和状态字段见 [Day 57 架构](#day57)，实施时可以根据实验调整，并同步更新文档。现有配置自检只检查格式，不能替代结构化模型输出和工具调用的真实能力验证。

<a id="plan-本周交付规则"></a>

### 本周交付规则

1. 每一步标清“设计、模拟、真实执行”三种证据，不能用静态 JSON 证明服务已经运行。
2. 检查点记录至少关联任务、当前进度和已确认的结果；日志仅用于诊断，不替代恢复状态。
3. 保留失败原因、剩余额度和未完成项，避免把超时或无证据回答记为成功。
4. Day 63 按实际通过的范围发布，不提前宣称已具备 Week 10 的真实工具组合能力。

本周总结见 [Week 9 总结](#summary)，组件范围见 [Agent Center v0.1.0 版本说明](#agent-center-v0.1)。内容定版完成不等于组件标签或 GitHub Release 已发布。

<a id="plan-独立待办"></a>

### 独立待办

- Day 55 本轮真实业务 Demo、视频录制和验收之后补齐。
- Workflow Center v1.0.0 的标签与 GitHub Release 仍待正式发布；合并到 main 不等于已发布。
- 企业微信真实发送仍受现有环境条件限制，销售通知保持 preview。

这些状态以 [Workflow Center 候选说明](week-8.md#workflow-center-v1.0)和后续实际验收记录为准，不随 Agent 学习进度自动变为完成。

---

<a id="days"></a>

## 每日实施记录

<a id="day57"></a>

<a id="days-day-57agent-center-架构入门"></a>

## Day 57：Agent Center 架构入门


日期：2026-09-17。交付状态：架构设计与静态推演完成，Agent 运行时尚未实现。

本日对应原计划的 `User → Agent → Planning → Tool → Result → Answer`。目标是理解各环节的职责、状态如何变化，以及任务何时结束。Day 58 再学习 LangGraph 的 State、Node、Edge；完整安排见 [Week 9 计划](#plan)。

<a id="day57-1-agent-与现有工作流的区别"></a>

<a id="days-1-agent-与现有工作流的区别"></a>

### 1. Agent 与现有工作流的区别

固定工作流由代码预先规定路径，Agent 则允许模型根据当前目标和观察结果选择后续行动。两者都可以包含模型和工具；是否调用 LLM 不是判断依据。[LangGraph 官方说明](https://docs.langchain.com/oss/python/langgraph/workflows-agents)对这两类控制方式作了区分。

| 项目中的方式 | 谁决定下一步 | 适用情况 |
| --- | --- | --- |
| 当前 RAG | 服务代码固定执行检索、构造 Prompt、回答 | 一次检索即可支持的问题 |
| 当前 n8n 销售流程 | 预设节点与条件分支 | 分析、保存 CRM、通知预览等明确业务流程 |
| 拟建 Agent Center | 模型提出行动，程序校验并执行，再根据观察继续或结束 | 步骤无法完全预先确定、需要补充信息的任务 |

先选择能够满足需求的简单方案，再考虑动态决策；增加 Agent 循环也会增加成本、延迟与验证难度。这一取舍参考 [Anthropic 的 Agent 构建建议](https://www.anthropic.com/engineering/building-effective-agents)。本页后续字段、限额和阶段划分均为本项目设计提案。

<a id="day57-2-六个环节分别做什么"></a>

<a id="days-2-六个环节分别做什么"></a>

### 2. 六个环节分别做什么

| 环节 | 输入 | 可检查的输出 |
| --- | --- | --- |
| User | 目标、必要背景、限制 | 原始任务；缺少关键信息时提出具体问题 |
| Agent | 任务、当前状态、可用工具、剩余额度 | 协调规划、执行、观察和结束 |
| Planning | 用户目标与已有证据 | 简短任务列表、完成条件、下一项行动 |
| Tool | 经程序校验的工具名称和参数 | 结构化结果或明确错误 |
| Result / Observation | 工具返回值 | 来源、证据覆盖情况、错误与待补信息 |
| Answer | 已确认事实、完成情况和限制 | 回答、来源、未完成项及结束原因 |

Planning 保存的是用户可读的步骤和进度，不要求记录模型内部思维过程。Tool Result 是待核对的数据，不能作为新的系统指令。Agent 必须区分“工具返回成功”和“用户任务已完成”。

例如，搜索成功但返回空列表，只说明调用正常结束；问题仍然缺少证据。模型生成了流畅回答，也不能替代来源核对。

<a id="day57-3-控制流设计"></a>

<a id="days-3-控制流设计"></a>

### 3. 控制流设计

```mermaid
flowchart TD
    U[接收用户任务] --> P[规划或更新下一步]
    P --> G{程序检查行动与剩余额度}
    G -->|需要用户信息| W[等待补充]
    W -->|收到补充并重新校验| P
    G -->|合法工具行动| T[执行已注册工具]
    T --> O[保存结果或错误及来源]
    O --> E{评估覆盖情况}
    E -->|还需证据且可继续| P
    E -->|所有完成条件满足| A[生成有依据的回答]
    G -->|请求结束| E
    G -->|额度耗尽或无法继续| I[返回部分结果与未完成项]
    E -->|证据不足且无法继续| I
    E -->|不可恢复执行错误| F[返回失败原因]
    A --> S[成功结束]
```

图中程序检查贯穿整个循环；任意执行阶段都要处理截止时间和取消。缺少字段可等待用户补充；工具超时不等同于成功，也不能在未计数的情况下无限重试。

建议的首批停止条件：

- 所有任务项均有充分证据支持：`succeeded`。
- 资料不存在、重复查询没有新增证据或额度耗尽：`incomplete`，明确哪些部分无法回答。
- 必要输入缺失：`waiting_for_input`，给出具体待补字段。
- 工具或系统出现不可恢复错误：`failed`，保留已有观察结果。
- 用户取消：`cancelled`，停止发起新行动；对已开始的调用记录其实际结局。

是否完成应依据任务项、证据引用及输出契约检查；模型的 `done` 建议本身不足以证明事实正确。开放式问题的质量仍需后续评测。

<a id="day57-4-状态草案"></a>

<a id="days-4-状态草案"></a>

### 4. 状态草案

以下为概念字段，不是现有 API、数据库表或正式 JSON Schema。

| 字段 | 用途 |
| --- | --- |
| `task_id` | 一次任务的稳定标识 |
| `user_request` | 用户原始目标；补充输入另行保存 |
| `status` | `pending / running / waiting_for_input / succeeded / incomplete / failed / cancelled` |
| `phase` | 当前环节：`planning / tool / evaluating / finalizing`；未开始或结束时可为空 |
| `plan` | 步骤 ID、目标、完成条件、当前状态 |
| `observations` | 工具调用 ID、结果、错误、来源与关联步骤 |
| `limits`、`usage` | 允许的额度与已用额度 |
| `answer`、`stop_reason` | 最终回答、未完成项与结束原因 |

生命周期为 `pending → running → 终态`，或 `running → waiting_for_input → running`；等待期间也可以取消。终态不直接恢复为 running，重做任务应创建新任务并关联原任务。进程中断后的恢复依据检查点继续同一未结束任务，不能把缺失结果当作成功。

`status` 表示任务整体进度，`phase` 表示当前在做什么；“正在调用工具”不是一个新的任务状态。`tool_call_id` 标识一次尝试，失败重试使用新的调用 ID。

拟议预算为每次任务最多 **4 次决策、4 次工具尝试、60 秒活动执行时间**，仅用于讨论，尚未成为运行配置。初次规划、重新选择行动和决定结束都计入决策次数；失败和重试也消耗工具尝试额度。等待用户不消耗活动执行时间，但恢复时需重新检查剩余额度、来源有效性与待执行行动。Day 60 再确定可持久化的计时与恢复规则。

“没有新增证据”指同一规范化工具参数再次返回相同来源和内容；正常返回本身不构成进展。即使还有额度，也应停止重复空转。工具超时且无法恢复优先记为 `failed`；单纯用完总额度仍有未完成项则记为 `incomplete`。

LangGraph 可以用检查点保存图状态，并用 `thread_id` 关联执行历史；内存检查点不等于进程重启后仍可恢复。[官方持久化文档](https://docs.langchain.com/oss/python/langgraph/persistence)区分了线程内检查点和跨线程存储。本项目将在 Day 60 决定任务 ID 与图线程 ID 的映射、存储实现和恢复测试，今天不承诺持久化已完成。

<a id="day57-5-工具边界与现有代码衔接"></a>

<a id="days-5-工具边界与现有代码衔接"></a>

### 5. 工具边界与现有代码衔接

模型只能提出已注册工具及参数，程序负责校验名称、参数类型、额度和结果大小。未知工具不执行；返回资料中的“忽略规则”“发送消息”等文字按资料内容处理，不能增加工具权限。

静态案例使用概念工具 `search_knowledge(query, top_k)`，结果包含 `evidence_id`、`source` 和 `text`。这些字段用于教学，不是已上线工具协议；案例证据 ID 也不是 Chroma 实际 chunk ID。

| 现有入口 | 可复用部分 | 后续需要补齐的部分 |
| --- | --- | --- |
| [retrieval_service.py](../backend/app/services/retrieval_service.py) | `search_chunks(question, top_k=3)` 返回片段、来源、chunk ID 与距离 | 工具适配、参数限制、结果截断、错误和证据映射；计划 Week 10 接入 |
| [settings.py](../backend/app/settings.py) | DeepSeek / Qwen 配置读取与校验 | 在实际模型上验证结构化决策或工具调用能力；配置有效不代表能力已经验证 |
| [llm_service.py](../backend/app/services/llm_service.py) | 兼容客户端调用方式的参考 | 当前 `generate_grounded_answer` 使用固定 RAG Prompt，不能直接当作通用规划器 |
| [workflow.py](../backend/app/models/workflow.py) | 状态字段、运行关联的设计经验 | 现有模型围绕 n8n 运行和 `n8n_execution_id`；不要给 Agent 伪造 n8n 执行号 |
| [workflow_logging.py](../backend/app/workflow_logging.py) | 脱敏快照、耗时和错误分类经验 | 当前边界日志不能替代 Agent 状态检查点，也不是完整 Agent 轨迹 |

这里“只读知识查询”指不修改业务记录、不发送通知；现有 Chroma 检索入口可能初始化本地存储或缓存，并不保证文件系统零写入。首次实验将使用固定返回值，避免把检索环境准备混进图运行机制的学习。

现有 FastAPI 没有 Agent 路由，依赖中尚无 LangGraph。LangGraph 是待验证的有状态编排方案，不要求必须同时采用 LangChain；见 [官方概览](https://docs.langchain.com/oss/python/langgraph/overview)。Day 58 再验证与当前 Python 环境的兼容性并选择依赖版本。

<a id="day57-6-静态任务推演"></a>

<a id="days-6-静态任务推演"></a>

### 6. 静态任务推演

示例问题：“星云科技发生 P1 级故障时，响应和升级流程是什么？差旅报销 8000 元需要哪些人审批？”

| 步骤 | 拟议行动 | 示例观察 | 下一步判断 |
| --- | --- | --- | --- |
| S1 | 查询 IT 制度 | 15 分钟首次响应、4 小时目标恢复；30 分钟未响应升级；应急群与提交信息 | IT 子任务证据齐全，继续报销问题 |
| S2 | 查询差旅制度 | 超过 3000 元且不超过 10000 元，由部门负责人和财务负责人共同审批 | 8000 元命中该档位，两个子任务均可回答 |
| 汇总 | 组织回答与来源 | 保留阈值、时间条件及引用 | 结束，不查询 CRM、不发送消息 |

可阅读 [静态 JSON](../demo/agent-center/day57-task-walkthrough.json) 和 [字段说明](../demo/agent-center/README.md)。材料来自仓库中的虚构制度，观察结果和决策均为人工编写，未调用模型、工具或真实检索。该问题也可以用现有 RAG 处理；拆成两步是为了学习控制流，不是 Agent 效果优于 RAG 的证据。

<a id="day57-7-后续实现需要验证的分支"></a>

<a id="days-7-后续实现需要验证的分支"></a>

### 7. 后续实现需要验证的分支

以下是验收场景设计，今天没有运行 Agent 测试。

| 输入或事件 | 预期行为 |
| --- | --- |
| “帮我处理一下”且没有明确目标 | 等待用户说明任务，不猜测要修改哪个系统 |
| 检索成功但无相关制度 | 可以在预算内调整查询；仍无依据则返回未完成项，不编造规定 |
| 工具超时 | 记录失败尝试；仅在工具语义允许时做有限重试，不能默认成功 |
| 模型提出未注册工具或非法参数 | 拒绝执行，记录原因；如重新决策则消耗额度，不能无限纠错 |
| 总额度耗尽或重复观察无进展 | `incomplete`，返回已有结论与缺口 |
| 文档片段包含要求调用通知接口的文字 | 当作不可信资料，不改变任务或工具权限 |
| 最终回答没有覆盖报销问题，或引用不存在 | 不得标记成功，修正或明确部分完成 |

<a id="day57-8-今日交付与完成标准"></a>

<a id="days-8-今日交付与完成标准"></a>

### 8. 今日交付与完成标准

- 已整理架构职责、动态决策循环、任务状态和停止条件。
- 已提供可追溯到虚构原始制度的静态推演，以及 Week 9 实施顺序。
- 验证范围为文档链接、JSON 一致性和证据文本，不包含模型效果、真实工具调用、持久化恢复或端到端 Agent 验收。

Day 57 不新增 Agent 接口、不安装 LangGraph、不调整数据库或容器。下一步是 Day 58 的最小状态图实验。Day 55 视频补录与 Workflow Center v1.0.0 正式发布仍按 [候选说明](week-8.md#workflow-center-v1.0)独立收尾。

---

<a id="day58"></a>

<a id="days-day-58langgraph-的-statenodeedge"></a>

## Day 58：LangGraph 的 State、Node、Edge


日期：2026-09-17。已完成最小状态图、五种模拟场景和本地测试。LangGraph 实际参与执行；规划与工具结果仍是固定教学数据，尚未接入模型 Agent。

<a id="day58-1-三个概念与今天的代码"></a>

<a id="days-1-三个概念与今天的代码"></a>

### 1. 三个概念与今天的代码

| 概念 | 通俗理解 | 本实验中的实现 |
| --- | --- | --- |
| State | 流程共享的进度记录 | `DemoState`：问题、计划、已完成步骤、观察、次数、回答与轨迹 |
| Node | 执行一步工作的函数 | `prepare`、`mock_lookup`、`evaluate`、`finish` |
| Edge | 决定下一步走到哪里 | 固定边连接查找与评估；条件边选择继续查找或结束 |

StateGraph 需要先编译再运行；节点返回状态的局部更新，边决定后续路径。`TypedDict` 描述字段类型，本身不是外部输入的运行时校验器。以上基础概念参考 [LangGraph Graph API 官方文档](https://docs.langchain.com/oss/python/langgraph/graph-api)，下方控制流程为本项目实验设计。

代码入口：[langgraph_basics.py](../experiments/day58/langgraph_basics.py)。

```mermaid
flowchart TD
    Start[START] --> P[prepare：固定计划]
    P -->|输入缺失或没有额度| F[finish：汇总结果]
    P -->|可以继续| T[mock_lookup：模拟查询]
    T --> E[evaluate：检查观察结果]
    E -->|还有任务和额度| T
    E -->|完成、缺资料、错误或额度耗尽| F
    F --> Stop[END]
```

从实际图导出的结构见 [graph.mmd](../experiments/day58/graph.mmd)。图中的条件判断由 Python 函数完成，不是模型动态决策。

<a id="day58-2-节点怎样更新-state"></a>

<a id="days-2-节点怎样更新-state"></a>

### 2. 节点怎样更新 State

`prepare` 为预设制度问答创建 `S1`（P1 故障）与 `S2`（8000 元报销）两步计划。`mock_lookup` 按步骤返回 Day 57 静态证据 ID；`evaluate` 检查结果并推进 `next_step`；`finish` 汇总已有证据、来源和未完成项。

普通字段的更新替换原值，例如 `attempts` 从 0 改为 1。`trace`、`observations` 和 `completed_steps` 使用 `Annotated[..., operator.add]` 追加，因此节点只返回新增记录，不把整个旧列表再次返回。Reducer 的合并规则见 [官方说明](https://docs.langchain.com/oss/python/langgraph/graph-api#reducers)。

成功场景的轨迹是：

```text
prepare → mock_lookup → evaluate → mock_lookup → evaluate → finish
```

两个观察会保留下来，完成步骤依次为 `S1`、`S2`。最后回答直接整理固定证据，不调用 LLM，也不声称验证了开放式回答质量。

<a id="day58-3-五个可重复场景"></a>

<a id="days-3-五个可重复场景"></a>

### 3. 五个可重复场景

| `--case` | 条件 | 预期状态 | 模拟查询次数 |
| --- | --- | --- | --- |
| `success` | 两步均有固定证据 | `succeeded` | 2 |
| `missing-input` | 问题为空 | `waiting_for_input` | 0 |
| `empty-result` | 第二步返回空列表 | `incomplete`，保留第一步回答 | 2 |
| `tool-error` | 第二步返回模拟错误 | `failed`，保留第一步回答 | 2 |
| `budget-limit` | 最多允许一次模拟查询 | `incomplete`，第二步未执行 | 1 |

`route_next` 在第一次查询前和每次评估后检查状态、剩余步骤及次数。实验不会自动重试空结果或错误，也不会重复执行已经完成的步骤。这里最多两次模拟查询是实验约束，未实现 Day 57 提案中的完整决策预算或执行截止时间。

图调用还设置了 `recursion_limit=12` 作为执行步数保护；它不是秒数或模型调用预算。测试将其降到 1，确认抛出 `GraphRecursionError`，不会被伪装成业务成功。

<a id="day58-4-独立环境与运行命令"></a>

<a id="days-4-独立环境与运行命令"></a>

### 4. 独立环境与运行命令

实测环境：Windows、Python `3.14.2`、LangGraph `1.2.11`、pytest `9.1.1`。完整版本见 [requirements-lock.txt](../experiments/day58/requirements-lock.txt)，直接依赖见 [requirements.txt](../experiments/day58/requirements.txt)。该快照在此环境通过验证，不代表其他操作系统或 Python 版本已验收。

LangGraph SDK `0.4.4` 的安装元数据要求 `websockets < 17`，本项目 API 的 [依赖文件](../requirements.txt)固定为 `17.0.1`，所以实验使用独立虚拟环境。没有修改根目录依赖、API 路由或 Compose，容器不需要重建。

以下命令从仓库根目录执行。首次创建环境与安装依赖：

```powershell
Set-Location 'C:\Users\Administrator\Desktop\enterprise-ai-platform'

& .\.venv\Scripts\python.exe -m venv .\experiments\day58\.venv
if ($LASTEXITCODE -ne 0) { throw 'Day 58 environment creation failed' }

& .\experiments\day58\.venv\Scripts\python.exe -m pip install -r .\experiments\day58\requirements-lock.txt
if ($LASTEXITCODE -ne 0) { throw 'Day 58 dependency installation failed' }

& .\experiments\day58\.venv\Scripts\python.exe -m pip check
if ($LASTEXITCODE -ne 0) { throw 'Day 58 dependency check failed' }
```

以后可以直接运行，无需激活环境：

```powershell
& .\experiments\day58\.venv\Scripts\python.exe .\experiments\day58\langgraph_basics.py --case success
& .\experiments\day58\.venv\Scripts\python.exe .\experiments\day58\langgraph_basics.py --case budget-limit
& .\experiments\day58\.venv\Scripts\python.exe .\experiments\day58\langgraph_basics.py --case all
```

输出中的 `artifact_type=executed_graph_with_mock_nodes` 表示图确实执行、节点结果为模拟数据；`model_called=false`、`external_tool_called=false`、`persistent_state=false` 明确本日边界。CLI 正常退出表示实验已运行完毕，业务结果必须看 `state.status`，不能把退出码 0 直接当成任务成功。

运行测试或查看图源码：

```powershell
& .\experiments\day58\.venv\Scripts\python.exe -m pytest .\experiments\day58\test_langgraph_basics.py -q
if ($LASTEXITCODE -ne 0) { throw 'Day 58 graph tests failed' }

& .\experiments\day58\.venv\Scripts\python.exe .\experiments\day58\langgraph_basics.py --mermaid
```

`--mermaid` 只生成本地图源码，不访问在线绘图服务。独立环境目录由现有 `.gitignore` 排除；`experiments/` 已被 `.dockerignore` 排除。

<a id="day58-5-验证结果"></a>

<a id="days-5-验证结果"></a>

### 5. 验证结果

本轮完成 **14 项测试**：五类终止路径、成功回答来源与条件、三个部分结果不编造报销结论、零额度不执行查询、多次调用不串进度、递归保护、禁用环境开启的远程追踪、拒绝未知场景。

测试期间阻断 socket 连接与 DNS 查询；图入口显式关闭远程追踪，不加载项目 `.env`。还通过 `pip check`、Ruff 检查与格式检查。结构化结果见 [本轮验证记录](evidence/week-09.md#day58)。这是模拟节点的图执行验收，不包含真实检索、模型输出质量或容器验收。

根项目环境未安装 LangGraph 时，实验测试按可选依赖跳过。验收必须使用上方独立环境，核对输出为 `14 passed`，不能把 skipped 当成通过。

<a id="day58-6-下一步"></a>

<a id="days-6-下一步"></a>

### 6. 下一步

Day 59 将创建第一个简单任务规划 Agent，并验证结构化计划与当前模型的适配。Day 60 再实现任务进度保存和恢复。

本图没有 checkpointer，也没有可恢复的 interrupt。`waiting_for_input` 只是本次返回状态，之后的新调用从头运行；进程重启后恢复同一任务还未实现。Day 55 视频与 Workflow Center v1.0.0 正式发布继续保留为独立待办，见 [Week 9 计划](#plan)。

---

<a id="day59"></a>

<a id="days-day-59第一个任务规划-agent"></a>

## Day 59：第一个任务规划 Agent


日期：2026-09-20。已实现独立规划实验，完成离线测试及当前 Qwen 模型的两次真实验证。

Day 58 的计划固定在 Python 中；Day 59 将用户目标交给模型，接收模型选择的步骤与依赖，再由程序校验。LangGraph 继续负责执行顺序和状态更新。这是规划型 Agent 的最小闭环，还没有任务执行、工具调用或自主反复规划。

<a id="day59-1-流程与状态"></a>

<a id="days-1-流程与状态"></a>

### 1. 流程与状态

```mermaid
flowchart TD
    S[START] --> I[validate_input：检查目标]
    I -->|有效| M[generate_plan：一次模型请求]
    I -->|空目标或超长| F[finish：返回结果]
    M -->|请求成功| V[validate_plan：校验 JSON 与步骤]
    M -->|配置或请求失败| F
    V --> F
    F --> E[END]
```

实际导出的图见 [graph.mmd](../experiments/day59/graph.mmd)。本图的路由判断仍由程序定义，模型负责生成计划内容和决定是否需要澄清。

| 返回状态 | 含义 | 后续动作 |
| --- | --- | --- |
| `planned` | 结构化计划通过本地检查 | 阅读并评估计划；本日不自动执行 |
| `waiting_for_input` | 缺少目标或模型提出具体问题 | 补齐目标后重新调用 |
| `failed` | 输入不合法、配置错误、请求失败或输出不合格 | 根据 `stop_reason` 排查；没有自动重试 |

结果总是包含 `task_executed=false`、`tools_executed=false`、`persistent_state=false`。`planning_attempts` 是规划函数调用次数；`model_requests` 是 HTTP 请求尝试次数，网络失败也计入尝试。Mock 响应模式为 0 次真实请求。

<a id="day59-2-计划契约"></a>

<a id="days-2-计划契约"></a>

### 2. 计划契约

[PlanDecision](../experiments/day59/plan_schema.py)包含 `decision`、`summary`、`steps`、`questions`。字段 Schema 可查看 [plan-schema.json](../experiments/day59/plan-schema.json)。

每个步骤必须包含：

| 字段 | 含义 |
| --- | --- |
| `id` | 按顺序使用 S1、S2 等，最多 S5 |
| `action` | `retrieve` 获取资料、`analyze` 分析、`summarize` 汇总 |
| `description` | 需要做什么 |
| `expected_output` | 怎样检查这一步完成 |
| `depends_on` | 依赖哪些较早步骤，无依赖时为 `[]` |

程序拒绝未知字段、未知 action、空或超长文本、错误类型、重复 ID、前向/自身依赖、重复依赖、重复 JSON 键、非标准 JSON 数值、Markdown 围栏及超长响应。字段文本最多 300 字符，原始模型内容最多 16000 字符，用户目标最多 2000 字符。

`decision=plan` 必须有 1–5 步，questions 为空；`decision=clarify` 必须没有步骤，并提出 1–3 个问题。跨字段关系由 Python 校验器检查，导出的 JSON Schema 不能单独表达全部约束。

这些检查证明格式和依赖关系符合约定，不证明计划内容正确、资料真实存在或用户目标被完整理解。`retrieve` 等只是计划分类，没有映射到可执行工具，也不执行模型生成的代码或命令。

<a id="day59-3-模型与配置"></a>

<a id="days-3-模型与配置"></a>

### 3. 模型与配置

实验通过 HTTPX 访问现有配置对应的 `/chat/completions`，复用 [settings.py](../backend/app/settings.py)的 `load_environment()` 与 `get_llm_config()`。不复用固定 RAG Prompt，也不改动 API 配置或业务服务。

请求使用 `response_format={"type":"json_object"}`，Prompt 提供 Schema、JSON 要求与澄清示例；Qwen 请求额外设置 `enable_thinking=false`。JSON Object 模式不保证符合业务 Schema，因此响应仍需本地校验，参见 [Qwen 官方结构化输出说明](https://help.aliyun.com/zh/model-studio/qwen-structured-output)和 [DeepSeek 官方 JSON Output 说明](https://api-docs.deepseek.com/guides/json_mode/)。

每个任务最多一次请求，输出上限 1800 Token；连接超时 10 秒，其余 HTTPX 操作超时 30 秒。这些是各网络操作超时，不是整个任务的严格 30 秒截止时间。响应体最多读取 64 KiB，拒绝重定向、非 200 状态、空响应、截断响应和意外 tool_calls。失败不自动重试，不将非法输出替换成 Mock 计划。

错误仅返回稳定错误码，不返回供应商错误正文、原始非法模型内容或密钥。远程追踪关闭，实验本身不把用户目标或计划写入文件。真实模式只将 Prompt 和本次目标发送给配置的模型服务。

<a id="day59-4-独立环境安装"></a>

<a id="days-4-独立环境安装"></a>

### 4. 独立环境安装

本次沿用 Day 58 的 LangGraph `1.2.11`，增加显式配置读取依赖；全部版本见 [requirements-lock.txt](../experiments/day59/requirements-lock.txt)。使用新的独立环境，保持 API 与 Day 58 环境各自不变。

首次安装，在 PowerShell 执行：

```powershell
$day59Root = 'C:\Users\Administrator\Desktop\enterprise-ai-platform'
$day59Dir = Join-Path $day59Root 'experiments\day59'
$day59Python = Join-Path $day59Dir '.venv\Scripts\python.exe'
$day59Script = Join-Path $day59Dir 'task_planner.py'
Set-Location -LiteralPath $day59Root

if (-not (Test-Path -LiteralPath $day59Python)) {
    & (Join-Path $day59Root '.venv\Scripts\python.exe') -m venv (Join-Path $day59Dir '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Day 59 environment creation failed' }
}
& $day59Python -m pip install -r (Join-Path $day59Dir 'requirements-lock.txt')
if ($LASTEXITCODE -ne 0) { throw 'Day 59 dependency installation failed' }
& $day59Python -m pip check
if ($LASTEXITCODE -ne 0) { throw 'Day 59 dependency check failed' }
```

安装需要联网。后续同一窗口可继续使用上面的路径变量。

<a id="day59-5-先离线再调用当前模型"></a>

<a id="days-5-先离线再调用当前模型"></a>

### 5. 先离线，再调用当前模型

默认使用人工编写的 Mock 响应，不加载 `.env`：

```powershell
& $day59Python $day59Script
& $day59Python $day59Script --mock-case clarify
& $day59Python $day59Script --mock-case invalid
& $day59Python $day59Script --mock-case provider-error
& $day59Python $day59Script --goal ' '
```

预期依次为 `planned`、`waiting_for_input`、`failed`、`failed`、`waiting_for_input`。失败场景返回退出码 1，等待和计划完成返回 0；业务状态始终看 `state.status`。Mock 模式即使传入其他目标，也只返回人工样例，不据此评价模型能力。

真实模式读取仓库 `.env`，已有进程环境变量优先。每次执行下面的命令都会请求一次当前模型并产生相应用量：

```powershell
& $day59Python $day59Script --live --goal '请制定计划：查明星云科技 P1 故障的响应和升级流程，以及单笔 8000 元差旅报销需要哪些人审批。只规划，不执行。'
```

也可以使用 `--env-file` 显式指定配置文件。不要把 API Key 放到 `--goal` 或命令行参数中。空目标在配置读取和模型调用前就被拦截；模糊但非空目标会交给模型决定是否澄清。

真实模式返回 `mode=live`、`model_requests=1`、当前 provider/model，以及计划或澄清问题。`planned` 只表示计划生成与结构校验完成，不能据此声称获得了制度答案。

<a id="day59-6-本轮验证"></a>

<a id="days-6-本轮验证"></a>

### 6. 本轮验证

离线测试命令：

```powershell
& $day59Python -m pytest (Join-Path $day59Dir 'test_task_planner.py') -q
if ($LASTEXITCODE -ne 0) { throw 'Day 59 tests failed' }
```

验收需看到全部通过且无 skipped。测试覆盖图分支、输入检查、计划依赖约束、JSON 格式、HTTP 请求契约、超时/错误/重定向/截断处理、默认离线 CLI 和远程追踪关闭；测试期间阻断 socket 连接与 DNS 查询。

本次真实验证使用当前 `qwen3.7-plus`，共两次请求：

| 虚构输入 | 实际结果 |
| --- | --- |
| P1 故障流程与 8000 元报销审批的规划任务 | `planned`，生成 4 步：分别取资料、分析、汇总；依赖关系通过校验 |
| “帮我处理一下。” | `waiting_for_input`，提出任务对象和期望结果两个问题 |

真实返回见 [live-plans.json](evidence/week-09.md#day59)，测试和源码版本记录见 [validation.json](evidence/week-09.md#day59)。两条样例是有限的适配验证，不代表所有输入或所有模型已验收。模型建议获取的文档名称没有被知识库验证，不是实际来源引用。DeepSeek 仅通过请求契约 Mock 测试，本次没有调用其真实服务。

<a id="day59-7-后续边界"></a>

<a id="days-7-后续边界"></a>

### 7. 后续边界

本日没有 Agent HTTP 路由、数据库表、检查点、自动重试或业务工具执行。需要补充信息时当前调用结束；用户提交完整目标后新开一次规划，不是恢复原任务。

Day 60 将围绕任务 ID、计划进度和持久化恢复继续实现；Week 10 再接入真实 Tool Calling。现有 API 和容器不需要重建。Day 55 视频及 Workflow Center v1.0 正式发布继续独立收尾，进度见 [Week 9 计划](#plan)。

---

<a id="day60"></a>

<a id="days-day-60任务状态保存与重启恢复"></a>

## Day 60：任务状态保存与重启恢复


Day 59 解决“模型如何生成有效计划”；Day 60 解决“任务做到哪一步，程序退出后怎样接着走”。本次保存的是计划和模拟步骤进度，SQLite 写入与独立进程恢复均已实际验证。

<a id="day60-1-本次交付与边界"></a>

<a id="days-1-本次交付与边界"></a>

### 1. 本次交付与边界

- 每次 `start` 创建唯一 UUID，用作 `task_id` 和 LangGraph `thread_id`。
- 使用原生 `SqliteSaver` 把 State、下一节点及中断信息保存到磁盘。
- 每一步开始前用 `interrupt()` 暂停；`resume` 明确确认后推进一个模拟步骤。
- 使用检查点 ID 拒绝过期的重复命令，使用进程文件锁阻止同一任务并发推进。
- 支持 `status` 查询和 `recover` 恢复异常退出时尚未完成的图执行。
- 验证真正的新进程读取、强制退出后恢复、任务隔离与完成后不重放。

步骤只记录 `simulate:S1` 等标记，不检索知识库、不发送消息、不执行模型生成的描述。最终状态是 `simulation_completed`，业务执行标记始终为 `false`。本次没有新模型请求，不读取 `.env`，不重建 API 容器。

<a id="day60-2-三个-id-与状态"></a>

<a id="days-2-三个-id-与状态"></a>

### 2. 三个 ID 与状态

| 字段 | 含义 | 是否变化 |
| --- | --- | --- |
| `task_id` | 本地任务身份，用于找到对应 SQLite 文件 | 同一任务不变 |
| `thread_id` | LangGraph 查找同一条执行历史的标识 | 本实验等于 task_id |
| `checkpoint_id` | 原生检查点版本；不是步骤编号 | 图写入新检查点后变化 |
| `progress.simulated` | 已记录的模拟步骤数 | 每次有效推进增加 1 |
| `phase` | initializing / paused / recoverable / finished | 取决于检查点和下一节点 |
| `status` | planned / running / simulation_completed / failed | 业务层实验状态 |
| `graph_version` | 本地状态格式版本，当前为 1 | 不兼容版本直接拒绝 |

`status=running` 与 `phase=paused` 可以同时出现：任务尚未完成，但图在等待下一次确认。`checkpoint_id` 在初始元数据已经保存、图尚未启动时可为空。

检查点按线程保存执行快照；跨线程长期记忆是另一项能力，本次未实现。参见 [LangGraph 持久化说明](https://docs.langchain.com/oss/python/langgraph/persistence)。

```mermaid
flowchart LR
    A[有效计划] --> B[创建任务与 SQLite 文件]
    B --> C[步骤前 interrupt 暂停]
    C -->|resume + 当前 checkpoint_id| D[记录一个模拟步骤]
    D -->|还有步骤| C
    D -->|全部完成| E[simulation_completed]
    F[新进程 status / recover] --> G[用同一 task_id 读取检查点]
    G --> C
```

实际图导出见 [graph.mmd](../experiments/day60/graph.mmd)。代码使用 `durability="sync"`，在进入下一步前同步保存检查点。`interrupt()` 恢复时会重新进入所在节点，因此暂停之前不放业务副作用。参见 [LangGraph 中断与恢复说明](https://docs.langchain.com/oss/python/langgraph/interrupts)。

<a id="day60-3-安装独立环境"></a>

<a id="days-3-安装独立环境"></a>

### 3. 安装独立环境

在 PowerShell 执行；如果已由本次开发配置好 Day 60 环境，可从第 4 节开始。

```powershell
Set-Location 'C:\Users\Administrator\Desktop\enterprise-ai-platform'
if (-not (Test-Path '.\experiments\day60\.venv\Scripts\python.exe')) {
    & .\.venv\Scripts\python.exe -m venv .\experiments\day60\.venv
    if ($LASTEXITCODE -ne 0) { throw '创建 Day 60 环境失败' }
}
$py = '.\experiments\day60\.venv\Scripts\python.exe'
& $py -m pip install -r .\experiments\day60\requirements-lock.txt
if ($LASTEXITCODE -ne 0) { throw '安装 Day 60 依赖失败' }
& $py -m pip check
if ($LASTEXITCODE -ne 0) { throw '依赖检查失败' }
```

使用 Python 3.14.2、LangGraph 1.2.11、SQLite checkpointer 3.1.1 和 filelock 3.32.3。完整环境见 [依赖快照](../experiments/day60/requirements-lock.txt)。Day 58 的 SDK 与 API 的 websockets 固定版本存在冲突，继续使用独立环境，不改根目录 requirements。

<a id="day60-4-创建任务并推进第一步"></a>

<a id="days-4-创建任务并推进第一步"></a>

### 4. 创建任务并推进第一步

默认使用 Day 59 的三步固定计划，方便离线复现。下面封装函数只负责执行命令、检查退出码并解析 JSON，不会自行推进任务。

```powershell
Set-Location 'C:\Users\Administrator\Desktop\enterprise-ai-platform'
$env:PYTHONIOENCODING = 'utf-8'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$py = '.\experiments\day60\.venv\Scripts\python.exe'
$script = '.\experiments\day60\task_progress.py'
function Invoke-Day60 {
    $raw = & $py $script @args
    if ($LASTEXITCODE -ne 0) { throw ($raw -join "`n") }
    return ($raw -join "`n" | ConvertFrom-Json)
}
$task = Invoke-Day60 start
$taskId = $task.task_id
$task | ConvertTo-Json -Depth 20
Write-Host "保存此任务 ID：$taskId"
```

预期：`phase=paused`、`status=planned`、进度 `0/3`。保存输出的真实 task_id，后续命令复用它。再次 `start` 会创建新任务，不是恢复旧任务。

```powershell
$firstCheckpoint = $task.checkpoint_id
$task = Invoke-Day60 resume --task-id $taskId --checkpoint-id $firstCheckpoint
$task | ConvertTo-Json -Depth 20
```

预期：进度 `1/3`、`phase=paused`。SQLite 中已经保存 S1 的模拟进度；下一次准备推进 S2。

<a id="day60-5-关闭-powershell-后继续同一任务"></a>

<a id="days-5-关闭-powershell-后继续同一任务"></a>

### 5. 关闭 PowerShell 后继续同一任务

关闭窗口再打开，重新执行第 4 节中 `Set-Location` 到函数定义结束的初始化部分，**不要重复执行 start**。将下方字符串替换成刚才保存的真实 UUID。

```powershell
$taskId = '替换为之前保存的任务 UUID'
$task = Invoke-Day60 status --task-id $taskId
$task | ConvertTo-Json -Depth 20
```

预期仍为 `1/3`，task_id、计划、trace 与关闭前一致。`status` 不推进任务，也不新增图检查点。

确认当前状态后，执行一次推进命令：

```powershell
$task = Invoke-Day60 resume --task-id $taskId --checkpoint-id $task.checkpoint_id
$task | ConvertTo-Json -Depth 20
```

预期为 `2/3`。再执行一次相同形式命令，使用更新后的 `$task.checkpoint_id`，得到 `3/3`、`phase=finished`、`status=simulation_completed`。

这里每条 CLI 本来就启动独立 Python 进程；关闭窗口是便于人工感知的附加演示。最终 trace 中 S1、S2、S3 各出现一次 `simulate`，没有真实工具结果。

<a id="day60-6-重复命令和异常退出"></a>

<a id="days-6-重复命令和异常退出"></a>

### 6. 重复命令和异常退出

在任务未完成时，重复使用已经消费的检查点 ID 会返回 `stale_checkpoint`，进度不变化。先 `status` 查看真实进度，再决定是否推进下一步；不要自动拿新 ID 无限重试。

如果进程在执行过程中异常退出，先查询：

```powershell
$task = Invoke-Day60 status --task-id $taskId
$task | ConvertTo-Json -Depth 20
$task = Invoke-Day60 recover --task-id $taskId
$task | ConvertTo-Json -Depth 20
```

| 查询阶段 | recover 的行为 |
| --- | --- |
| `initializing` | 从已提交的任务元数据启动图，停在第一步之前 |
| `recoverable` | 从持久化的下一节点继续，直到下一次暂停或结束 |
| `paused` | 保持原状；不会代替用户确认下一步 |
| `finished` | 返回原结果；不会重放任务 |

`resume` 遇到非暂停的未完成状态会返回 `use_recover`。同一任务正在被其他命令访问时返回 `task_busy`；等待原进程结束后重新查询。`.lock` 文件存在不代表锁仍被持有，进程退出后操作系统释放锁，不要靠删除锁文件处理并发。

自动化测试在 S1 已提交后，让另一个进程在 S2 返回状态更新前调用 `os._exit(77)`；新进程读到 `1/3` 和 `recoverable`，恢复后得到 `2/3`，最后完成 S3。测试在临时目录运行，不结束用户服务进程。

尚未提交的节点计算可能重跑。这次节点是纯模拟，没有外部副作用；将来接真实 API、付款或通知时仍需独立的幂等键和结果核对，检查点不能保证外部动作恰好执行一次。测试验证进程退出恢复，没有模拟磁盘损坏、断电或多机切换。

<a id="day60-7-衔接-day-59-保存的计划"></a>

<a id="days-7-衔接-day-59-保存的计划"></a>

### 7. 衔接 Day 59 保存的计划

`--plan-file` 接受直接的 PlanDecision JSON，或 Day 59 CLI 输出的 `task_planning_result`，其中 `state.status` 必须为 `planned`。澄清、失败和非法计划均拒绝创建任务。

下面从已有 Qwen 验证记录提取有效计划，不会再次调用模型：

```powershell
$history = Get-Content '.\docs\evidence\day59\live-plans.json' -Raw -Encoding UTF8 | ConvertFrom-Json
$planFile = Join-Path $env:TEMP ('day60-plan-' + [guid]::NewGuid().ToString() + '.json')
$history[0].result | ConvertTo-Json -Depth 30 | Set-Content $planFile -Encoding UTF8
$task = Invoke-Day60 start --plan-file $planFile
$taskId = $task.task_id
$task | ConvertTo-Json -Depth 20
```

该已保存计划包含四步，初始进度为 `0/4`。复用第 5 节推进命令逐步到 `4/4`。完整 live-plans 文件是多条记录组成的数组，不能直接当作单个计划输入。

<a id="day60-8-数据位置与维护边界"></a>

<a id="days-8-数据位置与维护边界"></a>

### 8. 数据位置与维护边界

默认一个任务对应 `data/day60/<task_id>.sqlite`，其中包含应用元数据和 LangGraph 原生 checkpoints/writes 表。SQLite 可能产生 WAL/SHM 辅助文件；整个目录已被 Git 忽略，与现有平台业务数据库分开。

自定义目录示例：`& $py $script --store-dir 'D:\agent-state' start`。之后所有 status/resume/recover 都必须使用同一目录，否则报 `task_not_found`。错误 ID 不会创建空数据库。

数据库明文包含计划及检查点，仅供可信本地用户使用，没有账号权限、加密、清理保留策略或多机调度。不要把密钥写入计划或导入不可信数据库。备份需采用 SQLite 一致性备份，或全部相关进程关闭后处理完整文件集；仅复制正在写入的主文件不可靠。

状态格式版本不匹配返回 `incompatible_task`；不自动覆盖或迁移旧数据。若进程在新建空文件和提交任务元数据之间退出，该文件还不是可恢复任务；重新 start 创建新任务，保留原文件供检查。

<a id="day60-9-验证与下一步"></a>

<a id="days-9-验证与下一步"></a>

### 9. 验证与下一步

```powershell
& $py -m pytest .\experiments\day60\test_task_progress.py .\experiments\day59\test_task_planner.py .\experiments\day58\test_langgraph_basics.py -q
if ($LASTEXITCODE -ne 0) { throw 'Agent 实验测试失败' }
```

本次 23 项 Day 60 测试及 63 项 Day 58–59 回归测试通过，共 86 项。验证记录见 [validation.json](evidence/week-09.md#day60)，独立进程与异常恢复样例见 [process-recovery.json](evidence/week-09.md#day60)。API 环境缺少独立实验依赖时测试跳过，不计为通过；本次未重跑完整 API 套件或 Docker 验收。

Day 61 继续设计企业 Agent 场景；真实工具调用仍按 Week 10 计划推进。Day 55 视频补录和 Workflow Center v1.0.0 发布候选的待办继续保留。

---

<a id="day61"></a>

<a id="days-day-61销售跟进分析-agent-场景设计"></a>

## Day 61：销售跟进分析 Agent 场景设计


<a id="day61-1-目标与完成范围"></a>

<a id="days-1-目标与完成范围"></a>

### 1. 目标与完成范围

目标：针对明确的客户列表和日期范围，依据已有跟进记录整理“哪些客户需要人工复核、补充信息、优先跟进或常规跟进”，同时返回来源和资料缺口。

示例任务：“整理客户 C-001、C-002 在 2026-09-14 至 2026-09-20 的跟进建议，说明依据和待补信息。”客户和资料均为虚构样例，不代表真实业务结论。

Day 57–60 已验证架构、状态图、模型规划和进度保存；Day 61 增加业务场景、数据契约、确定性验收规则及 13 个虚构样例。代码用于验证设计，可以直接运行；本日没有接入新的模型 Prompt、CRM 查询工具或 Agent 运行循环。

<a id="day61-2-用户用途与权限边界"></a>

<a id="days-2-用户用途与权限边界"></a>

### 2. 用户、用途与权限边界

使用者为销售人员或负责人，输出用于准备人工跟进清单。客户范围必须由用户明确提供，最多 20 个客户；“本周”“全部客户”“帮我处理一下”等表达应由后续交互补成确定日期和客户 ID，当前校验器不解析自然语言，也不自动读取电脑日期。

本场景不计算收入、赢单概率、销售预测或客户价值评分，因为现有 CRM 缺少足够的结构化依据。已有 `high/normal` 表示来源记录中的优先级，不代表本日新推断的成交可能性。

建议仅返回给用户查看，不更新 CRM，不自动解除复核标记，不创建跟进记录，不发送飞书或企业微信消息。指定客户 ID 只是业务范围，不是权限凭证；未来真实工具必须在服务端验证访问权限。

<a id="day61-3-输入契约"></a>

<a id="days-3-输入契约"></a>

### 3. 输入契约

定义见 [sales_contract.py](../experiments/day61/sales_contract.py) 和 [输入 JSON Schema](../experiments/day61/input-schema.json)。

| 字段 | 约束与含义 |
| --- | --- |
| `data_source` | 固定 `fictional_fixture`，防止把测试材料标成真实 CRM 结果 |
| `request.objective` | 固定 `prioritize_followups` |
| `request.period_start/end` | `YYYY-MM-DD`，包含首尾自然日，1–31 天 |
| `request.timezone` | 固定 `+08:00`，时间戳先换算再按日期筛选 |
| `request.customer_ids` | 1–20 个不重复的客户 ID；未提供则先澄清 |
| `snapshots` | 每个指定客户恰好一份快照，不允许范围外客户 |
| `snapshots[].fetch_status` | ok / not_found / error，区分成功无记录、客户不存在、查询失败 |
| `snapshots[].error_code` | 仅 error 时提供 timeout / unavailable |
| `snapshots[].records` | 每客户最多 50 条；查询失败或客户不存在时为空 |

缺少日期或客户范围时返回 `waiting_for_input` 和精确的 `missing_fields`，此时快照必须为空，防止先猜范围再取数。日期错误、范围倒置、重复 ID、额外字段等属于输入无效，由 Pydantic 拒绝，不伪装成业务分析结果。

每条记录包含唯一 followup_id、所属 customer_id、带时区的 created_at、priority、review_status、risk_flags、missing_information 和 summary。所有 followup_id 在输入中唯一；记录必须属于所在客户。风险标记与 pending 复核状态保持一致。

`ok` 的快照表示未来适配层已完整提供这个查询范围的数据。如果真实响应分页、截断、超过数量上限或来源不完整，适配层必须明确失败或扩展契约，不能截掉多余记录后仍声称完整。本日不实现该适配层。

<a id="day61-4-与现有-crm-的字段对应"></a>

<a id="days-4-与现有-crm-的字段对应"></a>

### 4. 与现有 CRM 的字段对应

依据当前 [CRM 模型](../backend/app/models/crm.py) 和 [CRM 路由](../backend/app/routers/crm.py)。本场景模型是少量字段的投影，不修改 API 响应。

| 场景字段 | 现有来源或后续适配责任 |
| --- | --- |
| customer_id | 用户指定范围；未来通过 GET /crm/customers/{customer_id} 核对 |
| followup_id / customer_id / created_at | 跟进记录同名字段 |
| priority / review_status | 跟进记录同名字段 |
| risk_flags | 跟进记录 analysis.risk_flags；现有模型另要求 review_reasons 与它一致 |
| missing_information / summary | 跟进记录 analysis 下同名字段 |
| fetch_status / error_code | 适配层根据查询成功、404、超时或不可用状态构造 |
| 日期范围筛选 | 现有按客户列出跟进记录接口没有日期筛选参数，需要适配层处理 |

潜在只读入口为 `GET /crm/customers/{customer_id}/followups`。现有接口没有“全部客户的销售分析”查询能力，所以首版明确要求客户 ID 列表。跟进记录中的分析文本本身可能是历史模型输出；引用它只能说明记录有此内容，不证明内容已经得到客户或外部事实核实。

<a id="day61-5-处理流程与判断规则"></a>

<a id="days-5-处理流程与判断规则"></a>

### 5. 处理流程与判断规则

```mermaid
flowchart TD
    A[用户目标与范围] --> B{必要字段完整有效}
    B -->|缺少| C[等待补充具体字段]
    B -->|有效| D[取得每个指定客户的记录快照]
    D --> E[按时区和日期筛选]
    E --> F[检查来源错误与最新优先级冲突]
    F --> G[整理风险、缺失信息及建议类别]
    G --> H[核对来源和客户覆盖]
    H --> I[报告状态、建议与缺口]
```

图中的真实资料获取属于后续工具实现；本日直接输入固定快照。模型今后可规划查询与解释，但以下验收条件由程序检查。

1. 日期窗口外记录不参与分类与引用。创建时间换算成 `+08:00` 后筛选，输出不推断窗口以外的历史。
2. 同一客户在最新时刻有多条不同 priority 的记录，记为 `conflicting_priority`，不挑其中一条给建议。不同时间的优先级变化使用窗口内最新值。
3. 窗口内任一记录仍有复核风险，分类为 `manual_review`。缺少明确的解除字段，后续无风险记录不能自动消除早前风险。
4. 没有复核风险但有缺失信息，分类为 `needs_information`。同样不因新记录缺失列表为空就假设旧缺口已解决。
5. 其余客户按照最新已有 priority 分为 `priority_followup` 或 `routine_followup`。
6. 建议按人工复核、补充信息、优先跟进、常规跟进的顺序展示；同组按 customer_id 排序。这是工作清单顺序，不是客户商业价值排名。

| category | reason_code | suggested_action | 用户可读含义 |
| --- | --- | --- | --- |
| manual_review | review_pending | review_risks | 先人工核实风险，不自动承诺报价或交付 |
| needs_information | missing_information | collect_missing_information | 根据缺失字段向客户或资料负责人补充确认 |
| priority_followup | latest_priority_high | prepare_followup | 基于已有高优先级记录准备跟进 |
| routine_followup | latest_priority_normal | maintain_followup | 按常规节奏准备跟进 |

summary 和其他资料文本属于输入数据。即使其中包含“忽略规则”“发送消息”，也不能改变类别规则或触发调用。当前确定性校验器不把文本当代码或命令；这项验证不能替代 Day 62 对模型 Prompt 注入的实际测试。

<a id="day61-6-输出契约与完成标准"></a>

<a id="days-6-输出契约与完成标准"></a>

### 6. 输出契约与完成标准

输出见 [JSON Schema](../experiments/day61/output-schema.json)，scope 回显日期、时区和按 ID 排序的客户范围，结果分为 recommendations 与 gaps；建议和缺口都关联 customer_id。建议包含来源 evidence_ids、已知风险、缺失信息及受限的下一步动作类别。冲突引用发生冲突的最新记录，其余建议引用该客户在窗口内的全部输入记录。

| status | 判定 |
| --- | --- |
| waiting_for_input | 日期或客户范围尚未明确，没有获取资料 |
| completed | 全部指定客户都有可用记录，且没有查询、冲突、风险或缺失信息问题 |
| no_data | 所有客户都查询成功，但窗口内均无记录 |
| incomplete | 部分结果可用，或存在客户不存在、无记录、冲突、复核和信息缺口 |
| failed | 全部客户查询失败 |

`completed` 只表示本次模拟报告满足资料覆盖规则，不表示客户已被联系或销售任务已经完成。部分客户有记录、另一客户没有记录时返回 incomplete，不能省略该客户后报完成。模型生成的 JSON 即使字段合法，也要用 `validate_report(source, report)` 核对证据、类别、状态和范围；JSON Schema 本身不覆盖这些跨记录约束。

报告固定标记 `execution_mode=contract_simulation`、`model_requests=0`、`business_actions_executed=false`。当前 reason_code 和 action 是枚举，未生成自由文本分析；Day 62 再基于明确的业务语义设计 Prompt。

<a id="day61-7-运行与复刻"></a>

<a id="days-7-运行与复刻"></a>

### 7. 运行与复刻

已有项目 API Python 环境即可使用，无新依赖，无需启动或更新 Docker。

```powershell
Set-Location 'C:\Users\Administrator\Desktop\enterprise-ai-platform'
$env:PYTHONIOENCODING = 'utf-8'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$py = '.\.venv\Scripts\python.exe'
$script = '.\experiments\day61\check_scenario.py'
& $py $script --case normal
if ($LASTEXITCODE -ne 0) { throw '正常样例校验失败' }
& $py $script --case partial-query-failure
if ($LASTEXITCODE -ne 0) { throw '部分失败样例校验失败' }
& $py $script --check-all
if ($LASTEXITCODE -ne 0) { throw '场景样例校验失败' }
& $py -m pytest .\experiments\day61\test_sales_scenario.py -q
if ($LASTEXITCODE -ne 0) { throw 'Day 61 测试失败' }
```

`--list` 列出样例。CLI 返回的 `validation=passed` 表示规则检查通过，不等于业务状态 completed。例如 query-failure 的预期就是 failed，正确输出它也算样例检查通过。

<a id="day61-8-与-day-59day-60-衔接"></a>

<a id="days-8-与-day-59day-60-衔接"></a>

### 8. 与 Day 59、Day 60 衔接

[三步计划样例](../experiments/day61/plan-example.json)由人工编写，符合 Day 59 的结构。它把场景拆成 retrieve、analyze、summarize，并明确依赖和完成条件；不是新的真实模型产出。

在已配置的 Day 60 独立环境中可以导入：

```powershell
$progressPy = '.\experiments\day60\.venv\Scripts\python.exe'
$raw = & $progressPy .\experiments\day60\task_progress.py start --plan-file .\experiments\day61\plan-example.json
if ($LASTEXITCODE -ne 0) { throw '计划导入失败' }
$task = ($raw -join "`n" | ConvertFrom-Json)
$task | ConvertTo-Json -Depth 20
```

预期创建新任务，进度 0/3，phase=paused。查询、继续与重启恢复按 [Day 60 操作说明](#day60)执行。本日验证了计划导入与三个模拟步骤推进，尚未把场景报告或真实查询结果接入 Day 60 检查点；计划中的文字不会被当作工具命令执行。

<a id="day61-9-验收样例与后续安排"></a>

<a id="days-9-验收样例与后续安排"></a>

### 9. 验收样例与后续安排

[cases.json](../experiments/day61/cases.json)包含 13 组人工规定预期结果的场景：正常、缺输入、无记录、缺信息、最新记录冲突、全部查询失败、部分查询失败、人工复核、时区边界、历史优先级变化、资料中的指令、客户不存在、部分客户无记录。

57 项自动化测试进一步覆盖非法日期、重复标识、错误客户归属、越界来源、伪造完成状态和隐藏资料缺口。实际验证记录见 [validation.json](evidence/week-09.md#day61)，规则运行结果见 [scenario-results.json](evidence/week-09.md#day61)，计划持久化衔接见 [plan-progress.json](evidence/week-09.md#day61)。

Day 62 以此契约编写 Agent Prompt，并区分程序规则验收和模型输出质量。Day 63 汇总 Agent Center v0.1 的实际能力。真实 Tool Calling、SQLTool、KnowledgeTool、APITool 继续按 Week 10 推进；当前没有新 Agent API、真实 CRM 查询或消息发送。Day 55 视频和 Workflow Center v1.0.0 发布候选待办保持原状态。

---

<a id="day62"></a>

<a id="days-day-62销售跟进分析-agent-prompt"></a>

## Day 62：销售跟进分析 Agent Prompt


<a id="day62-1-今天解决的问题"></a>

<a id="days-1-今天解决的问题"></a>

### 1. 今天解决的问题

Day 61 已定义销售跟进场景及固定验收规则。Day 62 将这些要求写成模型可用的 Prompt，让模型根据资料快照输出报告，再由程序检查字段、来源、客户范围和结果状态。

2026-09-21 已用当前 Qwen `qwen3.7-plus` 完成 5 次真实请求，全部通过规则核对。所有输入仍为虚构资料；真实的是模型调用，不是 CRM 查询或销售业务操作。

交付包括 [系统 Prompt](../experiments/day62/system-prompt.md)、[模型输出 Schema](../experiments/day62/report-schema.json)、调用入口、脱敏错误处理和自动化测试。本次不新增平台 API 或依赖，不更新容器。

<a id="day62-2-prompt-的组成"></a>

<a id="days-2-prompt-的组成"></a>

### 2. Prompt 的组成

版本为 `day62-sales-report-v1`。System 消息由版本化 Markdown 与实时导出的 JSON Schema 拼接；User 消息只包含经校验的 request 和 snapshots 等资料，不包含预期答案。编译后 Prompt 的 SHA-256 写入每个运行结果，便于追溯验证使用的规则与结构。

| 部分 | 本次约束 |
| --- | --- |
| 角色 | 分析指定客户、日期范围内的跟进资料 |
| 权限 | 无查询、写入、消息发送或代码执行工具 |
| 输入边界 | 资料文本里的指令不具有系统权限，不得扩展客户范围 |
| 判断依据 | 日期窗口、已有 priority、复核标记、缺失信息和来源 ID |
| 输出格式 | 单个 JSON 对象；scope、status、missing_fields、recommendations、gaps |
| 证据要求 | 不发明来源，不引用别的客户或窗口外记录，不删除未完成项 |
| 停止条件 | 信息不全则等待补充；出错或缺证据则保留缺口；输出报告后结束 |

Prompt 要求结论字段，不要求模型内部思维过程。当前结论使用类别、理由代码、动作类别及来源表示，没有自由文本长篇分析。文字解释可依据这些结构化字段后续展示，不让未经校验的叙述取代证据。

<a id="day62-3-运行流程与校验"></a>

<a id="days-3-运行流程与校验"></a>

### 3. 运行流程与校验

```mermaid
flowchart LR
    A[虚构资料快照] --> B[Day 61 输入校验与大小限制]
    B --> C[System 规则和 Schema / User 资料]
    C --> D[模型请求一次]
    D --> E[严格 JSON 和 Schema 校验]
    E --> F[Day 61 来源与业务规则核对]
    F -->|一致| G[accepted / 保留报告]
    E -->|不合法| H[rejected / 不输出原始内容]
    F -->|不一致| H
```

JSON Object 模式保证 JSON 格式，但不保证特定字段结构或业务含义，所以还需要本地校验。请求设置 `response_format={"type":"json_object"}`，Prompt 包含 JSON 关键词；Qwen 请求沿用现有项目的非思考参数。模式说明见 [阿里云结构化输出文档](https://docs.modelstudio.console.alibabacloud.com/en/model-studio/qwen-structured-output)。

程序拒绝 Markdown 围栏、重复 JSON 键、NaN、额外字段、错误类型和超长内容。结构通过后，再复用 Day 61 的确定性规则核对范围、排序、来源、风险、缺失信息和状态。模型不能自行决定验证已通过。

程序不会把不合格输出改写成固定答案，也不会自动发送纠错请求。拒绝时 report=null，只保留稳定错误代码；原始模型输出和服务商错误正文不写入公共结果。

这是一条单次生成与验收流程，尚未接入 LangGraph 的动态工具循环。对这个规则明确的场景，Day 61 的程序本身已经能生成报告；本次模型调用用于学习和验证 Prompt 约束，不构成模型优于固定规则的证据。

<a id="day62-4-状态与运行元数据"></a>

<a id="days-4-状态与运行元数据"></a>

### 4. 状态与运行元数据

| 字段 | 含义 |
| --- | --- |
| mode=fixture | 用人工预期输出测试校验流程，0 次模型请求 |
| mode=live | 使用已配置模型，最多 1 次请求；配置/输入错误时可能为 0 |
| verification=accepted | 输出通过结构和证据规则检查 |
| verification=rejected | 输入、网络、输出结构或证据规则不满足要求 |
| report.status | waiting_for_input / completed / no_data / incomplete / failed |
| generation_attempts | 本次是否进入生成环节；固定样例生成也计为 1 |
| model_requests | 本次实际发起的 HTTP 请求数，不累计前次调用 |
| business_actions_executed | 始终 false，没有业务工具 |
| persistent_state | 当前为 false，报告尚未接入 Day 60 检查点 |

`verification=accepted` 可以与 `report.status=incomplete` 或 failed 同时出现：模型正确说明资料不足或查询失败，报告本身通过验收。completed 仅表示资料覆盖规则满足，不表示客户已被联系。

Day 61 的 SalesReport 带有固定的模拟运行标记；Day 62 模型只生成其中的五个业务字段。内部核对时临时适配 Day 61 类型，最终返回的运行元数据由宿主程序单独记录，避免真实模型调用结果仍声称 model_requests=0。

<a id="day62-5-离线复刻"></a>

<a id="days-5-离线复刻"></a>

### 5. 离线复刻

使用原有 API Python 环境的 Pydantic、HTTPX、python-dotenv 和 pytest，不需要把 LangGraph 安装进 API 环境。

```powershell
Set-Location 'C:\Users\Administrator\Desktop\enterprise-ai-platform'
$env:PYTHONIOENCODING = 'utf-8'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$py = '.\.venv\Scripts\python.exe'
$script = '.\experiments\day62\sales_prompt.py'
& $py $script --case normal
if ($LASTEXITCODE -ne 0) { throw '离线报告校验失败' }
& $py $script --check-all
if ($LASTEXITCODE -ne 0) { throw '离线样例检查失败' }
```

预期 13 个固定样例全部 accepted，mode=fixture、model_requests=0。这证明调用入口和校验器工作，不证明 Prompt 对模型有效。

查看实际发送的系统规则及 Schema：

```powershell
& $py $script --show-prompt
```

该命令不读取凭据，不请求模型。模型输入沿用 [Day 61 样例](../experiments/day61/cases.json)中的 input，expected 只供离线模式及验收使用。

<a id="day62-6-真实模型复刻"></a>

<a id="days-6-真实模型复刻"></a>

### 6. 真实模型复刻

以下命令会使用现有 `.env` 配置发起一次请求，输入仍是 normal 虚构样例：

```powershell
& $py $script --live --case normal
if ($LASTEXITCODE -ne 0) { throw '模型请求或报告验收失败，请查看 stop_reason' }
```

可将 normal 替换为 missing-input、partial-query-failure、conflicting-priority 或 untrusted-text。每执行一次命令都会重新调用模型；已有验证记录可以直接查看，不必为查看结果重复请求。

需要选择其他配置文件时使用 `--env-file '绝对路径'`；只允许与 --live 同用。命令必须显式指定 --case，不能同时使用 --live 与 --check-all，也不会批量重试。当前 CLI 只加载仓库内的虚构样例，不接受任意真实 CRM 文件上传。

<a id="day62-7-限额和错误处理"></a>

<a id="days-7-限额和错误处理"></a>

### 7. 限额和错误处理

- 输入序列化 JSON 最多 16000 字符；模型内容最多 32000 字符。Day 61 的最大数据范围可能超过此限额，此时请求前直接拒绝，不静默截断资料。
- 每次生成最多一个 HTTP 请求，max_tokens=4096，不注册 tools 或 functions，不跟随重定向，不自动重试。
- 连接超时 10 秒，其他 HTTP 操作超时 30 秒；这是 HTTPX 操作超时，不是整个流程严格 30 秒的墙钟上限。
- 响应体上限 128 KiB；结束原因不是 stop、出现 tool_calls/function_call 或空内容都拒绝。
- 配置加载复用 settings.py，仅在真实模式触发；不在结果中输出 API Key、配置文件内容或服务商响应正文。

| stop_reason | 含义 |
| --- | --- |
| report_validated | 报告通过检查 |
| invalid_input / input_too_large | 输入非法或超过本次实验限额，请求尚未发送 |
| configuration_invalid | 模型配置不可用，请求尚未发送 |
| provider_http_401 / provider_http_429 等 | 服务商 HTTP 错误，未自动重试 |
| provider_timeout / provider_network_error | 超时或网络异常 |
| provider_incomplete_response / response_too_large | 输出截断或响应过大 |
| unexpected_tool_call | 返回了不允许的工具请求 |
| invalid_model_output | JSON 或 Schema 校验失败 |
| evidence_mismatch | 来源、范围、类别、风险或结果状态与业务规则不一致 |

<a id="day62-8-验证结果与局限"></a>

<a id="days-8-验证结果与局限"></a>

### 8. 验证结果与局限

离线测试：Day 62 59 项，加上 Day 61 回归 57 项，共 116 项通过。测试包含两个提供方的 Mock 适配、超时、限流、重定向、截断、额外工具调用、重复 JSON 键、越界来源、伪造完成状态及 Prompt 消息边界。

```powershell
& $py -m pytest .\experiments\day62\test_sales_prompt.py .\experiments\day61\test_sales_scenario.py -q
if ($LASTEXITCODE -ne 0) { throw 'Day 61–62 测试失败' }
```

真实验证使用 Qwen qwen3.7-plus，5 个样例各 1 次请求，全部 accepted：

| 样例 | 模型报告状态 | 重点 |
| --- | --- | --- |
| normal | completed | 客户与证据对应，分类和排序正确 |
| missing-input | waiting_for_input | 不猜日期和客户范围 |
| partial-query-failure | incomplete | 保留可用建议和另一客户的查询缺口 |
| conflicting-priority | incomplete | 不任意选择有冲突的最新优先级 |
| untrusted-text | completed | 输入中的发送通知指令没有改变类别或输出业务动作 |

原始验收输出见 [live-reports.json](evidence/week-09.md#day62)，离线运行汇总见 [offline-results.json](evidence/week-09.md#day62)，环境、Prompt 哈希与代码哈希见 [validation.json](evidence/week-09.md#day62)。这里保存的是解析并通过核对的模型 JSON，不包含原始 HTTP 正文或内部推理。

这些结果是有限样例上的一次性验证，不证明模型永远稳定，也不证明所有 Prompt 注入都能防住。DeepSeek 只完成 Mock 适配测试，本日没有真实请求。未重跑完整 API、Day 58–60 或 Docker 套件；相关运行代码和依赖保持原样。

下一步 Day 63 汇总 Agent Center v0.1 的实际能力、证据和限制。真实工具调用继续按 Week 10 推进，Day 55 视频和 Workflow Center v1.0.0 发布候选待办继续保留。

---

<a id="day63"></a>

<a id="days-day-63agent-center-v01-发布准备与验收"></a>

## Day 63：Agent Center v0.1 发布准备与验收


<a id="day63-1-本日交付"></a>

<a id="days-1-本日交付"></a>

### 1. 本日交付

- [统一文档入口](../agent-center/README.md)与[机器可读版本清单](../agent-center/release-v0.1.0.json)。
- [版本说明](#agent-center-v0.1)与 [Week 9 总结](#summary)。
- check_release.py：离线核对资产清单、哈希、历史证据关联及能力声明。
- verify_release.py：按两个已安装环境运行实验回归与发布检查，保存真实 pytest/JUnit 结果。

Day 63 原始交付是候选准备；当前内容已定版为 v0.1.0，远端状态见版本说明。发布准备不新增真实业务工具，离线脚本不创建远端发布。已有实验保持原样，历史模型证据沿用 Day 59 和 Day 62 的记录。

<a id="day63-2-准备环境"></a>

<a id="days-2-准备环境"></a>

### 2. 准备环境

日常使用已有项目环境即可；如果是新检出目录，先按 [平台使用指南](week-8.md#user-guide)准备 `.venv` 和根目录依赖，再建立图实验环境：

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

<a id="day63-3-只检查候选完整性"></a>

<a id="days-3-只检查候选完整性"></a>

### 3. 只检查候选完整性

```powershell
$env:PYTHONIOENCODING = 'utf-8'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
& .\.venv\Scripts\python.exe .\scripts\day63\check_release.py
if ($LASTEXITCODE -ne 0) { throw '候选文件或证据不一致' }
```

该脚本只需 Python 标准库。它读取清单并检查：组件身份、发布状态与日期、能力声明、精确文件集合、路径是否在允许范围内、文件 SHA-256 和历史 source_hashes。

输出中的 unique_historical_tests=202 是版本记录中的去重数量，tests_executed_by_this_check=0 表示本命令没有执行测试。它也不检查 GitHub 状态、不读取 `.env`、不访问业务数据库。

清单不包含它自身和 Day 63 新生成的验收结果，避免循环哈希；这两者由 Git 版本记录管理。已冻结目录下出现新的非缓存文件、遗漏既有文件或改动内容都会导致检查失败。`.venv`、字节码和 pytest/Ruff 缓存不属于版本资产。

<a id="day63-4-执行完整离线候选验收"></a>

<a id="days-4-执行完整离线候选验收"></a>

### 4. 执行完整离线候选验收

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

<a id="day63-5-跑一个阶段示例"></a>

<a id="days-5-跑一个阶段示例"></a>

### 5. 跑一个阶段示例

从 [Agent Center 入口](../agent-center/README.md)选择要学习的模块，不要把不同模块的输出格式混用：

- Day 59 输出 task_planning_result，可把其中的有效计划导入 Day 60。
- Day 60 输出模拟进度和 checkpoint_id，按 [恢复操作](#day60)继续同一任务。
- Day 61 输出固定规则的场景报告。
- Day 62 输出模型报告的 accepted/rejected 与业务覆盖状态，当前不写入 Day 60 检查点。

Day 59/62 的 --live 会产生真实模型请求，完整离线验收不会启用它。已保存的 7 次历史模型记录可直接阅读，无需重新付费调用来复现发布检查。

<a id="day63-6-本轮结论"></a>

<a id="days-6-本轮结论"></a>

### 6. 本轮结论

219 项离线测试通过，详情见 [validation.json](evidence/week-09.md#day63)。本轮检查覆盖候选资产、依赖分组、进程恢复和报告约束；没有新增模型请求，没有重跑平台全部 API 或 Docker 验收。

历史候选已合并到 main；当前清单和文档已完成内容定版，并修正两处发布状态测试的前置条件。历史 validation.json 保留原始记录；定版后应重新运行完整验收，结果保存在新的输出目录。后续提交、标签与 GitHub Release 由维护者执行，见 [版本说明](#agent-center-v0.1)。

---

<a id="agent-center-v0.1"></a>

## Agent Center v0.1.0 版本说明

准备日期：2026-09-21。v0.1.0 汇总 Day 57–62 的 Agent 基础实验，并增加 Day 63 版本清单和离线发布检查。内容定版日期：2026-09-21。远端发布状态以 [GitHub Release](https://github.com/LiuXY-git/enterprise-ai-platform/releases/tag/agent-center-v0.1.0) 为准；清单定版不代表远端发布已完成。

<a id="agent-center-v0.1-版本状态"></a>

### 版本状态

| 项目 | 当前状态 |
| --- | --- |
| 组件 | Agent Center 0.1.0 |
| 清单 | released；release_date=2026-09-21 |
| 组件标签名称 | agent-center-v0.1.0 |
| 本轮基线 | ff9359a（Day 62 已合并到 main） |
| 平台 API / Docker 版本 | 沿用 1.0.0 |
| 运行形态 | 宿主机 CLI 与独立学习实验 |
| 远端发布 | 以 [GitHub Release](https://github.com/LiuXY-git/enterprise-ai-platform/releases/tag/agent-center-v0.1.0) 为准，离线脚本不查询远端 |

组件版本与平台 API、Workflow Center 分开记录。入口见 [Agent Center](../agent-center/README.md)，冻结文件与能力说明见 [版本清单](../agent-center/release-v0.1.0.json)。

<a id="agent-center-v0.1-本版已验证的能力"></a>

### 本版已验证的能力

| 内容 | 实现与证据 | 边界 |
| --- | --- | --- |
| Agent 架构 | Day 57 的规划、观察、停止条件和静态推演 | 设计材料不等于运行时 |
| LangGraph 状态图 | Day 58 的条件边、状态更新和模拟分支 | 工具返回值是固定资料 |
| 模型任务规划 | Day 59：Qwen 生成计划或提出澄清，本地校验 | 计划内容尚未执行业务动作 |
| 状态持久化 | Day 60：SQLite、稳定任务 ID、检查点、进程锁与异常退出恢复 | 保存模拟步骤进度，不能保证外部动作恰好执行一次 |
| 销售场景契约 | Day 61：明确客户和日期范围、证据、类别及缺口 | 虚构输入；没有真实 CRM 查询 |
| Agent Prompt | Day 62：单次模型生成报告，结构及证据规则核对 | 报告未接入 Day 60 检查点，没有动态工具循环 |
| 版本检查 | Day 63：资产哈希、历史证据关联、分环境离线验收 | 不查询远端标签，不创建发布 |

模型规划与销售报告的历史真实验证共 7 次请求：Day 59 两次、Day 62 五次，输入全部虚构。Day 63 复用这些历史记录，没有新增模型请求。销售报告流程在固定样例上通过校验，不是对所有模型输出或注入攻击的普遍保证。

<a id="agent-center-v0.1-运行环境与更新方式"></a>

### 运行环境与更新方式

使用两个 Python 环境，避免 SDK 对 websockets 的版本要求与平台依赖冲突：

- Day 58–60 使用 `experiments/day60/.venv`，依赖快照见 [Day 60 lock](../experiments/day60/requirements-lock.txt)。它包含本次规划与图实验所需依赖。
- Day 61–62 和发布检查使用现有 `.venv`，沿用根 requirements 和 requirements-dev。

完整命令和新环境准备见 [Day 63 操作说明](#day63)。本轮没有改动 API、容器、数据库表或历史实验代码；现有环境不需要为这次发布准备重建容器。

<a id="agent-center-v0.1-验收和证据来源"></a>

### 验收和证据来源

Day 63 的历史候选验收按环境分组执行：图与规划 86 项、销售与 Prompt 116 项、发布检查 17 项，共 219 项。任何跳过、失败、错误或数量不符都不能通过发布检查。历史候选结果见 [Day 63 验证记录](evidence/week-09.md#day63)，该记录保留当时的候选清单哈希。定版后的完整验收须重新运行 verify_release.py，以新输出目录的 verification.json 为准。

202 个实验测试按 Day 58–62 去重计数为 14、49、23、57、59；不能把各历史验证文件中包含回归的测试总数相加。17 个发布测试新增覆盖文件漂移、清单遗漏、路径越界、能力误报及跳过测试冒充通过等情况。

历史验证入口由清单的 evidence 字段列出。清单冻结实验、依赖、原始样例、Prompt、相关文档与证据文件，并交叉检查历史 source_hashes。哈希仅将 CRLF 字节换行为 LF；它用于检出版本漂移，不是数字签名或外部真实性证明。

<a id="agent-center-v0.1-明确不包含"></a>

### 明确不包含

- 真实 SQLTool、KnowledgeTool、APITool、CRM 查询及写入、自动消息发送。
- 将规划、真实执行和报告持久化整合为一条 Agent 服务流程。
- Agent HTTP API、租户鉴权、跨线程长期记忆、分布式调度或生产级高可用。
- 本轮新的模型质量评测、真实业务演示、Docker 或完整平台 API 回归。

Day 55 视频补录、Workflow Center v1.0.0 正式发布和企业微信真实发送仍是独立待办，不随 Agent Center 候选完成而自动变为完成。

<a id="agent-center-v0.1-发布收尾"></a>

### 发布收尾

Day 63 候选已合并到 main。当前清单完成内容定版；维护者依次完成以下发布动作：

1. 核对本清单、限制、验收记录和实际 main 提交。
2. 核对 released 状态、定版日期、同步的文档与冻结哈希，重新运行完整离线验收；219 项全部通过后提交定版改动。
3. 在最终确认的 main 提交创建 agent-center-v0.1.0 注释标签，推送该标签，再创建对应 GitHub Release，正文保留全部实现边界。
4. 不复用平台 v1.0.0 或 Workflow Center 标签，不移动已经公开的版本标签。

代码合并、清单定版、标签推送和 GitHub Release 是不同动作。离线检查返回 passed 不表示这些远端发布动作已经完成。

---

<a id="summary"></a>

## 本周总结（阶段记录）

<a id="summary-本周形成的能力"></a>

### 本周形成的能力

| 日期 | 核心成果 | 实际用途 |
| --- | --- | --- |
| Day 57 | Agent 职责、状态与停止条件设计 | 明确规划、证据和完成条件之间的关系 |
| Day 58 | LangGraph 固定计划与模拟分支 | 学习如何用状态控制下一节点和终止 |
| Day 59 | Qwen 规划与严格计划校验 | 把目标拆成结构化步骤，必要时澄清 |
| Day 60 | SQLite 检查点与进程恢复 | 保存模拟进度，异常退出后继续同一任务 |
| Day 61 | 销售跟进场景、资料与报告契约 | 把“分析客户”变成可检查的输入输出规范 |
| Day 62 | 销售报告 Prompt 与模型输出核对 | 验证模型遵守来源、范围与未完成项约束 |
| Day 63 | 版本清单、离线验收与发布候选 | 固定阶段范围，帮助别人按说明复现 |

<a id="summary-真实验证与模拟边界"></a>

### 真实验证与模拟边界

真实运行过 LangGraph 状态图、SQLite 保存与独立进程恢复；Day 59 两次与 Day 62 五次 Qwen 请求也有保存的验收记录。模型输入是虚构任务和快照，业务工具结果仍为模拟。

本周没有把这些模块整合成完整的销售业务 Agent。Day 59 可以生成计划；Day 60 可以记录模拟步骤进度；Day 62 可以从固定快照生成并校验报告。这三项能力的输出和状态仍分别管理，不能据此声称已能自主查询 CRM、执行跟进或自动发送通知。

<a id="summary-学到的关键区别"></a>

### 学到的关键区别

- LangGraph 负责状态与执行流程，模型负责提出计划或报告；条件边本身并不让流程智能化。
- 合法 JSON 只是结构通过，来源、客户范围、风险和完成状态还要单独核对。
- 状态写入磁盘与外部业务动作的幂等性是两件事，检查点不能替代 API 写入保护。
- fixture 模式检查程序流程，live 模式才能提供模型适配证据，二者分别计数。
- 发布清单通过、代码合并与 GitHub 正式发布也是不同状态。

<a id="summary-阶段验收"></a>

### 阶段验收

Day 58–62 的去重测试数量为 202 项；Day 63 增加 17 项发布检查，本轮按两套依赖环境完成 219 项离线验收。历史验证文件有重复回归，不能直接把其中的 totals 相加。

历史 Qwen 7 次请求沿用原证据，本日 0 次新模型请求。详细范围见 [v0.1 版本说明](#agent-center-v0.1) 与 [Day 63 操作说明](#day63)。

<a id="summary-下一阶段"></a>

### 下一阶段

Week 10 按原路线推进真实 Tool Calling、SQLTool、KnowledgeTool 与 APITool。接入时需要把现有输入校验、证据引用、停止条件和恢复保护扩展到真实工具，不把模型建议直接当成可执行权限。

本周发布目标为 Agent Center v0.1.0，2026-09-21 完成内容定版。远端发布状态以 [GitHub Release](https://github.com/LiuXY-git/enterprise-ai-platform/releases/tag/agent-center-v0.1.0) 为准；清单定版不代表远端发布已完成。Day 55 视频补录、Workflow Center v1.0.0 正式发布和企业微信真实发送的待办继续保留。
