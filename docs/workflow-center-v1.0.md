# Workflow Center v1.0.0 发布候选说明

准备日期：2026-09-17。Workflow Center `1.0.0` 汇总 Week 8 的模板、日志、配置、部署、文档与演示工具，业务流程继续使用已经维护的八条 n8n 导出。当前为本地发布候选，尚未创建本版本标签或 GitHub Release。

维护者已决定先完成 Day 56，之后补录视频。Day 55 材料已准备，本轮真实业务演示及视频验收仍未执行。该延期不阻止阶段总结和本版本发布准备；发布说明保留这一事实，后续补充录制结果。

## 版本与发布状态

| 项目 | 当前值 |
| --- | --- |
| Workflow Center 目标版本 | `1.0.0` |
| API / Docker 应用版本 | 沿用 `1.0.0` |
| n8n 镜像版本 | 沿用 `2.36.8` |
| 组件标签名称 | `workflow-center-v1.0.0`，待发布收尾时创建 |
| 清单状态 | `candidate`，正式 `release_date` 暂为 null |
| 已有发布基线 | `workflow-center-v0.5.0` |
| Day 56 工作基线 | Day 55 提交 `8429fbb`；包含尚未合并到 main 的 Day 55 成果 |
| Demo 视频 | 维护者确认延期，未录制、未验收 |

组件版本和平台 API 版本是不同发布范围；不要复用平台已有的 `v1.0.0` 标签。清单见 [workflow-center-v1.0.0.json](../n8n/workflow-center-v1.0.0.json)，阶段取舍见 [Week 8 总结](week-8-summary.md)。

## 本版内容

| 交付部分 | 内容与入口 |
| --- | --- |
| 工作流模板 | [客服、邮件和销售目录](../n8n/templates/README.md)，含契约、样例与绑定说明 |
| 日志 | [Day 51](day51-workflow-logging.md)：HTTP 业务边界事件、有限脱敏快照、耗时与用量来源 |
| 配置 | [Day 52](day52-configuration-center.md)：集中配置、按需校验、环境优先级与离线自检 |
| 部署 | [Day 53](day53-compose-deployment.md)：一键启动、部署检查、日志容量、隔离重建验证 |
| 文档 | [使用指南](user-guide.md)、[系统架构](architecture.md)、[技术选型](tech-stack.md) |
| 演示工具 | [Day 55](day55-workflow-demo.md)：独立请求包、逐步执行、超时留证与录制验收表；视频延期 |

Day 56 新增候选清单、总结与发布元数据，更新录制延期状态；后端业务代码、模型配置、工作流导出和部署脚本均沿用当前基线。

## 工作流与新环境绑定

| 导出文件 | 层级 | 默认发布 |
| --- | --- | --- |
| `w6d36-foundation-check.json` | reference | 否 |
| `w6d37-customer-request-webhook.json` | reference | 否 |
| `w6d38-ai-customer-request.json` | reference | 否 |
| `w6d39-ai-email-assistant.json` | reference | 否 |
| `w6d40-daily-workflow-report.json` | optional | 否 |
| `w6d41-workflow-error-handler.json` | release | 是 |
| `w6d41-persistent-ai-email-assistant.json` | release | 是 |
| `w7d47-sales-followup-assistant.json` | release | 是 |

清单的工作流路径相对 `n8n`，文档和交付资产路径相对仓库根目录。每条导出记录 SHA-256，计算前只把 CRLF 换行为 LF，避免 Windows 检出换行导致误报；视频文件的 SHA-256 则按原始文件字节计算。

新环境按清单 `deployment.import_order` 导入，给持久化邮件助手绑定 Error Workflow，给日报与销售的 `DashScope Qwen Chat Model` 绑定实例内 `openAiApi` 凭据，再按 `publish_order` 发布默认流程。参考流程按需发布；录制客服片段时，需要单独确认其 Webhook 已发布或开启测试监听。

API 与 n8n 由本项目 Compose 管理，Dify 独立部署。API 的 `LLM_PROVIDER` 不会修改 Dify/n8n 内部模型。保留原 `N8N_ENCRYPTION_KEY`；所有仓库导出继续为 inactive，且不包含实例凭据引用、固定执行数据或自动继承的发布状态。

## 现有环境如何更新

维护者已反馈 Day 53 容器更新和健康检查通过，Day 54、Day 55、Day 56 的增量是文档及宿主机演示工具，**已部署 Day 53 的环境无需因这些增量重建容器**。已经验收的工作流也无需为候选清单重新导入。

