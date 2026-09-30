# Agent Center v0.1.0 版本说明

准备日期：2026-09-21。v0.1.0 汇总 Day 57–62 的 Agent 基础实验，并增加 Day 63 版本清单和离线发布检查。内容定版日期：2026-09-21。远端发布状态以 [GitHub Release](https://github.com/LiuXY-git/enterprise-ai-platform/releases/tag/agent-center-v0.1.0) 为准；清单定版不代表远端发布已完成。

## 版本状态

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

## 本版已验证的能力

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

## 运行环境与更新方式

使用两个 Python 环境，避免 SDK 对 websockets 的版本要求与平台依赖冲突：

- Day 58–60 使用 `experiments/day60/.venv`，依赖快照见 [Day 60 lock](../experiments/day60/requirements-lock.txt)。它包含本次规划与图实验所需依赖。
- Day 61–62 和发布检查使用现有 `.venv`，沿用根 requirements 和 requirements-dev。

完整命令和新环境准备见 [Day 63 操作说明](week-9-notes.md#day63)。本轮没有改动 API、容器、数据库表或历史实验代码；现有环境不需要为这次发布准备重建容器。

## 验收和证据来源

Day 63 的历史候选验收按环境分组执行：图与规划 86 项、销售与 Prompt 116 项、发布检查 17 项，共 219 项。任何跳过、失败、错误或数量不符都不能通过发布检查。历史候选结果见 [Day 63 验证记录](evidence/week-09.md#day63)，该记录保留当时的候选清单哈希。定版后的完整验收须重新运行 verify_release.py，以新输出目录的 verification.json 为准。

202 个实验测试按 Day 58–62 去重计数为 14、49、23、57、59；不能把各历史验证文件中包含回归的测试总数相加。17 个发布测试新增覆盖文件漂移、清单遗漏、路径越界、能力误报及跳过测试冒充通过等情况。

历史验证入口由清单的 evidence 字段列出。清单冻结实验、依赖、原始样例、Prompt、相关文档与证据文件，并交叉检查历史 source_hashes。哈希仅将 CRLF 字节换行为 LF；它用于检出版本漂移，不是数字签名或外部真实性证明。

## 明确不包含

- 真实 SQLTool、KnowledgeTool、APITool、CRM 查询及写入、自动消息发送。
- 将规划、真实执行和报告持久化整合为一条 Agent 服务流程。
- Agent HTTP API、租户鉴权、跨线程长期记忆、分布式调度或生产级高可用。
- 本轮新的模型质量评测、真实业务演示、Docker 或完整平台 API 回归。

Day 55 视频补录、Workflow Center v1.0.0 正式发布和企业微信真实发送仍是独立待办，不随 Agent Center 候选完成而自动变为完成。

## 发布收尾

Day 63 候选已合并到 main。当前清单完成内容定版；维护者依次完成以下发布动作：

1. 核对本清单、限制、验收记录和实际 main 提交。
2. 核对 released 状态、定版日期、同步的文档与冻结哈希，重新运行完整离线验收；219 项全部通过后提交定版改动。
3. 在最终确认的 main 提交创建 agent-center-v0.1.0 注释标签，推送该标签，再创建对应 GitHub Release，正文保留全部实现边界。
4. 不复用平台 v1.0.0 或 Workflow Center 标签，不移动已经公开的版本标签。

代码合并、清单定版、标签推送和 GitHub Release 是不同动作。离线检查返回 passed 不表示这些远端发布动作已经完成。
