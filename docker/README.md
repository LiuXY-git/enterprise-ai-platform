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
- 启动 API 容器
- 映射 8000 端口
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
只更新 API 使用 `-ApiOnly`。脚本按源码位置确定项目目录，先构建再更新，并等待健康与挂载检查。详见 [Day 53 部署说明](../docs/day53-compose-deployment.md)。
