"""Check and verify the scoped Enterprise AI Platform v1.0 release locally."""

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts import test_platform as runner  # noqa: E402

MANIFEST = "scripts/release/platform-v1.0.0.json"
TAG = "enterprise-ai-platform-v1.0.0"
DIRECTORIES = (
    "backend",
    "frontend",
    "docker",
    "scripts",
    "tests",
    "experiments",
    "agent-center",
    "evaluation-center",
    "n8n",
    "demo",
    "docs",
)
ROOT_FILES = (
    "README.md",
    "CHANGELOG.md",
    "compose.yaml",
    ".dockerignore",
    ".gitignore",
    ".env.example",
    "requirements.txt",
    "requirements-dev.txt",
    "pyproject.toml",
    "conftest.py",
)
SKIP = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "node_modules",
    "data",
    "logs",
}
SUFFIXES = {
    ".py",
    ".json",
    ".txt",
    ".ps1",
    ".md",
    ".yaml",
    ".yml",
    ".toml",
    ".html",
    ".css",
    ".js",
    ".cjs",
    ".conf",
    ".sql",
    ".zip",
}
EXCLUDED = {MANIFEST, "scripts/evidence_layout/index.json"}
MINIMUM_TESTS = {
    "api": 618,
    "planner": 86,
    "agent": 369,
    "workflow": 259,
    "evaluation": 242,
}
LIMITS = [
    "Offline regression is not live model quality or production readiness.",
    "Browser and Docker deployment are separate checks; not executed by this command.",
    "No real model requests or notification sends are part of this acceptance.",
    "Demo videos and live prompt-quality evaluation remain pending.",
    "Tag, GitHub Release and deployment are not created by this command.",
]


def digest(path):
    raw = path.read_bytes()
    if path.suffix != ".zip":
        raw = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def inventory(root):
    """Select shipped source/config/docs, never private env or runtime output."""
    root = Path(root).resolve()
    paths = [root / name for name in ROOT_FILES]
    for name in DIRECTORIES:
        base = root / name
        if base.is_symlink():
            raise ValueError("source_symlink")
        for directory, dirs, files in base.walk(follow_symlinks=False):
            dirs[:] = sorted(d for d in dirs if d not in SKIP)
            if any((directory / d).is_symlink() for d in dirs):
                raise ValueError("source_symlink")
            for filename in sorted(files):
                path = directory / filename
                rel = path.relative_to(root).as_posix()
                if rel in EXCLUDED or rel.startswith("docs/evidence/"):
                    continue
                if filename.startswith(".env") and filename != ".env.example":
                    continue
                if path.suffix in SUFFIXES or filename in {
                    "CHANGELOG.md",
                    ".dockerignore",
                }:
                    paths.append(path)
    result = {}
    for path in sorted(paths):
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError("source_escapes_repository")
        if not path.is_file():
            raise ValueError("required_source_missing")
        result[path.relative_to(root).as_posix()] = digest(path)
    return result


def check(root=ROOT):
    root = Path(root).resolve()
    path = root / MANIFEST
    if path.is_symlink() or not path.resolve().is_relative_to(root):
        raise ValueError("manifest_escapes_repository")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if (
        manifest.get("schema_version") != 1
        or manifest.get("product") != "Enterprise AI Platform"
        or manifest.get("version") != "1.0.0"
        or manifest.get("tag") != TAG
        or manifest.get("hash_policy") != "sha256_crlf_to_lf_except_zip"
    ):
        raise ValueError("invalid_release_identity")
    status, released = manifest.get("release_status"), manifest.get("released_on")
    if status == "candidate":
        if released is not None:
            raise ValueError("candidate_cannot_have_release_date")
    elif status == "released":
        if (
            not isinstance(released, str)
            or date.fromisoformat(released).isoformat() != released
        ):
            raise ValueError("invalid_release_date")
    else:
        raise ValueError("invalid_release_status")
    if manifest.get("files") != inventory(root):
        raise ValueError("release_inventory_mismatch")
    expected = manifest.get("expected_tests", {})
    if set(expected) != {*runner.SUITES, "release"} or any(
        type(v) is not int or v < MINIMUM_TESTS.get(k, 1) for k, v in expected.items()
    ):
        raise ValueError("invalid_test_contract")
    return manifest


