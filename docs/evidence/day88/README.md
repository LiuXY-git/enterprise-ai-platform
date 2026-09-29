# Day 88 证据范围

regression.xml 为 198 项测试结果；execution.json 是本次十二例的完整报告快照，包含计时、来源摘要和执行状态；cases 下保存实际 generation.json 和 events.json。validation.json 核对本次源文件与证据摘要。

本机完整目录为 data/day88/acceptance-20260929，包含被 Git 忽略的运行数据库、stdout/stderr 和逐例结果，可使用 Day 88 inspect 检查。此处 Git 中的 JSON/XML 快照不含数据库，不应直接当作完整运行目录传给 inspect。

其他机器按教程重新运行得到自己的完整目录。时长受机器、缓存和后台负载影响，不要求与本次相同。测试使用确定性假时钟验证公式，集成验收使用真实 perf_counter_ns；二者分别记录。
