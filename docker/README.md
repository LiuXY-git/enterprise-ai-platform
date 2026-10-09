# Docker

本目录保存 API 的 [Dockerfile](Dockerfile)。项目根的 [compose.yaml](../compose.yaml) 管理 frontend、api、n8n；完整配置与操作手册见 [Week 14](../docs/week-14.md#day97-setup)。

## 镜像与拓扑

| 服务 | 构建/镜像 | 宿主机入口 |
| --- | --- | --- |
| api | Python 3.14-slim；安装 requirements.txt，仅复制 backend；非 root app 用户 | 127.0.0.1:8000 |
| frontend | [独立 Dockerfile](../frontend/Dockerfile)，Nginx 1.30.5-alpine 与静态资源；非 root nginx 用户 | 127.0.0.1:8080 |
| n8n | docker.n8n.io/n8nio/n8n:2.36.8 | 127.0.0.1:5678 |

前端经 /api/ 代理到 api:8000。SQLite 和 Chroma 在 API 内运行，当前没有独立数据库/向量库容器；Dify 独立部署。Agent/MCP/评测 CLI 使用宿主机环境，不进入 API 镜像。

[.dockerignore](../.dockerignore) 排除私有环境文件、运行数据、缓存和实验资料。前端镜像仅复制其静态资源与 Nginx 配置，前端不读取服务端密钥。

## 选择更新范围

在项目根目录执行，使用与现有实例一致的环境文件：

```powershell
$platformEnv = '.env'
# 只更新 API，保留前端与 n8n 当前状态
& .\scripts\start.ps1 -EnvFile $platformEnv -ApiOnly
```

API 加前端使用 -WithoutN8n；更新三个服务时省略这两个开关。它们不能同时使用，也不会自动停止未选中的服务。**ApiOnly 仍需通过完整 Compose 配置验证，N8N_ENCRYPTION_KEY 不能缺失。** 已有 n8n 数据卷应保留原加密键；初始化方法见 [环境说明](../docs/week-14.md#day94)。

脚本先检查 Docker/Compose，再构建、更新、等待健康、校验挂载和选中服务。按需附加 -CheckComponents llm,dify；检查失败会报错，但不提供自动回滚。配置格式通过与真实业务成功是不同结论。

已有容器只检查、不构建：

```powershell
& .\scripts\check-deployment.ps1 -EnvFile $platformEnv -ApiOnly
```

若之前选择了前端或 n8n，检查时选择对应相同范围；不能用 ApiOnly 的成功证明全部服务已通过检查。

## 持久化与日志

| 宿主机目录/卷 | 容器目录 |
| --- | --- |
| ./data | /app/data |
| ./logs | /app/logs |
| ./data/chroma-cache | /home/app/.cache/chroma |
| n8n_data 命名卷 | n8n 的 /home/node/.n8n |

API 日志包括 app.log 和 workflow-events.jsonl，容器日志沿用每文件 10m、3 份限制。应用文件轮转与容器日志是不同存储来源，细节见 [日志说明](../docs/week-14.md#day95)。

## 停止与维护

```powershell
docker compose --env-file $platformEnv ps
docker compose --env-file $platformEnv stop frontend
```

只有需要停止全部服务时，另行执行 `docker compose --env-file $platformEnv stop`。

stop 保留容器和数据；再次 start.ps1 会按选定范围更新。仅 restart 不会重新应用 Compose 环境变化。备份应覆盖数据库、向量索引、n8n 数据卷及匹配配置，见 [维护与恢复边界](../docs/week-14.md#day97-operations)。

源码或配置提交不等于已部署新镜像；固定的 :1.0.0 镜像标签也不标识某次构建内容。当前未部署 ELK，无自动备份、恢复或数据库版本回滚工具。