def git_identity(root):
    def git(*args):
        return subprocess.check_output(
            ["git", *args],
            cwd=root,
            text=True,
            encoding="utf-8",
            stderr=subprocess.DEVNULL,
            timeout=10,
        ).strip()

    try:
        if Path(git("rev-parse", "--show-toplevel")).resolve() != Path(root).resolve():
            raise ValueError("not_repository_root")
        return {
            "commit": git("rev-parse", "HEAD"),
            "working_tree_clean": not bool(git("status", "--porcelain")),
        }
    except (OSError, subprocess.SubprocessError, ValueError):
        return {"commit": None, "working_tree_clean": False}


def require_counts(counts, expected):
    if counts != {"tests": expected, "failures": 0, "errors": 0, "skipped": 0}:
        raise ValueError("unexpected_test_counts")


def release_tests(root, folder, python, timeout):
    folder.mkdir()
    command = [
        str(python),
        "-B",
        "-m",
        "pytest",
        "scripts/release/test_release.py",
        "-q",
        "--tb=short",
        "-p",
        "no:cacheprovider",
        "-p",
        "scripts.testing.inventory",
        f"--eap-inventory={folder / 'inventory.json'}",
        f"--junitxml={folder / 'tests.xml'}",
        f"--basetemp={folder / 'temp'}",
    ]
    return runner.assess(folder, runner.execute(command, root, folder, timeout))


def release_body(result):
    stage = "候选验收" if result["release_status"] == "candidate" else "正式定版验收"
    suites = "\n".join(
        f"- {s['suite']}：{s['counts']['tests']} 项。" for s in result["suites"]
    )
    commit = result["git"]["commit"] or "源码副本，无 Git 提交关联"
    clean = (
        "干净"
        if result["git"]["working_tree_clean"]
        else "未确认干净；不能据此创建正式标签"
    )
    return f"""# Enterprise AI Platform v1.0.0

Week 14（Day 92–98）阶段版本；当前为{stage}。这是本地学习平台的阶段交付。

- 标签名称：{TAG}（本命令没有创建标签）。
- 验收时间：{result["completed_at"]}。
- 提交：{commit}；工作区：{clean}。
- 清单 SHA-256（CRLF→LF）：{result["manifest_sha256"]}。

## 本版包含

- Knowledge Hub 文档上传、片段检索前端及现有 FastAPI 接口。
- API、前端、n8n Compose 配置，SQLite、Chroma 与日志持久化。
- 环境文件选择、配置自检、结构化日志及请求追踪。
- Agent/MCP、人工确认和固定虚构销售评测的宿主机 CLI 入口。
- 分环境回归、技术操作手册及可重复运行的发布验收。

## 验证

本次新执行 {result["total_tests"]} 项离线测试，失败、错误、跳过均为零。

{suites}

附件 verification.json 为本次验收摘要；完整日志、测试编号、JUnit 保留在本机运行目录。
本命令没有执行浏览器、Docker 部署、真实模型或通知调用。

## 能力边界与待办

前端提供上传与片段检索；Agent 与评测为独立 CLI，没有统一 Agent 网页或 HTTP API。
身份认证仍不完整，服务按本机回环部署；通过离线测试不代表生产安全或真实模型成功率。
SQLite 与 Chroma 为嵌入式存储，Dify 独立部署；平台 API 元数据仍为 1.0.0。
视频补录、真实 Prompt 质量测量、真实模型评测接入及原有 Workflow Release 等待办继续保留。
此命令不创建 GitHub Release，也不更新现有容器。
"""


