#!/usr/bin/env python3
"""Run smoke, change-targeted, or full Paper Atlas tests."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TESTS_DIR = ROOT / "tests"
SMOKE_TESTS = {
    "test_api_contract.py",
    "test_library_layout.py",
    "test_start_app.py",
}
FULL_TESTS = {path.name for path in TESTS_DIR.glob("test_*.py")}

PATH_RULES: tuple[tuple[tuple[str, ...], set[str]], ...] = (
    (("web/", "platform/macos/"), {"test_api_contract.py", "test_v1_foundations.py"}),
    (("scripts/api_", "scripts/app_backend.py", "scripts/app_services.py", "scripts/job_manager.py", "scripts/runtime_store.py"),
     {"test_api_contract.py", "test_app_backend.py", "test_maintenance_actions.py", "test_review_api.py"}),
    (("scripts/discover_papers.py", "scripts/discovery_", "config/discovery"),
     {"test_discovery.py", "test_review_api.py", "test_v13_features.py"}),
    (("scripts/manage_candidate.py",), {"test_review_api.py", "test_v13_features.py"}),
    (("scripts/build_graph.py",), {"test_graph_rules.py", "test_v13_features.py", "test_v1_foundations.py"}),
    (("scripts/library_", "scripts/classify_library.py", "scripts/update_library.py"),
     {"test_library_layout.py", "test_graph_rules.py", "test_v1_foundations.py"}),
    (("scripts/maintenance_actions.py", "scripts/system_diagnostics.py"),
     {"test_maintenance_actions.py", "test_v1_foundations.py"}),
    (("scripts/start_app.py", "platform/windows/"), {"test_start_app.py", "test_v1_foundations.py"}),
    (("scripts/task_center.py", "config/tasks.json"), {"test_v1_foundations.py"}),
    (("scripts/backup_restore.py",), {"test_v1_foundations.py"}),
    (("README.md", "CHANGELOG.md", "VERSION"), {"test_v1_foundations.py"}),
)

FULL_TEST_TRIGGERS = {
    "requirements.txt",
    "Makefile",
    ".github/workflows/ci.yml",
    "scripts/discovery_utils.py",
    "scripts/shared_lock.py",
}


def git_lines(*args: str) -> set[str]:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=False,
    )
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def changed_paths(base: str | None = None) -> set[str]:
    paths: set[str] = set()
    if base:
        result = subprocess.run(
            ["git", "diff", "--name-only", f"{base}...HEAD"],
            cwd=ROOT, capture_output=True, text=True, check=False,
        )
        if result.returncode:
            # An unavailable/shallow base must never accidentally downgrade CI
            # to the smoke suite.
            return {"requirements.txt"}
        paths.update(line.strip() for line in result.stdout.splitlines() if line.strip())
    else:
        paths.update(git_lines("diff", "--name-only", "HEAD"))
    paths.update(git_lines("diff", "--cached", "--name-only"))
    paths.update(git_lines("ls-files", "--others", "--exclude-standard"))
    return paths


def select_tests(paths: set[str]) -> set[str]:
    """Choose the smallest safe suite for a set of repository-relative paths."""
    if not paths:
        return set(SMOKE_TESTS)
    if paths & FULL_TEST_TRIGGERS:
        return set(FULL_TESTS)

    selected = set(SMOKE_TESTS)
    unknown_code = False
    for path in paths:
        if path.startswith("tests/test_") and path.endswith(".py"):
            selected.add(Path(path).name)
            continue
        if path.startswith(("docs/", "assets/")) or path in {"LICENSE", ".gitignore", "preview.png"}:
            continue
        matched = False
        for prefixes, tests in PATH_RULES:
            if path.startswith(prefixes):
                selected.update(tests)
                matched = True
        if path.startswith(("scripts/", "web/", "platform/", "config/")) and not matched:
            unknown_code = True
    return set(FULL_TESTS) if unknown_code else selected


def run(test_names: set[str]) -> int:
    existing = sorted(name for name in test_names if (TESTS_DIR / name).is_file())
    command = [sys.executable, "-m", "unittest", "-v", *(str(TESTS_DIR / name) for name in existing)]
    print("测试范围：" + "、".join(existing), flush=True)
    return subprocess.run(command, cwd=ROOT, check=False).returncode


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("smoke", "changed", "full"), nargs="?", default="changed")
    parser.add_argument("--base", help="Git base SHA/ref used to select changed tests")
    parser.add_argument("--list", action="store_true", help="Only print the selected test files")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths = changed_paths(args.base) if args.mode == "changed" else set()
    tests = set(FULL_TESTS) if args.mode == "full" else set(SMOKE_TESTS)
    if args.mode == "changed":
        tests = select_tests(paths)
        print(f"检测到 {len(paths)} 个改动文件；自动选择 {len(tests)}/{len(FULL_TESTS)} 个测试文件。", flush=True)
    if args.list:
        print("\n".join(sorted(tests)))
        return 0
    return run(tests)


if __name__ == "__main__":
    raise SystemExit(main())
