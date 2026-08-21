# RAG 黄金问题集

以下问题用于测试和比较 RAG 系统效果。

## 问题 1

问题：项目支持上传哪些文档格式？

预期答案：PDF、DOCX 和 Markdown。

允许来源：README.md 或 docs/week-2-summary.md

## 问题 2

问题：如何使用 Docker 启动项目？

预期答案：运行 `docker compose up --build`。

预期来源：README.md

## 问题 3

问题：健康检查接口是什么？

预期答案：`GET /health`。

预期来源：README.md

## 问题 4

问题：数据库保存了哪些文档信息？

预期答案：文件名、文件类型、Content-Type、大小、状态和创建时间。

允许来源：docs/database.md 或 docs/week-2-summary.md

## 问题 5

问题：当前项目版本是多少？

预期答案：v0.3.0。

预期来源：README.md

## 问题 6

问题：Docker、FastAPI、Routers 和 Services 之间是什么关系？

预期答案：用户通过 Docker 暴露的端口访问 FastAPI，FastAPI 将请求交给 Routers，Routers 调用 Services 完成业务处理。

预期来源：docs/architecture.md

## 问题 7

问题：Week 3 完成了哪些 RAG 功能？

预期答案：完成文档切分、Embedding、Chroma 检索、受约束回答和来源引用。

预期来源：docs/week-3-summary.md