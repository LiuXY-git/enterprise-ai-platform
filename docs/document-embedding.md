# 文档 Embedding 流程

## 目标

将真实文档切分成 Chunk，为每个 Chunk 生成 Embedding，
并保存到 Chroma 向量数据库。

## 当前流程

```text
文档
  ↓
读取文本
  ↓
固定长度切分
  ↓
生成 Embedding
  ↓
保存到 Chroma
```

## 当前切分参数

| 参数 | 当前值 |
| --- | ---: |
| chunk_size | 200 |
| overlap | 50 |

## Embedding 模型

当前使用 Chroma 的 DefaultEmbeddingFunction。

它在本地运行 all-MiniLM-L6-v2 模型，每个 Chunk 生成一个
384 维向量。

## Chroma Collection

真实文档向量保存在：

```text
enterprise_document_chunks
```

Day 17 的三维测试向量保存在：

```text
enterprise_documents
```

两个 Collection 分开保存，因为三维向量和 384 维向量不能
放在同一个 Collection 中。

## 每条记录包含的内容

| 字段 | 作用 |
| --- | --- |
| id | Chunk 唯一编号 |
| document | Chunk 原始文本 |
| embedding | 模型生成的 384 维向量 |
| document_id | 所属文档 |
| source | 来源文件 |
| chunk_index | Chunk 顺序 |
| chunk_size | 切分长度 |
| overlap | 重叠长度 |

## 当前状态

- 已实现文档 Chunk 的 Embedding 和向量存储
- 已实现问题向量检索
- `/rag/query` 可以返回最相关的 Chunk
- `/rag/answer` 可以生成带来源的自然语言回答
- 当前通过实验程序建立文档索引

## 当前限制

- 上传接口暂未自动触发 Embedding
- 当前模型的中文检索效果仍需继续测试