# Day 91 候选验收证据

- `verification.json`：本次完整验收摘要，包含清单哈希、测试计数、评分和消耗边界。
- `regression.xml` / `release.xml`：342 项既有测试和 41 项发布测试的 JUnit 记录。
- `scoring.json`：本次新运行 12 例后的 Day 90 完整评分快照。
- `validation.json`：本阶段来源、证据哈希与检查记录。

原始目录保留在本机 `data/day91/candidate-20260930`；其中 `integration/full/run` 包含 SQLite 和 Worker 等原始文件。此目录被 Git 忽略。克隆仓库后应运行 `scripts/day91/verify_release.py` 获取自己的完整证据。

本目录是本次清单生成后的输出，不纳入清单自身，避免自引用。正式发布需要在 released 清单上重新运行验收，并上传新的 verification.json；此处候选摘要保持不变。
