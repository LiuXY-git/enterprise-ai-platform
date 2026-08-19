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