# Day 67：天气 API Tool

`get_weather_forecast` 让 Agent 调用一个固定的外部天气 API，学习请求约束、响应校验和错误处理。支持北京、上海、广州，从当地今天开始 1–3 天，返回最高/最低温和最大降水概率。

在仓库根目录使用已有 API 虚拟环境，无新增依赖，无需更新容器：

```powershell
& .\.venv\Scripts\python.exe experiments/day67/weather_agent.py --show-tools
& .\.venv\Scripts\python.exe experiments/day67/weather_agent.py --check-all
```

默认模型回复与 HTTP 响应均为固定样例，**不联网**。4 例包括北京、上海、模拟超时、模拟 429。后两例的 `result.status` 应为 `rejected`，匹配预期错误就算该负面用例通过；`--check-all` 全部匹配时退出码为 0。

只调用真实公开 API，不调用 Qwen：

```powershell
& .\.venv\Scripts\python.exe experiments/day67/weather_api.py --live-api --city beijing --days 1
```

真实 Qwen + 真实天气 API：

```powershell
& .\.venv\Scripts\python.exe experiments/day67/weather_agent.py --live --case beijing
& .\.venv\Scripts\python.exe experiments/day67/weather_agent.py --live --case shanghai
```

每例最多 2 次模型请求和 1 次 API 请求。Qwen 使用已有 `.env` 配置，也可加 `--env-file .env`；天气 API 无需密钥，不接收模型密钥。不会自动重试或跟随重定向。

本轮实际通过 123 项新增测试，连同已有回归共 481 项。Qwen 北京一天、上海三天两个场景共 4 次模型请求；加上单独 API 检查，共 3 次真实天气请求。预报会更新，历史证据不能当作当前天气使用。

```powershell
$day67TestDir = Join-Path $env:TEMP ('day67-tests-' + [guid]::NewGuid().ToString('N'))
& .\.venv\Scripts\python.exe -m pytest experiments/day64 experiments/day65 experiments/day66 experiments/day67 tests/test_retrieval_service.py -q -p no:cacheprovider --basetemp $day67TestDir
```

天气数据来自 [Open-Meteo](https://open-meteo.com/)，按 CC BY 4.0 署名。免费接口用于本次非商业学习，商业产品应按 [官方使用条件](https://open-meteo.com/en/terms)选择适当方案。

详细参数、失败行为、可复刻流程和能力边界见 [Day 67 操作说明](../../docs/day67-api-tool.md)；结果见 [验收清单](../../docs/evidence/day67/validation.json)。
