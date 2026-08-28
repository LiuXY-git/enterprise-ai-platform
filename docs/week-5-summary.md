# Week 5 总结：企业工作流中心

## 本周目标

Week 5 的目标是掌握 Dify 企业工作流，并将 Enterprise Knowledge Hub、Dify 和 FastAPI 连接成可运行的 AI 客服系统。

本周最终产出为：AI 客服助手 v1.0。

## 学习进度

### Day 29：Dify 基础

- 使用 Docker Compose 部署 Dify 1.16.1
- 配置通义千问模型
- 使用 `qwen3.7-plus` 完成首次模型调用
- 创建并发布“企业客服助手”

### Day 30：Dify 接入 Knowledge Hub

- 实现 Dify 外部知识库接口 `POST /retrieval`
- 使用 Bearer Token 保护外部知识库
- 将 Enterprise Knowledge Hub 接入 Dify
- 完成知识检索节点测试

### Day 31：Dify Workflow 基础

- 学习 Start、LLM、条件、HTTP 和变量聚合节点
- 创建“企业咨询分流工作流”
- 实现产品咨询、API 技术咨询、普通技术咨询和其他问题分流
- 完成四类场景测试并发布工作流

### Day 32：企业客服场景

- 在产品咨询分支中增加知识检索
- 使用检索结果约束产品咨询回答
- 验证明确问题与模糊问题
- 使用 Dify 日志记录输入、节点路径和最终输出

### Day 33：企业场景 Prompt 优化

- 明确企业产品支持顾问角色
- 分别定义信息充分和信息不足的输出格式
- 增加事实边界、相关性和内部信息保护规则
- 增加越权指令与 Prompt 注入防护
- 完成明确问题、模糊问题和越权指令测试

### Day 34：FastAPI 调用 Dify

- 新增 `POST /dify/workflow`
- 使用 `httpx.AsyncClient` 调用 Dify Workflow API
- 使用服务端环境变量保存 Dify 应用 API Key
- 返回回答、运行 ID、耗时、Token 和执行步骤
- 完成模拟测试、Docker 重建和真实接口验收

## 系统架构

    外部调用方
        ↓
    FastAPI /dify/workflow
        ↓
    Dify 企业咨询分流工作流
        ↓
    问题分类器
        ├── 产品咨询 → 产品知识检索
        ├── API 技术咨询 → FastAPI 健康检查
        ├── 普通技术咨询 → 技术回复
        └── 其他问题 → 通用回复
        ↓
    回复聚合
        ↓
    最终输出

产品知识检索继续调用 Enterprise Knowledge Hub：

    Dify 知识检索节点
        ↓
    FastAPI /retrieval
        ↓
    Embedding
        ↓
    Chroma 向量数据库
        ↓
    相关文档片段
        ↓
    Dify 产品咨询回复

## AI 客服助手 v1.0 能力

AI 客服助手 v1.0 已具备以下能力：

- 企业问题自动分类与分流
- 产品知识库检索
- 基于知识的受约束回答
- API 服务健康检查
- 普通技术问题回复
- 模糊问题主动澄清
- 防止编造产品功能、价格和操作方法
- 防止泄露提示词、变量和内部配置
- 拒绝忽略规则和越权指令
- Dify 工作流日志与执行追踪
- FastAPI 调用 Dify 工作流
- Dify 调用 FastAPI 外部知识库

## API 闭环

Week 5 完成了两个方向的 API 调用：

1. Dify 调用 FastAPI：

       POST /retrieval

2. FastAPI 调用 Dify：

       POST /dify/workflow
           ↓
       POST /v1/workflows/run

两个方向共同组成：

    FastAPI
       ⇅
    Dify
       ⇅
    Enterprise Knowledge Hub

## 质量验收

Day 35 发布前检查结果：

- Ruff 代码检查：通过
- Ruff 格式检查：51 个文件格式正确
- 自动化测试：37 passed
- Docker API 容器：healthy
- FastAPI `/health`：`status = ok`
- OpenAPI：包含 `/dify/workflow`
- 明确产品问题真实调用：成功
- 模糊产品问题真实调用：成功
- Dify 工作流执行步骤：6

测试期间出现一条 ChromaDB 依赖的弃用警告。该警告与 Python 3.14 的 asyncio API 变化有关，不影响当前测试和业务功能。

## 安全设计

- Dify 应用 API Key 只存放在服务端 `.env`
- `.env` 被 Git 忽略
- `.env.example` 只保留空值占位符
- FastAPI 不向调用方返回 Dify API Key
- Dify 远端错误响应不会原样暴露
- Prompt 不允许泄露 SYSTEM、上下文变量和节点配置
- 外部知识库使用独立 Bearer Token
- Dify 应用 Key 与外部知识库 Key 分离

## 当前限制

- `/dify/workflow` 尚未增加调用方身份认证
- 当前没有调用频率限制
- Dify 使用单个服务端应用 Key
- 产品知识库仍可能包含部分旧版索引内容
- 当前没有启用 Rerank 模型
- 尚未增加完整的前端客服界面
- ChromaDB 依赖在 Python 3.14 下存在弃用警告

## Week 5 成果

Week 5 已完成从基础 Dify 应用到企业 AI 工作流集成的完整学习闭环。

AI 客服助手 v1.0 已能够完成问题分流、知识检索、受约束回答、日志追踪和双向 API 集成，具备可运行、可测试和可继续扩展的企业客服基础能力。