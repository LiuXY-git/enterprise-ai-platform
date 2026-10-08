# Week 14：测试与运行结果

本周收录 Day 92–93，共 9 份原始记录。日常阅读本页即可，详细 JSON、XML 和运行记录收在[本周数据包](week-14.zip)。

[返回周目录](README.md) · [学习与操作记录](../week-14.md#days)

## 一览

| 日期 | 验证内容 | 当次测试统计 |
| --- | --- | --- |
| [Day 92](#day92) | 后端重构与接口兼容 | 555 项 |
| [Day 93](#day93) | Compose 前端、反向代理与持久化 | 后端 528 项；浏览器 9 组；隔离容器验收通过 |

各日测试范围可能重叠，不将这些数字累加为本周独立测试总数。记录描述当时运行结果，不能代替修改后的重新测试。

<a id="day92"></a>

## Day 92：后端重构与接口兼容

- 主要结果：`validation.json`；共 4 份记录。
- 后端 514 项及发布测试 41 项通过；25 个 OpenAPI 路径在重构时保持一致。
- 操作说明：[Week 14 对应章节](../week-14.md#day92)。

<a id="day93"></a>

## Day 93：Compose 前端、反向代理与持久化

- 后端 528 项通过，包含新增 14 项；浏览器使用本机 HTTP 测试响应，9 组检查通过。
- 真实构建 API/前端镜像，页面与代理检查通过；测试容器重建后，SQLite、Chroma 固定向量和日志保留。
- 临时测试容器及镜像已清理。没有替换现有容器、使用真实业务数据、下载 Embedding 模型或新增模型请求。
- 本次收录 5 份记录：validation.json、backend-tests.xml、browser-validation.json、compose-validation.json、deployment-validation.json。
- 操作说明：[Week 14 对应章节](../week-14.md#day93)。n8n 重建和真实语义检索质量不在本次验收范围内。
