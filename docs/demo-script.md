# Knowledge Hub Demo 录制脚本

## 演示目标

在 3～5 分钟内展示 Enterprise AI Platform 如何完成企业文档上传、自动索引、跨文档检索和带来源回答。

演示使用虚构的“星云科技”制度文档，不包含真实企业数据。

## 演示场景

员工需要同时查询两个不同制度：

- P1 级系统故障的响应和升级流程
- 8000 元差旅报销需要哪些人审批

演示问题：

```text
星云科技发生 P1 级故障时，响应和升级流程是什么？差旅报销 8000 元需要哪些人审批？
```

## 录制前准备

- 确认 `.env` 文件处于关闭状态
- 不在画面中显示任何 API Key
- 关闭微信、邮件等可能弹出通知的软件
- 浏览器只保留 Swagger 页面
- VS Code 终端字号调整到容易阅读
- 浏览器缩放调整到 100% 或 110%
- 确认通义千问账户可以正常调用
- 确认 Docker Desktop 正常运行
- 确认麦克风声音清晰
- 将两份演示文档放在容易选择的位置

演示文档：

```text
demo/nebula-it-policy.md
demo/nebula-expense-policy.md
```

## 启动准备

正式录制前执行：

```powershell
docker compose up -d --build
docker compose ps
```

确认容器状态为：

```text
healthy
```

打开 Swagger：

```text
http://127.0.0.1:8000/docs
```

## 时间轴与讲解词

### 00:00～00:25 项目介绍

画面：

- GitHub 项目首页或根目录 README
- 项目名称和功能清单

讲解：

> 这是我开发的 Enterprise AI Platform。当前完成的是 Knowledge Hub 企业知识库模块，它支持 PDF、DOCX 和 Markdown 文档上传、自动向量索引、跨文档检索，以及使用通义千问生成带来源引用的回答。

### 00:25～00:50 工程化能力

画面：

- VS Code 终端
- 执行 `docker compose ps`
- 执行健康检查

命令：

```powershell
docker compose ps
Invoke-RestMethod -Uri http://127.0.0.1:8000/health -Method Get
```

讲解：

> 项目已经完成 Docker 部署。容器包含健康检查、非 root 用户、数据持久化和自动重启配置。这里可以看到容器状态正常，健康检查接口返回 ok。

### 00:50～01:15 API 文档

画面：

- Swagger 首页
- 展示 `system`、`chat`、`documents` 和 `rag` 四个接口分组
- 展开 `/upload` 和 `/rag/answer`

讲解：

> 平台使用 FastAPI 提供接口，并生成完整的 Swagger 和 ReDoc 文档。每个接口都包含请求参数、字段示例、响应结构和错误码说明，便于前端或第三方系统接入。

### 01:15～02:00 上传 IT 制度

画面：

- 展开 `POST /upload`
- 点击 `Try it out`
- 选择 `demo/nebula-it-policy.md`
- 点击 `Execute`
- 展示响应中的 `status` 和 `chunk_count`

讲解：

> 首先上传星云科技的 IT 故障响应制度。上传后，平台会提取文本、保存文档元数据、切分 Chunk、生成 Embedding，并写入 Chroma 向量数据库。接口返回 indexed，表示文档已经可以参与检索。

### 02:00～02:35 上传差旅制度

画面：

- 再次调用 `POST /upload`
- 选择 `demo/nebula-expense-policy.md`
- 点击 `Execute`
- 展示 `filename`、`status` 和 `chunk_count`

讲解：

> 接着上传第二份差旅报销制度。两份文档会进入同一个企业知识库，后续问题可以跨多个文档检索。

### 02:35～03:10 验证跨文档检索

画面：

- 展开 `POST /rag/query`
- 点击 `Try it out`
- 输入请求体
- 点击 `Execute`
- 展示结果中的两个来源文件

请求体：

```json
{
  "question": "星云科技发生 P1 级故障时，响应和升级流程是什么？差旅报销 8000 元需要哪些人审批？",
  "top_k": 5
}
```

讲解：

> 我先调用纯检索接口，不经过大语言模型。可以看到返回结果同时来自 IT 故障制度和差旅报销制度，说明系统已经具备跨文档检索能力。distance 越小，通常表示文档片段与问题越相关。

### 03:10～04:00 生成带来源回答

画面：

- 展开 `POST /rag/answer`
- 使用相同问题和 `top_k`
- 点击 `Execute`
- 展示自然语言回答
- 展示 `[来源1]`、`[来源2]`
- 展示 `sources` 中的文件名和原文

请求体：

```json
{
  "question": "星云科技发生 P1 级故障时，响应和升级流程是什么？差旅报销 8000 元需要哪些人审批？",
  "top_k": 5
}
```

讲解：

> 接下来调用完整的 RAG 回答接口。系统先检索相关内容，再将受约束的 Prompt 和来源文本发送给通义千问。回答指出，P1 故障需要在 15 分钟内响应，30 分钟未响应时升级联系值班经理；8000 元报销需要直属部门负责人和财务负责人共同审批。回答中的来源标签可以和下面的原文逐一对应，从而降低模型幻觉并支持结果追溯。

### 04:00～04:25 自动化测试

画面：

- VS Code 终端
- 运行测试或展示测试结果

命令：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

讲解：

> 除了人工演示，项目还包含上传、索引、检索、模型配置、RAG 回答和 OpenAPI 文档测试。目前全部测试通过，保证核心流程可以持续回归。

### 04:25～04:45 总结

画面：

- README 功能清单
- 或 Swagger 回答结果

讲解：

> 这个项目展示了从企业文档接入到可信问答的完整闭环，同时包含模型切换、Docker 部署、API 文档和自动化测试。下一步会继续完善权限控制、异步任务和生产级监控，并发布 Knowledge Hub v1.0。

## 录制验收清单

- [ ] 视频时长控制在 3～5 分钟
- [ ] 画面中没有出现 API Key
- [ ] Docker 容器显示 healthy
- [ ] `/health` 返回 ok
- [ ] 两份演示文档均上传成功
- [ ] 两份文档状态均为 indexed
- [ ] `/rag/query` 返回两个演示文件
- [ ] `/rag/answer` 返回正确答案
- [ ] 回答包含来源引用
- [ ] 自动化测试通过
- [ ] 讲解包含业务价值和下一步计划

## 失败兜底

如果模型接口临时不可用：

1. 保留 `/rag/query` 的成功结果
2. 检查 `.env` 中的 Provider、模型名称和 API Key
3. 确认容器已在修改配置后重新创建
4. 等待模型服务恢复后重新录制 `/rag/answer`
5. 不在视频中展示 `.env` 文件内容

如果检索结果没有同时出现两个文件：

1. 将 `top_k` 调整为 5
2. 确认两份文件的上传状态为 `indexed`
3. 使用脚本中的完整问题重新查询
4. 检查响应中的 `source` 字段