# Day 29：Dify 基础与首个 AI 应用

## 今日目标

- 理解 Dify 的核心概念
- 使用 Docker Compose 部署 Dify
- 配置通义千问模型
- 创建并发布第一个聊天应用

## 核心概念

| 概念 | 作用 |
|---|---|
| Application | 对外提供 AI 能力的应用载体 |
| Chatbot | 面向连续对话的聊天应用 |
| Workflow | 使用节点编排一次性业务流程 |
| Knowledge Base | 保存文档并为应用提供检索上下文 |

## 部署环境

- Dify：1.16.1
- 部署方式：Docker Compose
- 访问地址：`http://localhost`
- 模型供应商：通义
- 插件版本：0.2.15
- 推理模型：`qwen3.7-plus`

Dify 独立部署在：

`C:\Users\Administrator\Desktop\dify`

它不放入 `enterprise-ai-platform` 仓库，避免形成嵌套 Git 仓库。后续两个系统通过 HTTP API 集成。

## 完成内容

1. 克隆并启动 Dify 1.16.1。
2. 初始化管理员账户和工作区。
3. 安装 Tongyi 模型插件。
4. 配置 DashScope API Key。
5. 将 `qwen3.7-plus` 设置为系统推理模型。
6. 创建“企业客服助手”聊天应用。
7. 编写客服角色、安全边界和回答规则。
8. 完成预览测试并发布应用。

## 验收结果

### 通用能力测试

问题：

`你好，请介绍一下你的服务能力。`

结果：

- 模型调用成功
- 默认使用简体中文
- 回答结构清晰
- 正确说明当前未连接企业知识库

### 防止编造测试

问题：

`请告诉我公司的内部报销制度和具体审批流程。`

结果：

- 没有编造企业内部制度
- 明确说明当前未连接内部知识库
- 建议查询内部系统或咨询相关部门
- 提示后续接入知识库后再进行检索

## 故障处理记录

### Marketplace 插件下载返回 403

SSRF Proxy 日志出现：

`TCP_DENIED/403 CONNECT marketplace.dify.ai:443`

在 Dify 的 `docker/.env` 中增加：

```properties
SSRF_PROXY_ALLOW_PRIVATE_DOMAINS=marketplace.dify.ai
```

然后重新创建 SSRF Proxy：

```powershell
docker compose up -d --force-recreate ssrf_proxy
```

### 重启后出现 502 Bad Gateway

原因是 Nginx 启动时无法连接尚未就绪的 Web 服务。

处理命令：

```powershell
docker compose restart nginx
```

## 当前限制

当前应用只使用大语言模型，没有连接企业知识库，因此不能准确回答企业内部制度、产品价格、订单或专属资料。

Day 30 将把现有 Knowledge Hub 接入 Dify。