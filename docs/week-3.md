# Week 3：RAG：切分、向量检索与来源回答

学习路线：Day 15–21。

按学习路线归档，计划、实施记录与阶段总结集中在本页。记录中的版本、验收结果和“当前”均对应各节写作时点；后续修订会单独注明。

[总目录](README.md#按周阅读) · [上一周](week-2.md) · [下一周](week-4.md)

<a id="contents"></a>

## 本周目录

- [Embedding 学习笔记](#embedding)
- [Chunk 文本切分](#chunking)
- [Chroma 向量数据库](#vector-database)
- [文档 Embedding 流程](#document-embedding)
- [RAG Query 检索](#rag-query)
- [RAG 提示词与回答生成](#rag-prompt)
- [RAG 黄金问题集](#rag-golden-questions)
- [本周总结（阶段记录）](#summary)

---

<a id="embedding"></a>

## Embedding 学习笔记

<a id="embedding-什么是-embedding"></a>

### 什么是 Embedding

Embedding 是把文本转换为数字向量的过程。

例如：

```text
员工如何申请年假
↓
[0.12, 0.88, 0.31, ...]
```

---

<a id="chunking"></a>

## Chunk 文本切分

<a id="chunking-chunk-是什么"></a>

### Chunk 是什么

Chunk 是从长文档中切分出来的一小段文本。

RAG 系统不会直接检索整篇长文档，而是先将文档切成多个
Chunk，再对每个 Chunk 生成 Embedding。

<a id="chunking-为什么需要-chunk"></a>

### 为什么需要 Chunk

- 长文档可能超过模型上下文限制
- 整篇文档生成一个向量会丢失局部细节
- 小块文本更容易进行精准检索
- 可以只把相关内容交给大模型

<a id="chunking-当前实现的切分策略"></a>

### 当前实现的切分策略

<a id="chunking-按段落切分"></a>

#### 按段落切分

根据文档中的空行切分。

优点：

- 保留自然段落结构
- 内容容易理解

缺点：

- 不同段落长度可能相差很大
- 特别长的段落仍然需要再次切分

<a id="chunking-固定长度切分"></a>

#### 固定长度切分

按照固定字符数量切分。

优点：

- Chunk 长度比较稳定
- 实现简单

缺点：

- 可能从句子中间切断
- 可能丢失上下文

<a id="chunking-重叠切分"></a>

#### 重叠切分

相邻 Chunk 保留一部分重复内容。

优点：

- 减少边界处的信息丢失
- 保留更多上下文

缺点：

- 会产生重复数据
- 增加 Embedding 和存储成本

<a id="chunking-实验记录"></a>

### 实验记录

| 策略 | chunk_size | overlap | Chunk 数量 | 观察 |
| --- | ---: | ---: | ---: | --- |
| 按段落 | - | - | 16 | 切分比较自然 |
| 固定长度 | 200 | 0 | 4 | 容易切断句子 |
| 固定长度 | 200 | 50 | 4 | 上下文更加完整 |
| 固定长度 | 400 | 50 | 2 | Chunk 数量更少 |

<a id="chunking-当前结论"></a>

### 当前结论

Chunk 太小容易失去上下文，Chunk 太大会降低检索精度。

目前先使用字符数量理解切分原理。后续接入真实 Embedding
模型时，再根据 Token 数量和检索结果调整参数。

---

<a id="vector-database"></a>

## Chroma 向量数据库

<a id="vector-database-向量数据库是什么"></a>

### 向量数据库是什么

向量数据库用于保存和检索 Embedding 向量。

普通数据库通常根据 ID、名称或时间查询数据；向量数据库可以
根据向量之间的距离，查找语义上相似的内容。

<a id="vector-database-为什么使用-chroma"></a>

### 为什么使用 Chroma

- 支持保存文本和向量
- 支持保存来源等元数据
- 支持向量相似度检索
- 可以将数据持久化到本地磁盘
- 适合学习和构建 RAG 原型

<a id="vector-database-当前存储位置"></a>

### 当前存储位置

```text
data/chroma/
```

---

<a id="document-embedding"></a>

## 文档 Embedding 流程

<a id="document-embedding-目标"></a>

### 目标

将真实文档切分成 Chunk，为每个 Chunk 生成 Embedding，
并保存到 Chroma 向量数据库。

<a id="document-embedding-当前流程"></a>

### 当前流程

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

<a id="document-embedding-当前切分参数"></a>

### 当前切分参数

| 参数 | 当前值 |
| --- | ---: |
| chunk_size | 200 |
| overlap | 50 |

<a id="document-embedding-embedding-模型"></a>

### Embedding 模型

当前使用 Chroma 的 DefaultEmbeddingFunction。

它在本地运行 all-MiniLM-L6-v2 模型，每个 Chunk 生成一个
384 维向量。

<a id="document-embedding-chroma-collection"></a>

### Chroma Collection

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

<a id="document-embedding-每条记录包含的内容"></a>

### 每条记录包含的内容

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

<a id="document-embedding-当前状态"></a>

### 当前状态

- 已实现文档 Chunk 的 Embedding 和向量存储
- 已实现问题向量检索
- `/rag/query` 可以返回最相关的 Chunk
- `/rag/answer` 可以生成带来源的自然语言回答
- 当前通过实验程序建立文档索引

<a id="document-embedding-当前限制"></a>

### 当前限制

- 上传接口暂未自动触发 Embedding
- 当前模型的中文检索效果仍需继续测试

---

<a id="rag-query"></a>

## RAG Query 检索

<a id="rag-query-检索流程"></a>

### 检索流程

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

---

<a id="rag-prompt"></a>

## RAG 提示词与回答生成

<a id="rag-prompt-目标"></a>

### 目标

将用户问题和向量数据库检索出的相关文档片段一起发送给 DeepSeek，让模型根据项目资料生成回答。

<a id="rag-prompt-工作流程"></a>

### 工作流程

```text
用户问题
→ Embedding 向量化
→ Chroma 检索相关 Chunk
→ 构造 RAG 提示词
→ DeepSeek 生成答案
→ 返回答案和引用来源
```

<a id="rag-prompt-提示词结构"></a>

### 提示词结构

RAG 提示词主要包含三部分：

1. 系统要求
2. 用户问题
3. 检索到的文档片段

系统提示词要求模型：

- 只能根据提供的资料回答
- 不确定时明确说明资料不足
- 不允许编造项目中不存在的信息
- 在答案中标注引用来源

<a id="rag-prompt-模型配置"></a>

### 模型配置

项目使用 DeepSeek V4 Flash。

本地 `.env` 配置：

```env
DEEPSEEK_API_KEY=你的DeepSeek密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
```

真实密钥只能保存在 `.env` 中，不能写入本文档或提交到 GitHub。

<a id="rag-prompt-api-接口"></a>

### API 接口

```text
POST /rag/answer
```

请求示例：

```json
{
  "question": "项目支持上传哪些文档格式？",
  "top_k": 3
}
```

响应包含：

- `question`：用户提出的问题
- `answer`：DeepSeek 根据资料生成的回答
- `sources`：回答所使用的文档来源
- `distance`：问题与文档片段之间的向量距离

<a id="rag-prompt-测试结果"></a>

### 测试结果

测试问题：

```text
项目支持上传哪些文档格式？
```

模型能够根据检索结果回答项目支持 PDF、DOCX 和 Markdown，并返回对应的引用来源。

<a id="rag-prompt-注意事项"></a>

### 注意事项

- `distance` 越小，通常表示文档片段与问题越相关。
- `top_k` 表示返回多少个候选文档片段。
- 检索结果不准确时，可以调整 Chunk 大小、重叠长度和相关性阈值。
- DeepSeek 只负责根据检索结果组织答案，项目资料仍然来自本地向量数据库。

---

<a id="rag-golden-questions"></a>

## RAG 黄金问题集

> 问题集始建于 Week 3，包含 Day 23 等后续修订。允许来源已更新为合并后的文件名；文档内容变化后，旧检索分数不能当作本次重新测得的结果。

以下问题用于测试和比较 RAG 系统效果。

<a id="rag-golden-questions-问题-1"></a>

### 问题 1

问题：项目支持上传哪些文档格式？

预期答案：PDF、DOCX 和 Markdown。

允许来源：README.md 或 docs/week-2.md

<a id="rag-golden-questions-问题-2"></a>

### 问题 2

问题：如何使用 Docker 启动项目？

预期答案：运行 `docker compose up --build`。

预期来源：README.md

<a id="rag-golden-questions-问题-3"></a>

### 问题 3

问题：健康检查接口是什么？

预期答案：`GET /health`。

预期来源：README.md

<a id="rag-golden-questions-问题-4"></a>

### 问题 4

问题：数据库保存了哪些文档信息？

预期答案：文件名、文件类型、Content-Type、大小、状态和创建时间。

允许来源：docs/week-2.md

<a id="rag-golden-questions-问题-5"></a>

### 问题 5

问题：当前项目版本是多少？

预期答案：v1.0.0。

预期来源：README.md

<a id="rag-golden-questions-问题-6"></a>

### 问题 6

问题：Docker、FastAPI、Routers 和 Services 之间是什么关系？

预期答案：用户通过 Docker 暴露的端口访问 FastAPI，FastAPI 将请求交给 Routers，Routers 调用 Services 完成业务处理。

预期来源：docs/week-1.md

<a id="rag-golden-questions-问题-7"></a>

### 问题 7

问题：Week 3 完成了哪些 RAG 功能？

预期答案：完成文档切分、Embedding、Chroma 检索、受约束回答和来源引用。

预期来源：docs/week-3.md

---

<a id="summary"></a>

## 本周总结（阶段记录）

> 下方是 Week 3 当时的检索结果，来源文件名保持原记录；重新运行时使用本页黄金问题中的 Week 路径。

<a id="summary-本周目标"></a>

### 本周目标

完成企业知识库的第一版 RAG 闭环。

<a id="summary-已完成功能"></a>

### 已完成功能

- 实现文本 Chunk 切分
- 使用 Chroma 默认 Embedding 模型生成向量
- 将文档 Chunk 保存到 Chroma
- 根据用户问题检索相关 Chunk
- 构造受约束的 RAG Prompt
- 调用 LLM 生成自然语言回答
- 返回回答对应的引用来源
- 增加 RAG 自动化测试
- 使用黄金问题集进行验收

<a id="summary-当前流程"></a>

### 当前流程

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

<a id="summary-api-接口"></a>

### API 接口

| 请求方法 | 地址 | 作用 |
| --- | --- | --- |
| POST | `/rag/query` | 返回与问题相关的原始 Chunk |
| POST | `/rag/answer` | 根据知识库生成带来源的自然语言回答 |

<a id="summary-当前参数"></a>

### 当前参数

| 参数 | 当前值 |
| --- | ---: |
| chunk_size | 200 |
| overlap | 50 |
| top_k | 3 |

<a id="summary-验收结果"></a>

### 验收结果

- 自动化测试：10 个测试全部通过
- Ruff 代码检查和格式检查：通过
- 黄金问题 Top-3 来源命中：4/5
- 其中“项目支持上传哪些文档格式？”未命中指定来源 `README.md`
- 实际检索结果包含 `docs/week-2-summary.md`，该文档同样包含正确答案
- 真实模型回答与引用验收：待完成

<a id="summary-问题记录"></a>

### 问题记录

第一个黄金问题的 Top-3 结果为：

1. `docs/database.md`
2. `docs/database.md`
3. `docs/week-2-summary.md`

虽然第三个结果包含正确答案，但相关文档的排序仍不理想。该问题暂时记录为检索优化项，留到 Day 23 对比 Chunk、Top-K 和黄金问题的允许来源。
