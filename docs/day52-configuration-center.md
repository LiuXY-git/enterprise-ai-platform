# Day 52 配置中心与离线自检

Day 52 将六组后端配置集中到 `backend/app/settings.py`，保留原来的配置导入接口，并增加按组件执行的离线自检。修改配置前，先确定读取者是后端、Dify 还是 n8n。

## 模型由谁选择

| 场景 | 配置归属 | 后端 LLM_PROVIDER 是否影响 |
| --- | --- | --- |
| `/rag/answer` 生成回答 | 后端环境变量 | 是，支持已有 DeepSeek 和 Qwen |
| 客服、邮件草稿 | Dify 应用模型节点与凭据 | 否 |
| 销售分析、日报 | n8n 模型节点与 Credentials | 否 |

`/chat` 当前回显输入，`/rag/query` 只执行检索，都不用于检验生成模型切换。Embedding 配置也不在本次范围内。GPT、Claude、本地模型尚未新增适配。

## 加载与校验

FastAPI 在 lifespan 启动阶段显式调用 `load_environment()`；离线工具也在自己的入口调用它。导入 settings 或原有 `services/*_config.py` 不会读取 `.env`、创建客户端或验证凭据。直接编写独立 Python 调用脚本时，若需要 `.env`，也应先调用 `load_environment()`。

加载顺序：进程环境变量优先，源码确定的项目根目录 `.env` 补缺，未设置字段再使用默认值。启动目录不会改变默认文件位置。进程环境中的空值仍优先，必填字段会明确报缺项。`.env` 内容按字面读取，不展开 `${VARIABLE}`，兼容 UTF-8 与 UTF-8 BOM；默认文件可以不存在，显式指定的文件必须存在并可读。

配置对象按组件读取，不长期缓存。加载 `.env` 不覆盖已有进程变量，因此修改文件后应重启进程。企业微信仍通过配置对象比较决定是否替换 Token 服务缓存。

缺少可选集成配置不会阻止 `/health` 和 OpenAPI 启动；使用相应功能时才校验该组字段。Dify 和飞书超时现要求有限正数，拒绝 `NaN`、`Infinity` 和负数。企业微信固定地址、单成员限制、飞书接收者及重试规则保持原有语义。

模型、Dify、飞书的 Base URL 必须是具有主机名的 HTTP(S) 地址，不能包含用户名密码、查询参数、片段、空白或非法端口。内网 HTTP 和已有测试地址可继续使用；这是配置格式检查，不是地址可信性或网络连通性认证。错误信息不回显配置原值。

## 配置清单

以下字段均在使用对应组件时校验。敏感字段只保存在本地环境中；`.env.example` 提供空值示例。

| 组 | 环境变量 | 默认值或要求 |
| --- | --- | --- |
| RAG | `LLM_PROVIDER` | `deepseek`；也支持 `qwen`，去空白并转小写 |
| DeepSeek | `DEEPSEEK_API_KEY` | 敏感；选中该 Provider 时必填 |
| DeepSeek | `DEEPSEEK_BASE_URL` / `DEEPSEEK_MODEL` | `https://api.deepseek.com` / `deepseek-v4-flash` |
| Qwen | `DASHSCOPE_API_KEY` | 敏感；选中该 Provider 时必填 |
| Qwen | `QWEN_BASE_URL` / `QWEN_MODEL` | `https://dashscope.aliyuncs.com/compatible-mode/v1` / `qwen3.7-plus` |
| Dify 调用 | `DIFY_WORKFLOW_API_KEY` | 敏感；应用工作流 Key，必填 |
| Dify 调用 | `DIFY_API_BASE_URL` | Python 默认 `http://localhost/v1`；Compose 默认 `http://host.docker.internal/v1` |
| Dify 调用 | `DIFY_WORKFLOW_TIMEOUT_SECONDS` | `120`，有限正数 |
| 外部知识库 | `DIFY_EXTERNAL_KNOWLEDGE_API_KEY` | 敏感；检索鉴权 Key，必填，与工作流 Key 分开 |
| 外部知识库 | `DIFY_EXTERNAL_KNOWLEDGE_ID` | `enterprise-knowledge-hub`，不可为空 |
| 飞书鉴权 | `FEISHU_APP_ID` / `FEISHU_APP_SECRET` | 必填；Secret 为敏感字段 |
| 飞书鉴权 | `FEISHU_API_BASE_URL` / `FEISHU_TIMEOUT_SECONDS` | `https://open.feishu.cn/open-apis` / `10`，超时为有限正数 |
| 飞书发送 | `FEISHU_RECEIVE_ID_TYPE` / `FEISHU_RECEIVE_ID` | 类型默认 `chat_id`，也支持 `open_id`；接收者必填并符合对应前缀 |
| 飞书发送 | `FEISHU_MAX_ATTEMPTS` | 默认 `3`，1—5，包含首次尝试 |
| 飞书发送 | `FEISHU_RETRY_BASE_SECONDS` | 默认 `0.5`，有限非负数 |
| 企业微信 | `WECOM_CORP_ID` / `WECOM_AGENT_ID` | 必填；Agent ID 为正整数 |
| 企业微信 | `WECOM_APP_SECRET` / `WECOM_TO_USER` | 必填；Secret 为敏感字段，只允许单个接收成员 |
| 企业微信 | `WECOM_API_BASE_URL` / `WECOM_TIMEOUT_SECONDS` | 固定 `https://qyapi.weixin.qq.com` / 默认 `10`，超时为有限正数 |

