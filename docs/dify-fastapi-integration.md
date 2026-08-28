# Day 34：FastAPI 调用 Dify 工作流

## 今日目标

- 使用 FastAPI 调用已经发布的 Dify 企业咨询工作流
- 将 Dify 应用 API Key 安全保存在服务端环境变量中
- 返回工作流回答、运行状态和执行元数据
- 完成模拟测试、容器重建和真实端到端验收

## 调用链路

Day 34 建立以下双向集成：

    外部调用方
        ↓
    POST /dify/workflow
        ↓
    Enterprise AI Platform / FastAPI
        ↓ Authorization: Bearer <DIFY_WORKFLOW_API_KEY>
    POST /v1/workflows/run
        ↓
    Dify 企业咨询分流工作流
        ↓
    Enterprise Knowledge Hub 外部知识库
        ↓
    Dify 最终输出
        ↓
    FastAPI 标准响应

Day 30 已实现 Dify 调用 FastAPI 的 `/retrieval`；Day 34 增加反向链路，让 FastAPI 调用 Dify。

## Dify Workflow API

FastAPI 使用以下 Dify 接口：

    POST /v1/workflows/run

请求使用 `blocking` 模式：

```json
{
  "inputs": {
    "user_query": "系统支持哪些文档格式？"
  },
  "response_mode": "blocking",
  "user": "day34-demo-user"
}
```

`user` 是调用方定义的稳定终端用户标识，同一用户后续调用应复用相同值。

## 服务端配置

新增以下环境变量：

```properties
DIFY_API_BASE_URL=http://host.docker.internal/v1
DIFY_WORKFLOW_API_KEY=
DIFY_WORKFLOW_TIMEOUT_SECONDS=120
```

- `DIFY_API_BASE_URL`：FastAPI 容器访问宿主机 Dify 的 API 根地址
- `DIFY_WORKFLOW_API_KEY`：企业咨询分流工作流的应用 API Key
- `DIFY_WORKFLOW_TIMEOUT_SECONDS`：阻塞调用超时时间

实际 API Key 只写入被 Git 忽略的 `.env`，`.env.example` 只保留空值占位符。

## FastAPI 接口

新增：

    POST /dify/workflow

请求示例：

```json
{
  "question": "系统支持哪些文档格式？",
  "user": "day34-demo-user"
}
```

FastAPI 将 `question` 映射到 Dify 的 `inputs.user_query`，并返回：

- `task_id`
- `workflow_run_id`
- `status`
- `answer`
- `outputs`
- `elapsed_time`
- `total_tokens`
- `total_steps`

## 错误处理

- 未配置应用 API Key 时返回 `503`
- 无法连接 Dify 时返回 `503`
- Dify 返回非成功 HTTP 状态时只暴露状态码，不回传可能包含敏感信息的原始响应体
- 工作流状态不是 `succeeded` 时返回执行失败信息
- 响应缺少 `data`、`outputs` 或运行 ID 时返回结构错误
- 无法从最终输出提取文本回答时返回明确错误

## 自动化测试

新增配置、服务和路由测试，覆盖：

- 配置读取、URL 规范化和超时校验
- Bearer Token、请求地址和 Dify 请求体映射
- 工作流回答与运行元数据解析
- 远端错误信息隔离
- FastAPI 成功响应、`503` 映射和请求参数校验
- OpenAPI 标签和 `/dify/workflow` 操作说明

验收结果：

- Ruff 检查通过
- Ruff 格式检查通过
- 自动化测试 `37 passed`

## 真实接口验收

重新构建并启动 Docker 服务后，FastAPI `/health` 返回 `ok`，OpenAPI 中包含 `/dify/workflow`。

### 明确问题

输入：

    系统支持哪些文档格式？

结果：

- Dify 状态：`succeeded`
- 执行步骤：6
- 正确回答支持 PDF、DOCX 和 Markdown
- FastAPI 返回任务 ID、运行 ID、耗时、Token 和最终输出

### 模糊问题

输入：

    产品怎么使用？

结果：

    当前信息不足。
    请问您具体想了解哪个功能模块的使用方法？

通过 API 调用时仍然遵守 Day 33 的两句话 Prompt 约束，证明发布后的工作流与 FastAPI 集成一致。

## 今日成果

FastAPI 已能够使用服务端应用 Key 调用 Dify 企业咨询工作流，完成“外部调用方 → FastAPI → Dify → Knowledge Hub → FastAPI 响应”的闭环。

Day 35 将进行 Week 5 总结并整理 AI 客服助手 v1.0。
