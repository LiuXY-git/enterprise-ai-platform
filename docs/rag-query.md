# RAG Query 检索

## 检索流程

```text
用户问题
  ↓
生成问题 Embedding
  ↓
查询 Chroma
  ↓
按照距离排序
  ↓
返回最相关的 Chunk
```