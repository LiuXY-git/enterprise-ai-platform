# 多文档自动索引

## 目标

上传文档后自动完成文本切分、Embedding 和 Chroma 索引，
使 RAG 可以在多个企业文档之间检索。

## 当前流程

```text
上传文档
→ 解析文本
→ 创建 SQLite 记录
→ Chunk 切分
→ 生成 Embedding
→ 写入 Chroma
→ 更新文档状态
```