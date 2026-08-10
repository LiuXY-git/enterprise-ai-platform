# Week 1 总结

## 本周目标

完成 Enterprise AI Platform 的项目初始化，并建立可运行、可维护、可容器化的 FastAPI 后端基础。

## 已完成

- 配置 Python 虚拟环境
- 配置 VS Code 和 Ruff
- 创建 FastAPI 应用
- 实现 `GET /health`
- 实现 `POST /chat`
- 使用 Pydantic 校验请求和响应
- 拆分 routers、models、services 和 utils
- 练习 Git 分支、提交与合并
- 完成 FastAPI Docker 化
- 编写项目架构和技术选型文档

## 当前接口

| 方法 | 地址 | 作用 |
| --- | --- | --- |
| GET | `/health` | 检查服务状态 |
| POST | `/chat` | 接收聊天消息 |

## 启动方式

```powershell
docker compose up --build

## 接口文档

```text
http://127.0.0.1:8000/docs
```