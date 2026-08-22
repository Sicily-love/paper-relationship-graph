#!/usr/bin/env python3
"""Fail the v1 release when versions, bundled runtime, or local data diverge."""

from __future__ import annotations

import argparse
import plistlib
import subprocess
from pathlib import Path

import library_health


ROOT = Path(__file__).resolve().parents[1]


def check_release(papers_dir: Path | None) -> list[str]:
    errors: list[str] = []
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    if version not in readme:
        errors.append("README 版本号与 VERSION 不一致")
    if f"Paper Atlas {version}" not in html:
        errors.append("网页版本号与 VERSION 不一致")

    source_plist = plistlib.loads((ROOT / "platform" / "macos" / "Info.plist").read_bytes())
    app_plist_path = ROOT / "Paper Atlas.app" / "Contents" / "Info.plist"
    if not app_plist_path.exists():
        errors.append("缺少 Paper Atlas.app")
    else:
        app_plist = plistlib.loads(app_plist_path.read_bytes())
        if source_plist != app_plist:
            errors.append("应用 Info.plist 与源码不一致")
        if app_plist.get("CFBundleShortVersionString") != version:
            errors.append("应用版本号与 VERSION 不一致")

    runtime = ROOT / "Paper Atlas.app" / "Contents" / "Resources" / "runtime"
    required = [
        "VERSION", "requirements.txt", "scripts/app_backend.py", "scripts/library_health.py",
        "scripts/task_center.py", "web/index.html", "web/app.js", "config/tasks.json",
    ]
    for relative in required:
        source = ROOT / relative
        bundled = runtime / relative
        if not bundled.exists() or source.read_bytes() != bundled.read_bytes():
            errors.append(f"应用内运行资源不同步：{relative}")

    if papers_dir is not None:
        health = library_health.validate_library(papers_dir)
        if health["status"] != "healthy":
            errors.extend(f"论文库：{item['title']}" for item in health["issues"])

    graph = library_health.load_json(library_health.DEFAULT_GRAPH, {})
    if any("confidence" not in edge or "evidence" not in edge for edge in (graph.get("edges") or {}).get("citation", [])):
        errors.append("引用关系缺少可信度或证据")
    if not (ROOT / "preview.png").is_file():
        errors.append("缺少 README 预览图")

    signature = subprocess.run(
        ["codesign", "--verify", "--deep", "--strict", str(ROOT / "Paper Atlas.app")],
        capture_output=True, text=True, check=False,
    )
    if signature.returncode:
        errors.append("Paper Atlas.app 签名校验失败")
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--papers-dir", type=Path, default=ROOT.parent)
    parser.add_argument(
        "--skip-library",
        action="store_true",
        help="只检查仓库和应用包；用于没有本地论文 PDF 的 CI 环境",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    papers_dir = None if args.skip_library else args.papers_dir.expanduser().resolve()
    errors = check_release(papers_dir)
    if errors:
        for error in errors:
            print(f"ERROR\t{error}")
        raise SystemExit(1)
    print("Paper Atlas v1.0.0 release check passed")


if __name__ == "__main__":
    main()
