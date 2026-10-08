# Docker

该目录用于存放 Enterprise AI Platform 的 Docker 配置。

## 文件说明

### Dockerfile

`Dockerfile` 用于构建 FastAPI 后端镜像，主要包含：

- Python 3.14 运行环境
- 项目运行依赖
- 非 root 用户 `app`
- 数据和日志目录
- FastAPI 健康检查
- Uvicorn 启动命令

### Compose 配置

项目根目录的 `compose.yaml` 用于：

- 构建后端镜像
- 启动 API、前端与 n8n 容器
- 仅在本机映射 8000（API）、8080（前端）、5678（n8n）端口
- 注入本地环境变量
- 持久化数据库、向量数据和日志
- 持久化 Embedding 模型缓存
- 自动重启异常退出的服务

### Docker Ignore

项目根目录的 `.dockerignore` 用于排除：

- `.env` 和本地配置
- Git 与编辑器文件
- 测试及工具缓存
- 数据库、日志和模型缓存
- 文档与实验代码

## 启动服务

```powershell
& .\scripts\start.ps1 -CheckComponents llm,dify
```

只更新 API 使用 `-ApiOnly`。脚本按源码位置确定项目目录，先构建再更新，并等待健康与挂载检查。详见 [Day 93 部署说明](../docs/week-14.md#day93)。Day 94 增加 `-EnvFile`，启动和检查均需使用同一选中文件；初始化与配置检查见 [环境变量管理](../docs/week-14.md#day94)。

API 和前端一起更新时使用 -WithoutN8n。前端使用 [独立 Dockerfile](../frontend/Dockerfile) 构建静态资源及 Nginx，同源代理到 API。数据库沿用 API 内的 SQLite 和 Chroma，以宿主机目录持久化。

Day 95 API 应用日志改为 JSON，并以 X-Request-ID 关联 HTTP 与工作流事件。现有镜像需要按需重建后才生效；仅更新 API 可用 -ApiOnly，详见 [日志启用与排障](../docs/week-14.md#day95)。本次没有增加 ELK 服务。
