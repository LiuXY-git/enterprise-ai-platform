# Enterprise AI Platform v1.0.0 发布说明

状态：已于 2026-08-31 完成最终验收并正式发布。

## 版本概述

Knowledge Hub 是 Enterprise AI Platform 的第一个完整产品模块。

v1.0.0 已经形成从企业文档接入到可信问答的完整闭环：

1. 上传企业文档
2. 解析文档文本
3. 自动切分 Chunk
4. 生成 Embedding
5. 写入 Chroma 向量数据库
6. 跨文档检索相关内容
7. 调用 LLM 生成回答
8. 返回可核验的引用来源

在 Knowledge Hub 基础上，v1.0.0 还集成了 Dify 企业咨询分流工作流，形成 FastAPI 调用 Dify、Dify 调用 FastAPI 外部知识库的双向 API 闭环。

## 核心能力

### 文档接入

- 支持 PDF
- 支持 DOCX
- 支持 Markdown
- 使用 SQLite 保存文档元数据
- 上传成功后自动建立向量索引
- 记录文档解析与索引状态

### RAG 检索

- 使用 Embedding 表示问题和文档
- 使用 Chroma 保存并检索向量
- 支持跨多个文档检索
- 默认 Chunk Size 为 200
- 默认 Overlap 为 50
- 默认 Top K 为 3
- 对重复检索结果进行过滤

### 可信回答

- 使用检索结果构建受约束的 Prompt
- 只允许模型根据来源内容回答
- 回答中包含来源编号
- 响应中返回完整来源列表
- 来源包含文件名、Chunk 序号、原文和向量距离

### LLM 模型配置

- 支持 DeepSeek
- 支持通义千问
- 通过环境变量选择模型提供商
- 通过环境变量配置模型名称、API Key 和 Base URL
- 模型服务异常时返回明确错误

### 工程化能力

- FastAPI API 服务
- Swagger API 文档
- ReDoc API 文档
- OpenAPI Schema
- Docker 镜像
- Docker Compose
- 容器健康检查
- SQLite、Chroma 和日志数据持久化
- Pytest 自动化测试
- Ruff 代码检查

## API 接口

| 方法 | 地址 | 作用 |
| --- | --- | --- |
| GET | `/health` | 检查服务运行状态 |
| POST | `/chat` | 基础聊天接口 |
| POST | `/upload` | 上传、解析并索引文档 |
| POST | `/rag/query` | 检索相关文档片段 |
| POST | `/rag/answer` | 生成带来源引用的回答 |
| POST | `/retrieval` | 为 Dify 提供受 Bearer Token 保护的外部知识检索 |
| POST | `/dify/workflow` | 由 FastAPI 调用 Dify 企业咨询分流工作流 |

## 快速启动

复制环境变量示例：

```powershell
if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
}
```

在 `.env` 中配置所使用模型的 API Key，不要将真实密钥提交到 Git。
构建并启动服务：

```powershell
docker compose up -d --build
docker compose ps
```

健康检查：

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/health -Method Get
```

接口文档：

```text
http://127.0.0.1:8000/docs
http://127.0.0.1:8000/redoc
```

停止服务：

```powershell
docker compose down
```

## 质量验收

正式版本的验收结果：

- 自动化测试：37 passed
- Ruff 检查：通过，51 个文件格式正确
- OpenAPI 版本为 `1.0.0`
- Docker 镜像为 `enterprise-ai-platform:1.0.0`
- 容器健康状态为 `healthy`
- `/health` 返回 `status: ok`
- 文档可以成功上传并建立索引
- `/rag/query` 可以返回跨文档来源
- `/rag/answer` 可以生成带引用来源的回答
- `/dify/workflow` 产品问题真实调用成功，共执行 6 步
- Dify 技术分支调用 FastAPI 健康检查成功，共执行 7 步
- Demo 视频完成录制、画面抽检、音轨检测和交付验收

## 当前限制

- 暂未提供用户认证和权限控制
- 文档解析与索引仍在上传请求内同步执行
- 暂未提供文档管理前端
- 暂未提供生产级监控和告警
- 修改 LLM Provider 后需要重启服务
- 暂不支持单个请求临时指定模型
- `/dify/workflow` 尚未增加调用方身份认证和限流
- Dify 使用单个服务端应用 Key
- Demo 公开发布前仍建议进行精剪和响度标准化

## 发布前待办

- [x] 完成 v1.0.0 代码版本升级
- [x] 准备 CHANGELOG
- [x] 准备发布说明
- [x] 完成 Week 4 总结
- [x] 完成全部自动化测试
- [x] 完成 Ruff 检查
- [x] 完成 Docker 发布候选镜像验收
- [x] 完成 Demo 视频录制与验收
- [x] 将 Demo 验收记录加入 README
- [x] 创建 `v1.0.0` Git 标签
- [ ] 按需创建 GitHub Release 并上传精剪后的视频资产

## 发布状态

Enterprise AI Platform v1.0.0 已完成本地正式发布和交付验收。GitHub Release 属于可选的公开发布步骤，可直接基于 `v1.0.0` 标签创建。
