# Workflow Center v0.5.0 发布说明

Workflow Center v0.5.0 汇总 Week 7 企业系统集成成果：飞书与企业微信接口、模拟 CRM、销售线索工作流和故障恢复。销售流程已通过正常处理、重复事件及恢复保护验收，当前通知产出为预览。

业务验收于 2026-09-13 完成，版本内容于 2026-09-14 定版。清单中的 released 与 release_date 记录本地组件版本定版，不表示已经推送或创建 GitHub Release；线上发布状态以远端标签和 Release 页面为准。

## 版本与范围

| 项目 | 值或交付边界 |
| --- | --- |
| Workflow Center | 0.5.0 |
| 平台 API | 保持 1.0.0 |
| n8n | 当前项目固定为 2.36.8 |
| 组件标签 | workflow-center-v0.5.0 |
| 销售 CRM | 客户、跟进、事务写入、同一运行防重复 |
| 故障恢复 | AI 分类、分析检查点、CRM 显式回放、通知状态及人工核对 |
| 飞书 | 独立消息接口已实现，有历史真实联调证据 |
| 企业微信 | 接口及 Mock/本地验收已完成，真实发送待域名条件满足 |
| 销售通知 | 固定 preview；异常与人工核对通过状态 API 模拟 |

清单位于 [workflow-center-v0.5.0.json](../n8n/workflow-center-v0.5.0.json)，v0.1.0 清单与历史发布记录保留。

## 工作流清单

| 文件 | 层级 | 用途 |
| --- | --- | --- |
| w6d36-foundation-check.json | reference | 手动环境检查 |
| w6d37-customer-request-webhook.json | reference | 客户请求接入 |
| w6d38-ai-customer-request.json | reference | 调用 FastAPI/Dify |
| w6d39-ai-email-assistant.json | reference | 邮件分类与回复草稿 |
| w6d40-daily-workflow-report.json | optional | 日报，需要模型绑定后按需启用 |
| w6d41-workflow-error-handler.json | release | 邮件流程失败落库 |
| w6d41-persistent-ai-email-assistant.json | release | 持久化邮件助手 |
| w7d47-sales-followup-assistant.json | release | 销售助手与 CRM 恢复 |

八条文件均位于 n8n/workflows。reference 不默认发布；日报调度按需启用。已有实例无需为本次文档整理重新导入已经验收的工作流。

## 新环境部署与绑定

Compose 管理 api 与 n8n，Dify 独立部署。准备 N8N_ENCRYPTION_KEY；邮件/Dify 路径还需可访问的 Dify 工作流、DIFY_WORKFLOW_API_KEY 和正确的 DIFY_API_BASE_URL。API 使用本地 data 持久化 SQLite，n8n 使用 n8n_data 卷。

新环境按清单 import_order 导入工作流，再完成绑定：

1. 邮件助手的 Settings / Error Workflow 绑定到 W6D41 - Workflow Error Handler。
2. 日报与销售助手的 DashScope Qwen Chat Model 选择各自实例内的 OpenAI 兼容 Credential，模型与导出保持 qwen3.7-plus。
3. 先启用错误处理工作流，再发布持久化邮件助手，最后发布销售助手。销售助手使用自身 AI/CRM 错误分支，不要求绑定邮件错误处理器。
4. 日报发布调度前检查 Asia/Shanghai 时区；参考流程按需启用。

所有仓库导出保持 inactive，不携带实例 ID、Credential 引用或固定执行数据。导入后不会自动继承另一实例的凭据。容器内 API 地址为 http://api:8000；本机销售 Production 入口为 http://localhost:5678/webhook/w7d47-sales-followup-assistant。

部署基础步骤见 [Docker 部署](docker-deployment.md)，具体绑定以本版本清单为准。

## 验收结果

本轮完成以下增量验收：

- 新建两组通知异常记录，CRM 保存后的整条回放均返回 409，运行、客户及跟进记录不变。
- 模拟确认已送达后尝试保持 1 次；确认未送达后显式人工重试并模拟成功，尝试为 2 次。共 14 次受限操作被拒绝且状态不变。
- Production 首次运行成功，检查点保存，通知 preview；同一事件重复提交后 duplicate_count 为 1、跟进为 1 条、通知尝试为 0，CRM 不变。

Day 48 全量 415 项测试、Ruff、JavaScript 分类/检查点回归以及 AI/CRM 故障证据沿用原记录。Day 49 新清单及销售相关 21 项测试和 Ruff 已通过；验收脚本在隔离环境验证后由用户执行已部署 API 的业务验收。没有将 21 项局部检查写成新一轮全量测试。

证据与版本关联见 [Day 49 发布验收记录](week-7-notes.md#day49)。已通过且未受改动影响的项目沿用结果；只有相关代码改变、失败或新增风险时重验，不追加重复节点核对。

## 当前限制与 Week 8 待办

- 销售工作流未包含真实通知发送编排。通知状态 API 自身不发送消息，模拟 message_id 不是平台消息证据。
- 通知变为 sent 不会自动将原 failed 工作流改成 succeeded；通知恢复后的业务运行收尾需要单独设计。
- 企业微信真实发送仍受后台域名条件限制。
- 业务接口及 Webhook 尚无统一认证、租户隔离和限流；当前面向本机或可信网络的单机演示。
- 日报仍使用固定实验记录，CRM 回放由调用方显式发起；尚无定时恢复调度。
- Week 8 继续模板整理、统一日志、配置、部署说明和正式 Demo，不为发布 v0.5.0 临时扩大功能范围。

## 发布收尾与回退

本地交付采用功能分支提交、合并到 main、创建 workflow-center-v0.5.0 注释标签的方式。维护者负责推送 main 与组件标签，并在 GitHub 基于该标签创建 Release，标题为 Workflow Center v0.5.0。平台 API 版本保持 1.0.0。短演示可使用[已有验收证据讲解稿](workflow-center-v0.5-demo.md)，正式 Demo 留在 Day 55。

需要回退时先停止受影响的工作流入口，保留数据库和 n8n 卷备份，并恢复经确认兼容的代码与工作流版本。Day 49 的业务代码和销售导出沿用 Day 48，文档回退不应删除 CRM 数据、清空命名卷或盲目重放已完成阶段。

本周学习与取舍见 [Week 7 总结](week-7-summary.md)。
