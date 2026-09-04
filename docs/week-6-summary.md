# Week 6 总结：Workflow Center v0.1.0

## 本周目标

Week 6 的目标是掌握 n8n 工作流自动化，并把 Webhook、FastAPI、Dify、LLM
和 SQLite 连接成可运行、可追踪、可恢复、可版本化发布的企业工作流中心。

本周最终产出为：Workflow Center v0.1.0。

## 学习进度

### Day 36：n8n 基础与部署

- 使用 Docker Compose 部署固定版本 n8n 2.36.8
- 配置健康检查、时区、执行数据清理和命名卷
- 建立最小手动工作流
- 学习工作流 JSON 导出和安全脱敏

### Day 37：Webhook 触发

- 建立测试 URL 和生产 URL
- 规范化外部请求字段
- 使用 Respond to Webhook 返回显式 JSON
- 验证测试监听与发布后的生命周期差异

### Day 38：连接 AI 工作流

- 从 n8n 调用 FastAPI `/dify/workflow`
- 完成请求映射、超时配置和结构化响应
- 验证测试与生产 Webhook

### Day 39：AI 邮件助手

- 规范化邮件事件
- 分类请求类型和优先级
- 为敏感或高风险请求增加人工审核
- 为低风险请求生成 AI 回复草稿

### Day 40：AI 工作流日报

- 支持 Schedule Trigger 和手动回放
- 聚合成功率、失败类型、耗时和 Token
- 使用原生 LLM Chain 生成受约束日报
- 验证正常、无数据和非法日期场景

### Day 41：数据库持久化

- 新增 SQLite `workflow_runs` 运行账本
- 新增登记、完成、失败和查询 API
- 使用 `(workflow_name, event_id)` 实现幂等
- 使用 Error Trigger 自动保存失败
- 支持失败记录最多 3 次回放
- 验证成功、人工审核、重复、失败和回放场景

### Day 42：发布 Workflow Center v0.1.0

- 冻结 7 个版本化工作流的发布范围
- 新增机器可读发布清单
- 区分 reference、optional 和 release 工作流
- 固定导入、手动绑定和发布顺序
- 增加跨工作流可移植性与敏感信息测试
- 补齐 OpenAPI、API 文档和组件发布说明
- 使用独立组件标签避免与平台 `v0.1.0` 冲突

## 系统架构

```text
外部邮件 / HTTP 请求
        ↓
n8n Webhook
        ↓
运行登记与幂等判断 ───────→ SQLite workflow_runs
        ↓                              ↑
规则分类与人工审核                    │
        ↓                              │
FastAPI /dify/workflow                │
        ↓                              │
Dify 企业咨询分流                     │
        ↓                              │
Knowledge Hub / RAG                   │
        ↓                              │
统一响应与运行完成 ────────────────────┘

n8n 自动执行失败
        ↓
Error Trigger
        ↓
按 execution_id 保存失败
```

## v0.1.0 发布结构

```text
n8n/
├── workflow-center-v0.1.0.json
└── workflows/
    ├── w6d36-foundation-check.json
    ├── w6d37-customer-request-webhook.json
    ├── w6d38-ai-customer-request.json
    ├── w6d39-ai-email-assistant.json
    ├── w6d40-daily-workflow-report.json
    ├── w6d41-workflow-error-handler.json
    └── w6d41-persistent-ai-email-assistant.json
```

发布清单是组件版本的单一事实来源。新增、删除或重命名工作流后，如果没有同步
修改清单，自动化测试会失败。

## 工程能力

- 工作流 JSON 纳入 Git 版本控制
- 导出文件默认未激活，避免导入即触发生产任务
- 实例 ID、Webhook ID、Credential 和项目元数据不进入仓库
- FastAPI OpenAPI 描述覆盖工作流运行接口
- SQLite 使用事务和唯一约束保护运行状态
- 自动化测试覆盖数据库、服务、路由、工作流结构和发布清单
- Docker Compose 提供 API 与 n8n 的可重复运行环境

## 安全设计

- `.env` 被 Git 忽略，`.env.example` 只保留空占位符
- Dify API Key 只由 FastAPI 服务端读取
- n8n Credential 不随工作流 JSON 导出
- n8n 仅绑定 `127.0.0.1:5678`
- 运行数据和 n8n 配置使用独立持久化目录或命名卷
- 发布清单测试扫描常见明文 Token 模式

## 质量门禁

Workflow Center v0.1.0 发布必须同时满足：

- Pytest 全量通过
- Ruff 全量通过
- Git diff 格式检查通过
- API 与 n8n 容器健康
- n8n 版本为 2.36.8
- n8n 容器可以访问 FastAPI `/health`
- OpenAPI 包含 5 个工作流运行接口
- 7 个工作流文件均可解析且通过可移植性检查
- Day 41 五类真实场景结果保持有效

2026-09-04 最终结果为：`81 passed`、Ruff 全部通过、API 与 n8n 容器均为
`healthy`、n8n 到 FastAPI 健康检查成功、OpenAPI 包含 5 个工作流路径。

n8n 安全审计同时标记了无认证 Webhook、高能力 HTTP Request/Code 节点、一个
未使用 Credential 和可用的新补丁版本。这些项目已记录在发布说明中；它们是
本地 v0.1.0 的部署边界与后续加固事项，不是明文密钥泄露。

## 当前限制

- 运行接口尚未增加认证、租户隔离和限流
- Day 40 日报仍以固定记录作为可复现实验基线
- Credential 和 Error Workflow 需要在导入目标实例手动绑定
- 无认证 Webhook 只允许在本机或可信网络使用
- 当前冻结 n8n 2.36.8；升级到新补丁版本前必须执行兼容性回归
- 当前部署适合本地学习、内部演示和单机验证，不是高可用生产架构

## Week 6 成果

Week 6 已完成从最小 n8n 节点到可发布工作流组件的完整闭环。Workflow Center
v0.1.0 已具备接收业务事件、调用 AI、人工兜底、运行留痕、错误恢复、版本控制
和发布验收能力，为 Week 7 接入飞书、企业微信和 CRM 奠定了统一运行基础。

详细发布步骤见 [Workflow Center v0.1.0 发布说明](workflow-center-v0.1.md)。
