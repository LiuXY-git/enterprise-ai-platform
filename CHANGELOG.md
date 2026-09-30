# Changelog

本文件记录 Enterprise AI Platform 的主要版本变化。

## [Agent Center 0.1.0] - 2026-09-21

2026-09-21 完成 Agent Center 内容定版，平台 API 保持 1.0.0。远端发布状态以 [GitHub Release](https://github.com/LiuXY-git/enterprise-ai-platform/releases/tag/agent-center-v0.1.0) 为准；清单定版不代表远端发布已完成。范围见 [版本说明](docs/week-9.md#agent-center-v0.1)。

### Added

- Agent 架构与静态推演、LangGraph 模拟状态图。
- 结构化模型任务规划、SQLite 模拟进度与异常退出恢复。
- 销售跟进场景契约、模型报告 Prompt 与证据核对。
- 版本清单、文档入口、离线发布检查与 Week 9 总结。

### Quality

- 本轮分环境执行 202 项实验测试和 17 项发布检查，共 219 项离线测试。
- 沿用 Day 59 的 2 次及 Day 62 的 5 次 Qwen 虚构场景真实验证，本轮 0 次新模型请求。

### Limitations

- 尚无真实业务工具、Agent HTTP API 或销售报告检查点整合；各实验保留明确的模拟与真实验证边界。
- Agent Center 远端发布状态、Day 55 视频补录和 Workflow Center v1.0.0 发布继续单独跟踪。

## [Workflow Center 1.0.0] - Unreleased

2026-09-17 完成 Day 56 发布候选准备，平台 API 保持 `1.0.0`。本项尚未创建组件标签或 GitHub Release；版本范围与状态见 [候选说明](docs/week-8.md#workflow-center-v1.0)。

### Added

- 客服、邮件、销售模板目录、契约说明与离线请求生成器。
- 工作流 JSONL 事件、有限脱敏快照、耗时和 Token 用量来源。
- 分组配置入口、按需校验、显式环境加载与离线脱敏自检。
- 一键启动、部署检查、日志轮转和独立 API 容器重建验证工具。
- 平台使用指南、当前架构、技术选型及后端说明。
- Day 55 演示讲稿、请求包、逐步执行与结果留存工具；Day 56 候选清单及 Week 8 总结。

### Fixed

- PowerShell 构建阶段显式使用 Compose 纯文本进度，处理无效控制台句柄错误。
- 更正历史日志目录说明，实际宿主机路径为 `logs`，容器路径为 `/app/logs`。

### Quality

- 沿用 Day 53 的 506 项全量测试和隔离 API 重建结果，Day 54 文档验证及 Day 55 的 19 项离线/模拟工具检查。
- Day 56 校验候选清单、导出哈希、依赖绑定、交付路径和文档一致性，不冒充新的真实模型或业务验收。

### Deferred

- 维护者于 2026-09-17 同意先推进 Day 56，Day 55 本轮真实业务演示、视频录制与验收延期补齐。材料已准备，视频仍待交付。
- 销售真实通知、通知恢复后的工作流收尾、企业微信真实发送条件和接口加固继续保留现有边界。

## [Workflow Center 0.5.0] - 2026-09-14

Week 7 企业系统集成版本，业务验收及文档已完成。日期为本地版本定版日期；GitHub 发布状态以远端标签和 Release 页面为准。

### Added

- 飞书消息 API、企业微信通知 API，以及各自明确的配置和验收边界。
- 模拟 CRM 客户与跟进记录、事务写入和销售线索跟进工作流。
- AI 分析检查点、CRM 恢复、通知尝试与结果、人工核对及整条回放保护。
- 包含 8 条工作流的 v0.5.0 清单、模型绑定和部署依赖。
- Day 49 独立测试数据脚本、JSON 验收证据、发布说明及 Week 7 总结。

### Fixed

- 验收脚本中有序字典摘要显示为 null 的问题。
- 分析 JSON 字段顺序不同导致验收误报的问题，并支持从该失败位置复用原成功事件续跑。

### Quality

- 沿用 Day 48 全量 415 项测试和 Ruff/节点回归证据。
- Day 49 发布清单及销售工作流相关 21 项测试、Ruff 已通过。
- 新数据回放保护、人工核对与通知重试、Production 正常与重复事件均通过，见 Day 49 验收记录。
- 通知故障验收为状态模拟；销售通知保持 preview。通知恢复后工作流状态收尾仍为待办。

### Release

- 组件目标版本为 0.5.0，平台 API 保持 1.0.0。
- 清单状态为 released，记录本地组件版本定版；标签为 workflow-center-v0.5.0。GitHub 推送与 Release 由维护者执行。

## [Workflow Center 0.1.0] - 2026-09-04

Enterprise AI Platform v1.0.0 内的首个 n8n 工作流自动化组件版本。

### Added

- 增加 7 个覆盖部署、Webhook、AI 调用、邮件处理、日报和错误处理的版本化工作流
- 增加 SQLite `workflow_runs` 运行账本和 5 个工作流管理接口
- 增加重复事件幂等拦截、自动失败记录和最多 3 次失败回放
- 增加机器可读发布清单、导入顺序、发布顺序和手动绑定说明
- 增加 Workflow Center v0.1.0 发布说明和 Week 6 总结

### Changed

- OpenAPI 概述扩展为知识库、RAG 与工作流自动化 API
- API 文档增加工作流运行接口、状态转换和错误说明

### Quality

- 工作流导出文件保持未激活并移除实例 ID、Webhook ID 和 Credential 引用
- 自动化检查覆盖数据库、服务、路由、工作流结构、发布清单和敏感信息
- 真实验收覆盖成功、人工审核、重复、自动失败和失败回放

### Release

- 组件版本为 `0.1.0`，平台 API 版本保持 `1.0.0`
- 正式 Git 标签使用 `workflow-center-v0.1.0`，避免与平台历史标签冲突

## [1.0.0] - 2026-08-31

Enterprise AI Platform 首个正式版本，包含 Knowledge Hub v1.0.0 和 AI 客服助手 v1.0。

### Added

- 支持上传并解析 PDF、DOCX 和 Markdown 文档
- 上传文档后自动进行文本切分、Embedding 和向量索引
- 支持跨多个文档进行语义检索
- 提供 `/rag/query` 文档片段检索接口
- 提供 `/rag/answer` 带来源引用的自然语言回答接口
- 支持 DeepSeek 和通义千问模型切换
- 支持通过环境变量配置 LLM Provider、模型和 API 地址
- 增加 Docker 镜像、Compose 配置、健康检查和数据持久化
- 完善 Swagger、ReDoc 和 API 使用文档
- 增加 Demo 数据、跨文档问题和录制脚本
- 增加 Dify 外部知识库接口与 Bearer Token 鉴权
- 增加企业咨询分流工作流、受约束回答和日志追踪
- 增加 FastAPI 调用 Dify Workflow API 的 `/dify/workflow` 接口
- 完成 FastAPI / Dify 双向 API 集成和真实链路验收

### Changed

- RAG 默认检索参数调整为 Chunk Size 200、Overlap 50、Top K 3
- 检索过程增加重复结果过滤
- Docker 镜像版本升级为 `enterprise-ai-platform:1.0.0`
- OpenAPI 应用版本升级为 `1.0.0`
- API 示例和黄金问题版本答案升级为 `v1.0.0`

### Quality

- 具备文档索引、模型配置、Prompt、RAG 路由、检索和上传测试
- 正式版本包含 37 项自动化测试
- 使用 Ruff 进行代码规范检查
- 支持 Docker 容器健康检查

### Release

- 完成 AI 客服助手 v1.0 Demo 录制与验收
- 完成 Docker、OpenAPI 和双向真实接口最终验收
- 使用 `v1.0.0` Git 标签标记正式版本
- Demo 视频作为独立发布资产保存，不纳入 Git 仓库

## [0.3.0]

- 完成 RAG v1 闭环
- 增加文本切分、Embedding 和 Chroma 向量检索
- 增加带来源引用的自然语言回答
- 增加 RAG 自动化测试和黄金问题验收

## [0.2.0]

- 支持 PDF、DOCX 和 Markdown 文档上传与解析
- 使用 SQLite 保存文档元数据
- 增加异常处理和运行日志

## [0.1.0]

- 初始化 Enterprise AI Platform
- 创建 FastAPI 服务
- 增加健康检查和基础聊天接口