表内模型默认值沿用当前项目，不代表供应商最新推荐。n8n 的 `N8N_ENCRYPTION_KEY`、URL、时区等运行设置仍由 Compose 管理；原生模型凭据保存在 n8n Credentials 中，不纳入后端必填字段。

## 离线自检

在项目根目录执行需要的组件：

```powershell
.\.venv\Scripts\python.exe -m backend.app.check_config --component llm
.\.venv\Scripts\python.exe -m backend.app.check_config --component dify
.\.venv\Scripts\python.exe -m backend.app.check_config --component external-knowledge
.\.venv\Scripts\python.exe -m backend.app.check_config --component feishu
.\.venv\Scripts\python.exe -m backend.app.check_config --component wecom
```

`feishu` 检查鉴权与发送两组配置，每组至多报告首个错误；修正后再检查。Dify/n8n 内部模型明确标为外部管理、未检查。

可用 `--env-file` 指定一份文件。它替代默认 `.env`，但进程变量仍优先：

```powershell
.\.venv\Scripts\python.exe -m backend.app.check_config --component llm --env-file 'C:\path\to\local.env'
```

使用 `--all` 要求五个组件全部配置有效。未配置企业微信会使该命令失败，这不表示整个平台不能启动：

```powershell
.\.venv\Scripts\python.exe -m backend.app.check_config --all
$LASTEXITCODE
```

| 结果 | 退出码 | 含义 |
| --- | --- | --- |
| `configuration_valid` | 0 | 所选组件通过本地配置校验 |
| `configuration_invalid` | 1 | 有必填项缺失、值不合法或环境文件不可读取 |
| CLI 参数错误 | 2 | 组件名称或参数组合不正确 |

工具输出 JSON，密钥只显示 `configured` / `missing`；不输出模型原值、接收者、完整 URL 或配置对象。敏感 dataclass 字段也不出现在 repr 中，但配置对象仍携带调用所需密钥，不能用 `asdict` 等方式直接公开。

自检不导入 FastAPI 应用、模型客户端或数据库，不发请求、不取 Token、不发送消息，也不写业务数据。成功仅代表配置格式有效，不验证凭据有效性、模型可用性、连通性或工作流执行。dotenv 对文件的语法处理沿用 python-dotenv；字段级校验不替代完整环境文件语法审计。

## 配置修改何时生效

| 改动 | 操作 |
| --- | --- |
| 本地 `.env` | 重启本地 FastAPI 进程 |
| Compose 注入 API 的变量 | 重建 API 容器以重新注入；只 restart 不够 |
| API 代码 | 构建新镜像并重建 API 容器 |
| Dify 模型 | 修改对应应用并发布，验收受影响的流程 |
| n8n 原生模型 | 修改模型节点或 Credential 绑定，按现有保存/发布流程生效并验收 |

后端统一入口没有改写 Dify/n8n 模型设置或已有工作流导出。销售流程仍为 preview，企业微信真实发送仍受既有准入条件限制。

## 验证与后续

测试覆盖环境优先级、工作目录独立性、旧导入兼容、两个 Provider 的 Mock 客户端调用、有限超时、URL 校验、脱敏、无配置启动、CLI 退出码及无网络/数据库依赖。测试统一隔离开发者的环境配置和真实 `.env`。

验收结果：相关测试首次 123 项通过；最终全量回归 498 项通过，Ruff 通过。保留一项既有 ChromaDB 关于 `asyncio.iscoroutinefunction` 的弃用警告。全量检查发现 Day 51 日志测试直接赋值日志级别会留下级别缓存，已将该测试夹具改为 `setLevel()` 并在结束时恢复，修复后全量通过。

测试在不包含真实 `.env` 的隔离源码副本中运行，使用虚构凭据、Mock 客户端和临时数据库。没有调用真实模型、发送通知或重启业务服务。测试结果不代表当前运行中的 API 容器已经更新。Day 53 继续处理 Compose 部署和日志持久化：当前应用日志在 `/app/backend/logs`，现有卷映射为 `/app/logs`，此次未修改该部署行为。
