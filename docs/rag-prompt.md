# RAG 提示词与回答生成

## 目标

将用户问题和向量数据库检索出的相关文档片段一起发送给 DeepSeek，让模型根据项目资料生成回答。

## 工作流程

```text
用户问题
→ Embedding 向量化
→ Chroma 检索相关 Chunk
→ 构造 RAG 提示词
→ DeepSeek 生成答案
→ 返回答案和引用来源
```

## 提示词结构

RAG 提示词主要包含三部分：

1. 系统要求
2. 用户问题
3. 检索到的文档片段

系统提示词要求模型：

- 只能根据提供的资料回答
- 不确定时明确说明资料不足
- 不允许编造项目中不存在的信息
- 在答案中标注引用来源

## 模型配置

项目使用 DeepSeek V4 Flash。

本地 `.env` 配置：

```env
DEEPSEEK_API_KEY=你的DeepSeek密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
```

真实密钥只能保存在 `.env` 中，不能写入本文档或提交到 GitHub。

## API 接口

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

## 测试结果

测试问题：

```text
项目支持上传哪些文档格式？
```

模型能够根据检索结果回答项目支持 PDF、DOCX 和 Markdown，并返回对应的引用来源。

## 注意事项

- `distance` 越小，通常表示文档片段与问题越相关。
- `top_k` 表示返回多少个候选文档片段。
- 检索结果不准确时，可以调整 Chunk 大小、重叠长度和相关性阈值。
- DeepSeek 只负责根据检索结果组织答案，项目资料仍然来自本地向量数据库。