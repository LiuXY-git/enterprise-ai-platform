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

## API 接口

| 请求方法 | 地址 | 作用 |
| --- | --- | --- |
| POST | `/rag/query` | 返回与问题相关的原始 Chunk |
| POST | `/rag/answer` | 根据知识库生成带来源的自然语言回答 |

## 当前参数

| 参数 | 当前值 |
| --- | ---: |
| chunk_size | 200 |
| overlap | 50 |
| top_k | 3 |

## 验收结果

- 自动化测试：10 个测试全部通过
- Ruff 代码检查和格式检查：通过
- 黄金问题 Top-3 来源命中：4/5
- 其中“项目支持上传哪些文档格式？”未命中指定来源 `README.md`
- 实际检索结果包含 `docs/week-2-summary.md`，该文档同样包含正确答案
- 真实模型回答与引用验收：待完成

## 问题记录

第一个黄金问题的 Top-3 结果为：

1. `docs/database.md`
2. `docs/database.md`
3. `docs/week-2-summary.md`

虽然第三个结果包含正确答案，但相关文档的排序仍不理想。该问题暂时记录为检索优化项，留到 Day 23 对比 Chunk、Top-K 和黄金问题的允许来源。
