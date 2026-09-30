# Day 24：LLM 模型切换

## 学习目标

让 RAG 回答服务支持在 DeepSeek 和通义千问之间切换，同时保持 `/rag/answer` 接口和 RAG 业务流程不变。

## 支持的模型服务

| Provider | API Key 环境变量 | 默认模型 |
| --- | --- | --- |
| deepseek | DEEPSEEK_API_KEY | deepseek-v4-flash |
| qwen | DASHSCOPE_API_KEY | qwen3.7-plus |

## 配置结构

Day 52 起模型配置实现集中在 `backend/app/settings.py`；`backend/app/services/llm_config.py` 保留兼容导入入口。应用启动时显式加载项目根目录 `.env`，进程环境变量优先。

配置模块负责：

- 读取当前 LLM Provider
- 读取对应的 API Key
- 读取 Base URL
- 读取模型名称
- 检查必要配置
- 拒绝不支持的 Provider

`llm_service.py` 不再直接读取某个模型供应商的环境变量，只使用统一的 LLM 配置对象。

## 切换到 DeepSeek

在本地 `.env` 中配置：

```env
LLM_PROVIDER=deepseek

DEEPSEEK_API_KEY=本地密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
```

修改后需要重启 FastAPI。

## 切换到通义千问

在本地 `.env` 中配置：

```env
LLM_PROVIDER=qwen

DASHSCOPE_API_KEY=本地密钥
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_MODEL=qwen3.7-plus
```

修改后需要重启 FastAPI。

千问通过阿里云百炼的兼容接口调用。项目复用已经安装的 Python 客户端库，但请求发送到阿里云百炼，不使用 OpenAI 账号、API Key 或计费服务。

## 调用流程

```text
POST /rag/answer
→ 检索相关 Chunk
→ 构造受约束 Prompt
→ 读取 LLM_PROVIDER
→ 加载对应模型配置
→ 调用 DeepSeek 或通义千问
→ 返回回答与引用来源
```

## 安全要求

- 真实 API Key 只能保存在本地 `.env`
- `.env` 必须由 Git 忽略
- `.env.example` 只能保留空密钥
- 不允许通过接口请求传递 API Key
- 不允许在日志中输出 API Key
- 包含密钥的终端或编辑器页面不能截图

## 自动化测试

配置测试覆盖：

- 正确读取 DeepSeek 配置
- 正确读取千问配置
- 拒绝未知 Provider
- 检查当前 Provider 的 API Key
- 验证 LLM 服务使用千问的 Base URL 和模型

测试使用模拟客户端，不会请求外部模型，也不会消耗 Token。

## 真实接口验收

使用以下配置完成真实调用：

```text
Provider：qwen
Model：qwen3.7-plus
```

请求：

```json
{
  "question": "当前项目版本是多少？",
  "top_k": 3
}
```

验收结果：

- HTTP 状态码：200
- 回答：当前项目版本为 v0.3.0
- 回答包含来源引用
- 来源指向 README.md
- 千问模型调用成功

## 当前限制

本页的 Provider 切换只影响后端 `/rag/answer`。客服和邮件使用 Dify 应用中的模型；销售和日报使用 n8n 原生模型节点及 Credentials。`/chat` 当前为回显接口，不用于检验模型切换。

切换后可先离线检查配置：

```powershell
.\.venv\Scripts\python.exe -m backend.app.check_config --component llm
```

退出码 0 仅表示配置有效，不验证密钥或模型服务连通性。修改本地 `.env` 后重启 FastAPI；Compose 环境变量变更需重新创建 API 容器，仅 restart 不会重新注入变量。当前支持与默认型号沿用项目已有配置，不代表供应商最新推荐。

完整字段、优先级、脱敏与生效方式见 [Day 52 配置中心](week-8-notes.md#day52)。

- 修改 Provider 后需要重启服务
- 当前不支持单个请求临时指定模型
- 当前只支持 DeepSeek 和通义千问
- 模型供应商不可用时，接口返回 503
