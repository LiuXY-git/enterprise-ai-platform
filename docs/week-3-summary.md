# Week 3 总结：RAG v1

## 本周目标

完成企业知识库的第一版 RAG 闭环。

## 已完成功能

- 实现文本 Chunk 切分
- 使用 Chroma 默认 Embedding 模型生成向量
- 将文档 Chunk 保存到 Chroma
- 根据用户问题检索相关 Chunk
- 构造受约束的 RAG Prompt
- 调用 LLM 生成自然语言回答
- 返回回答对应的引用来源
- 增加 RAG 自动化测试
- 使用黄金问题集进行验收

## 当前流程

```text
文档
→ Chunk
→ Embedding
→ Chroma
→ 问题检索
→ Prompt
→ LLM
→ 回答与来源
```