若使用的是更早代码或新环境，按 [使用指南](user-guide.md) 和 [Day 53](day53-compose-deployment.md) 执行部署与检查。更新程序和更新文档是不同操作，不把代码合并当作容器已经更新，也不把健康状态当作真实模型调用成功。

## 证据与本轮检查

候选清单的 `quality_gates` 列出质量范围，`quality_evidence` 指明结果来源；列入门禁不表示本轮重新执行。

| 范围 | 来源与状态 |
| --- | --- |
| 正常、复核、重复、失败与恢复保护 | 沿用 [Day 49 及其基线记录](day49-release-acceptance.md) |
| 日志与集中配置 | 沿用 [Day 51](day51-workflow-logging.md)、[Day 52](day52-configuration-center.md) |
| 全量 506 项测试与隔离容器重建 | 沿用 [Day 53](day53-compose-deployment.md)，不是 Day 56 重跑 |
| 使用与架构文档 | 沿用 [Day 54](day54-documentation.md) |
| 演示工具的 19 项离线/模拟检查 | 沿用 [Day 55](day55-workflow-demo.md)，不是本轮真实业务或视频验收 |
| Day 56 清单与文档 | 13 项一致性检查通过，其中复用六项既有发布清单检查逻辑验证 v1 候选 |
| Day 55 新录制 | 明确延期，不计为通过项 |

当前本轮校验范围为：候选版本与路径、八条导出内容哈希、导入/发布顺序、实际节点的凭据和错误处理绑定、模板目录引用、交付资产及文档链接、延期状态一致性。

本轮结果：8 条导出哈希及部署绑定一致，3 个模板入口有效，26 个交付资产路径和 176 个本地文档链接检查通过，16 个 Markdown 代码围栏完整。对比 Day 55 基线，历史清单、业务代码、工作流导出和执行/部署脚本未变化。本轮不调用业务接口、模型或消息服务，不重跑全量 pytest，也不执行录屏。

## 已知限制

- 销售通知固定为 preview，真实消息编排尚未实现。通知状态 API 不会自行发送消息。
- 人工核对将通知变为 sent 后，原 failed 工作流不会自动结束。
- 企业微信接口有 Mock/本地验收，真实发送仍待环境条件；飞书独立接口的历史联调不代表销售通知链路已验收。
- 邮件助手没有邮箱监听或自动发信；客服模板没有平台事件去重；日报使用既有实验数据。
- 统一业务 API/Webhook 认证、租户隔离、限流和高可用仍待实现，当前面向本机或可信网络。
- Day 55 本轮真实业务演示、视频文件与视频验收延期，不能将旧视频或模拟响应作为本版新录制证据。

## 发布收尾

当前分支包含 Day 55 的本地提交，合并 Day 56 时会一并带入。维护者按此前分工执行推送、合并与发布：

1. 核对候选清单、变更记录和延期事项，推送 Day 56 分支并将相关提交合并到 `main`。
2. 准备正式版本时，将清单 `release_status` 改为 `released`、`release_date` 填实际定版日期，同步 README、CHANGELOG 与本页的当前发布状态，并提交这些元数据。Demo 延期字段继续保留，直到实际补录验收。
3. 在已确认的最终 `main` 提交上创建 `workflow-center-v1.0.0` 注释标签，推送 main 和该标签，再创建同名组件 GitHub Release。发布正文写清本版范围、证据来源、视频延期及已知限制。
4. 后续补录完成后提交验收摘要，更新视频交付记录，并按需要补充 Release 资产或说明；不要移动已经发布的标签。

这些是后续可执行步骤，本轮没有执行推送、合并、标签创建或 GitHub 发布。视频延期不要求把已经完成的代码改回去，也不需要重新执行不受影响的历史业务验收。

## 之后补录

录制条件具备后，先运行现有部署检查，为当日演示创建新的请求包，按 [Day 55 操作稿](day55-workflow-demo.md) 完成场景并核对实际响应与持久化结果，再按 [验收表](../demo/day55-recording-checklist.md) 检查视频。只有实际文件存在并通过核对后才填写视频路径、时长和 SHA-256。

新一轮录制不要复用旧的已执行事件作为新业务，失败或超时也不要删除结果文件重发。若补录发现需要修复程序，则对相关改动验证并正常提交；视频补录和程序修复分别记录。