def verify(root, output, interpreters, timeout=900):
    root, output = Path(root).resolve(), Path(output).resolve()
    if timeout <= 0:
        raise ValueError("timeout_must_be_positive")
    if output.is_relative_to(root) and not output.is_relative_to(
        root / "logs/test-runs"
    ):
        raise ValueError("repository_output_must_be_under_logs_test_runs")
    output.mkdir(parents=True, exist_ok=False)
    result = {
        "schema_version": 1,
        "status": "running",
        "product": "Enterprise AI Platform",
        "version": "1.0.0",
        "tag": TAG,
        "started_at": datetime.now(UTC).isoformat(),
        "suites": [],
        "limits": LIMITS,
        "remote_publication_checked": False,
    }
    runner.save(output / "verification.json", result)
    try:
        manifest = check(root)
        before, identity = digest(root / MANIFEST), git_identity(root)
        result.update(
            manifest_sha256=before,
            release_status=manifest["release_status"],
            git=identity,
            source_files=len(manifest["files"]),
        )
        if manifest["release_status"] == "released" and (
            not identity["commit"] or not identity["working_tree_clean"]
        ):
            raise ValueError("formal_acceptance_requires_clean_commit")
        for python in interpreters.values():
            if not Path(python).is_file():
                raise ValueError("python_environment_missing")
        controls = release_tests(root, output / "release", interpreters["api"], timeout)
        result["suites"].append({"suite": "release", **controls})
        if controls["status"] != "passed":
            raise ValueError("release_controls_failed")
        require_counts(controls["counts"], manifest["expected_tests"]["release"])
        runner.save(output / "verification.json", result)
        regression = runner.run(
            root, output / "regression", ["all"], interpreters, timeout
        )
        if regression["status"] != "passed" or regression["selected_suites"] != list(
            runner.SUITES
        ):
            raise ValueError("regression_failed")
        if [s["suite"] for s in regression["suites"]] != list(runner.SUITES):
            raise ValueError("incomplete_regression_suites")
        seen = set(controls["test_ids"])
        for item in regression["suites"]:
            name = item["suite"]
            folder = output / "regression" / name
            observed = runner.assess(folder, {"exit_code": item["exit_code"]})
            if observed["status"] != "passed":
                raise ValueError("invalid_regression_evidence")
            require_counts(observed["counts"], manifest["expected_tests"][name])
            ids = set(observed["test_ids"])
            if seen.intersection(ids):
                raise ValueError("duplicate_tests_across_suites")
            seen.update(ids)
            result["suites"].append(
                {"suite": name, "status": "passed", "counts": observed["counts"]}
            )
        if (
            check(root) != manifest
            or digest(root / MANIFEST) != before
            or git_identity(root) != identity
        ):
            raise ValueError("release_changed_during_acceptance")
        result.update(status="passed", total_tests=len(seen))
        result["suites"][0].pop("test_ids")
    except (OSError, ValueError, KeyError, TypeError, KeyboardInterrupt) as exc:
        result.update(
            status="failed",
            problem=str(exc) if isinstance(exc, ValueError) else type(exc).__name__,
        )
    result["completed_at"] = datetime.now(UTC).isoformat()
    runner.save(output / "verification.json", result)
    if result["status"] == "passed":
        (output / "release-body.md").write_text(release_body(result), encoding="utf-8")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "verify"))
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--timeout", type=int, default=900)
    defaults = runner.default_interpreters(ROOT)
    for name, path in defaults.items():
        parser.add_argument(f"--{name}-python", type=Path, default=path)
    args = parser.parse_args(argv)
    try:
        if args.action == "check":
            manifest = check()
            print(
                json.dumps(
                    {
                        "status": "passed",
                        "release_status": manifest["release_status"],
                        "source_files": len(manifest["files"]),
                        "tests_executed": 0,
                    }
                )
            )
            return 0
        output = args.output_dir or ROOT / "logs/test-runs" / (
            "platform-v1-" + uuid4().hex[:12]
        )
        result = verify(
            ROOT,
            output,
            {n: getattr(args, n + "_python") for n in defaults},
            args.timeout,
        )
        print(
            json.dumps(
                {k: result[k] for k in ("status", "tag")}
                | {
                    "total_tests": result.get("total_tests"),
                    "output_dir": str(output),
                    "problem": result.get("problem"),
                }
            )
        )
        return 0 if result["status"] == "passed" else 1
    except (OSError, ValueError) as exc:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "problem": str(exc)
                    if isinstance(exc, ValueError)
                    else type(exc).__name__,
                }
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
