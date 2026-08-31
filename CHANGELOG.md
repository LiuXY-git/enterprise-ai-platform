# Changelog

本文件记录 Enterprise AI Platform 的主要版本变化。

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
