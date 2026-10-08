# Workflow Center 模板目录

Day 50 将已有客服、邮件和销售工作流整理为可复用模板。每份模板由使用说明、请求样例和原工作流导出引用组成。导入 n8n 时选择说明中的 workflows JSON，catalog.json 与 examples JSON 不用于导入。

## 选择模板

| 模板 | 适用场景 | 持久化与重复保护 | 输出与边界 |
| --- | --- | --- | --- |
| [客服](customer-service/README.md) | 知识库咨询、依据资料回答 | 此 n8n 流程没有平台账本或事件去重 | answer；依赖已发布 Dify 工作流与知识库 |
| [邮件](email-assistant/README.md) | 邮件文本分类、人工复核、低风险草稿 | 平台运行账本、event_id 去重、显式失败回放 | draft_reply；没有收件箱监听或邮件发送 |
| [销售](sales-followup/README.md) | 分析线索、写入模拟 CRM、给出跟进建议 | 运行账本、CRM 事务与分析检查点 | CRM 跟进及通知预览；没有真实通知编排 |

机器索引见 [catalog.json](catalog.json)，其中所有路径均相对仓库根目录。它描述模板及已有接口，不改变 v0.5.0 发布清单。三类模板共享原始导出作为唯一执行来源，避免复制节点后产生两个实现。

## 使用顺序

1. 按业务场景选择模板，阅读输入、输出和不适用条件。
2. 已验收实例直接复用已有工作流；新环境按各模板说明导入原导出并完成绑定。不要在同一实例同时发布两个相同 Webhook 路径。
3. 按样例构造请求。独立业务事件使用新 event_id/request_id；排查同一事件时保留原标识。customer_id 是业务客户标识，真实复用时不要随意更换。
4. 按 [平台使用指南](../../docs/week-8.md#user-guide) 选择测试监听或已发布的生产入口，手动发送业务体并核对响应和运行记录。Day 50 的模板整理以及 Day 54 的文档更新均未修改执行流程，已有验收实例无需因此重新导入。

## 离线生成独立示例请求

在仓库根目录运行：

```powershell
.\.venv\Scripts\python.exe scripts/day50/render_template_request.py --template sales-followup --scenario normal --output "$env:TEMP\day50-sales-request.json"
```

脚本只写入请求说明文件，包含 method、url、headers 和 body，不发 HTTP 请求。每次生成新事件标识；客服、销售的示例 customer_id 也使用独立标识，以隔离后续手动演示数据。邮件 requester 和 sales_owner 使用虚构样例值。

生成文件不是可直接 POST 的业务体；未来手动调用时仅将其中 body 发送到 url。默认 URL 为本机 Test URL，届时需在 n8n 开启测试监听；`--production` 仅切换生成的 URL，不发布或执行工作流。`--output` 拒绝覆盖已有文件，换新文件名即可。

固定 examples 文件用于阅读，勿反复发送同一个邮件/销售样例来模拟新的业务事件。销售 report_date 由生成器更新为 Asia/Shanghai 当日日期；原样例日期只表示格式。

## 凭据与配置

API 与 n8n 使用现有 Compose，n8n 内部 API 地址沿用 http://api:8000。客服、邮件由 API 使用 DIFY_WORKFLOW_API_KEY 和 DIFY_API_BASE_URL 访问 Dify；销售绑定 n8n 中的 DashScope 凭据。密钥不写入模板或请求样例。

输入字段和输出名称保留各流程的约定。日志字段与耗时/Token 来源见 [Day 51](../../docs/week-8.md#day51)，配置归属与模型选择见 [Day 52](../../docs/week-8.md#day52)，启动与检查见 [Day 53](../../docs/week-8.md#day53)。当前接口及 Webhook 面向本机或可信网络，统一认证和租户隔离仍为待办。
