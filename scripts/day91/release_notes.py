"""Create release-body.md from a released manifest and matching local acceptance."""

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from experiments.day86.dataset_tool import read_json  # noqa: E402
from experiments.day90 import runner as scoring  # noqa: E402
from scripts.day91 import release_gate as gate  # noqa: E402
from scripts.day91.verify_release import (  # noqa: E402
    SUITES,
    junit_counts,
    require_passed,
)


def acceptance(directory, root=ROOT):
    directory = Path(directory).resolve()
    gate.validate(root)
    manifest = read_json(root / gate.MANIFEST)
    record = read_json(directory / "verification.json")
    if (
        manifest["release_status"] != "released"
        or record.get("status") != "passed"
        or record.get("release_status") != "released"
    ):
        raise ValueError("formal_released_acceptance_required")
    if record.get("manifest_sha256_lf") != gate.digest(root / gate.MANIFEST):
        raise ValueError("verification_manifest_mismatch")
    names = {
        "regression/tests.xml",
        "release/tests.xml",
        "integration/full/evaluation/report.json",
    }
    hashes = record.get("output_sha256_lf")
    if not isinstance(hashes, dict) or set(hashes) != names:
        raise ValueError("acceptance_inventory_invalid")
    for name, expected in hashes.items():
        if gate.digest(gate.safe_path(directory, name)) != expected:
            raise ValueError("acceptance_output_changed")
    seen = set()
    for name, count, _ in SUITES:
        parsed = junit_counts(directory / name / "tests.xml")
        require_passed(parsed, count)
        ids = {tuple(v) for v in parsed["test_ids"]}
        if seen.intersection(ids):
            raise ValueError("duplicate_acceptance_tests")
        seen.update(ids)
    if record.get("total_tests") != len(seen):
        raise ValueError("acceptance_test_total_invalid")
    audit = scoring.inspect(
        directory / "integration/full/run",
        directory / "integration/full/evaluation/report.json",
    )
    if (
        audit["summary"]["passed"] != 12
        or record.get("scoring_summary") != audit["summary"]
    ):
        raise ValueError("acceptance_score_invalid")
    return manifest, record


def git(root, *args):
    return subprocess.run(
        ["git", "-c", "safe.directory=" + root.as_posix(), "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()


def create(directory, output, root=ROOT):
    root = Path(root).resolve()
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError("existing_release_body")
    manifest, record = acceptance(directory, root)
    if git(root, "status", "--porcelain"):
        raise ValueError("commit_formal_manifest_first")
    commit = git(root, "rev-parse", "HEAD")
    if not re.fullmatch("[a-f0-9]{40}", commit):
        raise ValueError("invalid_git_commit")
    committed = git(root, "show", commit + ":" + gate.MANIFEST) + "\n"
    if (
        hashlib.sha256(committed.replace("\r\n", "\n").encode("utf-8")).hexdigest()
        != record["manifest_sha256_lf"]
    ):
        raise ValueError("committed_manifest_mismatch")
    body = f"""# Evaluation Center v0.1.0

Week 13（Day 85–91）阶段正式版本，交付本地 CLI 与固定虚构销售评测。

定版日期：{manifest["release_date"]}
正式提交：{commit}
清单 SHA-256（CRLF→LF）：{record["manifest_sha256_lf"]}

## 本版包含

- Agent/测试集契约、12 个固定用例和独立标准答案。
- 隔离子进程执行、本地 stdio MCP、逐例日志与 SQLite 证据。
- 单调时钟计时，包含启动、重试、清理及基础证据保存。
- 离线验证的 usage 采集与显式价格估算，缺失信息保留未知。
- 独立规则判分、失败原因、分类计数与完整性检查；错误保留在成功率分母。
- 版本清单、历史证据关联检查、可重跑验收和报告复核。

## 验证

正式定版后 {record["total_tests"]} 项离线测试通过，含 342 项既有回归和 {gate.RELEASE_TESTS} 项发布检查，无失败、错误或跳过。
新执行 12 个 fixture 场景，12/12 符合预期。24 次 fixture 模型尝试、13 次本地 MCP 派发；无真实模型请求或消息发送。
附件 verification.json 为正式验收摘要；本机完整运行目录保留 SQLite、回执和逐例评分。
Agent Center v1.0 及其历史冻结资产完整性检查通过；未重新执行全部 721 项历史发布测试。

## 能力边界与待办

100% 是这 12 个固定场景的规则符合率，不是真实模型或生产成功率。
fixture Token 保持 null，模型 API 成本为零不代表所有计算免费。
费用为显式价格算术估算，未核对供应商账单；真实模型评测入口尚未接入。
没有通用 Agent 适配器、网页看板、自由文本语义评分或生产部署承诺。
Day 83 视频仍延期，Day 82 真实 Prompt 质量改善仍未测量；Evaluation Center 发布不改变既有待办。
平台 API 版本仍为 1.0.0。
"""
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(body)
    return dict(
        output=str(output),
        commit=commit,
        tag=manifest["component_tag"],
        title="Evaluation Center v0.1.0",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verification-dir", type=Path, required=True)
    parser.add_argument("--output-file", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(
            json.dumps(
                create(args.verification_dir, args.output_file), ensure_ascii=False
            )
        )
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError):
        print(
            json.dumps(
                dict(status="failed", error="formal_release_notes_inputs_invalid")
            )
        )
        raise SystemExit(1) from None
