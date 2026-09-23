# Day 66：Knowledge Tool

`search_knowledge` 将模型提出的检索请求交给现有 Knowledge Hub，返回带来源的片段，再核对模型回答中的引用编号。资料均为虚构教学数据。

在仓库根目录运行，使用已有 API 虚拟环境，无新增依赖：

```powershell
& .\.venv\Scripts\python.exe experiments/day66/knowledge_agent.py --check-all
& .\.venv\Scripts\python.exe experiments/day66/knowledge_agent.py --show-tools
```

默认 `fixture` 模式中的检索和模型回复都是固定样例，不加载向量模型，不读取模型凭据。`supported`、`empty`、`injection` 三个场景分别展示引用回答、空结果和不可信文档内容。

调用真实 Knowledge Hub 检索函数、本地向量模型和临时 Chroma 集合，模型仍用固定回复：

```powershell
& .\.venv\Scripts\python.exe experiments/day66/knowledge_agent.py --backend hub-demo --case supported
& .\.venv\Scripts\python.exe experiments/day66/knowledge_agent.py --backend hub-demo --case empty
```

每次单独启动检索子进程，在内存集合中放入 [虚构教学资料](knowledge-data.json)；`empty` 使用真正的空集合。需要已有 `all-MiniLM-L6-v2/onnx` 本地缓存，缺少缓存直接返回 `embedding_cache_missing`，不自动下载。

实际 Qwen Function Calling（每例最多 2 次模型请求、1 次检索）：

```powershell
& .\.venv\Scripts\python.exe experiments/day66/knowledge_agent.py --live --backend hub-demo --case supported
& .\.venv\Scripts\python.exe experiments/day66/knowledge_agent.py --live --backend hub-demo --case empty
```

`--live` 使用项目已有模型配置，可加 `--env-file .env`。该 CLI 只允许向模型发送虚构 `hub-demo` 结果，不能选择业务 `hub`。本轮 Qwen qwen3.7-plus 两例共 4 次请求均通过，详见 [实际验收证据](../../docs/evidence/day66/validation.json)。重复执行会产生新的模型请求。

只查看检索结果：

```powershell
& .\.venv\Scripts\python.exe experiments/day66/knowledge_tool.py --backend hub-demo --query 'hotel reimbursement invoice' --top-k 3
```

已有业务知识库的本地检索入口、参数含义、完整复刻步骤和限制，见 [Day 66 操作说明](../../docs/day66-knowledge-tool.md)。本日是宿主机 CLI 实验，不需要更新 API 容器。

离线测试：

```powershell
$day66TestDir = Join-Path $env:TEMP ('day66-tests-' + [guid]::NewGuid().ToString('N'))
& .\.venv\Scripts\python.exe -m pytest experiments/day64 experiments/day65 experiments/day66 tests/test_retrieval_service.py -q -p no:cacheprovider --basetemp $day66TestDir
```

358 项通过：Day 66 新增 120 项、Day 64–65 回归 237 项、原检索服务回归 1 项。引用校验仅确认编号能对应到本次证据；不能证明模型每句话在语义上正确。
