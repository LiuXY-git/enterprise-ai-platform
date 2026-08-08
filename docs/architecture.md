# 系统架构

## 当前架构

```mermaid
flowchart LR
    User[用户或浏览器] --> Docker[Docker 端口 8000]
    Docker --> Main[FastAPI main.py]
    Main --> Routers[routers 路由层]
    Routers --> Models[models 数据模型]
    Routers --> Services[services 业务层]
    Services --> Routers
    Routers --> User