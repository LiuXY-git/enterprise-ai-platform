# Week 4 总结：Knowledge Hub 产品化

Week 4 的目标是将 Week 3 完成的 RAG v1 闭环继续产品化，并准备发布 Knowledge Hub v1.0.0。

## 本周完成内容

### Day 22：多文档自动索引

- 上传 PDF、DOCX 或 Markdown 文档后自动建立向量索引
- 将文档文本切分为多个 Chunk
- 为 Chunk 批量生成 Embedding
- 将向量和来源元数据写入 Chroma
- 增加 `indexing`、`indexed` 和 `index_failed` 状态
- 支持在多个上传文档之间进行检索

### Day 23：RAG 检索参数优化

- 建立 7 个黄金问题作为检索基准
- 对比不同 Chunk Size、Overlap 和 Top K
- 使用 Hit 和 MRR 衡量检索效果
- 最终选择 Chunk Size 200、Overlap 50、Top K 3
- 最佳实验取得 7/7 来源命中率和 0.762 MRR
- 增加重复检索结果过滤

### Day 24：LLM 模型切换

- 抽离统一 LLM 配置
- 支持 DeepSeek
- 支持通义千问
- 通过 `LLM_PROVIDER` 选择模型提供商
- 通过环境变量配置 API Key、Base URL 和模型名称
- 使用 Qwen3.7-Plus 完成真实接口验收
- 模型提供商不可用时返回明确错误

### Day 25：Docker 部署

- 完善后端 Dockerfile
- 使用 Docker Compose 构建和启动服务
- 增加容器健康检查
- 持久化 SQLite、Chroma、日志和模型缓存
- 使用非 root 用户运行服务
- 完成容器内健康接口和 RAG 接口验收

### Day 26：API 文档

- 完善 FastAPI 应用信息
- 增加 OpenAPI Tag 和接口说明
- 为请求和响应模型增加字段描述与示例
- 记录主要成功和错误响应
- 完善 Swagger 和 ReDoc
- 新增完整 API 使用文档
- 增加 OpenAPI 自动化测试

### Day 27：Demo 准备

- 准备 IT 故障响应制度演示文档
- 准备差旅报销制度演示文档
- 设计跨文档检索问题
- 编写 3 至 5 分钟录制脚本
- 编写 Demo 验收标准
- 视频录制根据安排暂缓

### Day 28：v1.0.0 发布准备

- 将 OpenAPI 版本升级为 `1.0.0`
- 将 Docker 镜像升级为 `enterprise-ai-platform:1.0.0`
- 更新 API 示例和黄金问题版本答案
- 新增 CHANGELOG
- 新增 v1.0.0 发布说明
- 整理 Week 4 总结
- 正式标签和 GitHub Release 等待 Demo 完成后创建

## Knowledge Hub v1.0.0 能力

当前发布候选版本已经形成以下完整流程：

1. 用户上传企业文档
2. 系统解析并保存文档信息
3. 系统自动切分文本
4. 系统生成并保存向量索引
5. 用户提交业务问题
6. 系统跨文档检索相关 Chunk
7. 系统构建受约束的 RAG Prompt
8. LLM 根据来源生成回答
9. API 返回回答和可核验来源

## 主要 API

- `GET /health`：检查服务运行状态
- `POST /chat`：基础聊天接口
- `POST /upload`：上传、解析并索引文档
- `POST /rag/query`：检索相关文档片段
- `POST /rag/answer`：生成带来源引用的回答

## 工程化成果

- FastAPI 分层结构
- Pydantic 请求和响应模型
- SQLite 文档元数据
- Chroma 向量数据库
- 可配置 LLM Provider
- Docker 和 Docker Compose
- Swagger、ReDoc 和 OpenAPI
- Pytest 自动化测试
- Ruff 代码规范检查
- 学习文档、部署文档和发布文档

## 质量状态

发布候选版本已完成以下最终验收：

- 23 项自动化测试全部通过
- Ruff 检查通过
- OpenAPI 版本为 `1.0.0`
- Docker 容器状态为 `healthy`
- `/health` 返回 `status: ok`
- 上传文档后状态为 `indexed`
- 跨文档检索返回正确来源
- 千问生成带来源引用的回答

ChromaDB 在 Python 3.14 下仍会产生一条弃用警告，目前不影响功能和测试结果。

## 当前限制

- 暂未实现用户认证和权限控制
- 文档解析和索引仍是同步流程
- 暂未提供文档管理前端
- 暂未提供生产级监控和告警
- 修改 LLM Provider 后需要重启服务
- Demo 视频尚未录制
- `v1.0.0` 标签和 GitHub Release 尚未创建

## 当前发布状态

Knowledge Hub v1.0.0 当前为发布候选版本。

代码、文档和自动化验收完成后可以继续进入下一阶段学习。Demo 视频、Git 标签和 GitHub Release 将在收到录制通知后补齐。

## 下一阶段

下一阶段进入 Enterprise Workflow Center，开始学习和实践企业 AI 自动化工作流。
