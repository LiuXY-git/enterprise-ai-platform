# Day 87 验证证据

`regression.xml` 为 170 项测试报告；`execution.json` 为最终代码执行 12 例的原始报告快照；`cases/<id>/generation.json` 与 `events.json` 保存实际回答与事件。`validation.json` 记录源摘要、证据摘要、离线请求边界及验收核对结果。

Git 中保存 JSON/XML 证据，不提交本地运行数据库和日志文件。本机完整运行目录为 `data/day87/acceptance-20260929`（被 Git 忽略）。运行 `runner.py inspect --output-dir .\data\day87\acceptance-20260929` 可核对完整证据；不要把这里不含数据库的快照目录直接传给 inspect。

换一台机器后，按复刻教程运行到新目录再 inspect。运行编号、时间、数据库字节和引用会变化；此处历史哈希只属于本次运行。原始执行报告未判分，业务 failed/rejected 均被如实保留。
