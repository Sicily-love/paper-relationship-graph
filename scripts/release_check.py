#!/usr/bin/env python3
"""Fail the v1 release when versions, bundled runtime, or local data diverge."""

from __future__ import annotations

import argparse
import json
import os
import plistlib
import subprocess
from pathlib import Path

import library_health
import prepare_release_seed
import generate_release_notes


ROOT = Path(__file__).resolve().parents[1]


def check_release(papers_dir: Path | None, public_release: bool = False) -> list[str]:
    errors: list[str] = []
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    if version not in readme:
        errors.append("README 版本号与 VERSION 不一致")
    if f"Paper Atlas {version}" not in html:
        errors.append("网页版本号与 VERSION 不一致")
    errors.extend(generate_release_notes.check_generated_files())

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
        "VERSION", "requirements.txt", "scripts/app_backend.py", "scripts/app_services.py",
        "scripts/generate_release_notes.py", "scripts/library_health.py",
        "scripts/task_center.py", "scripts/prepare_release_seed.py",
        "scripts/embed_python_runtime.py",
        "web/index.html", "web/app.js", "web/data/releases.json",
        "web/data/releases-data.js", "config/tasks.json", "config/discovery-evaluation.json",
    ]
    for relative in required:
        source = ROOT / relative
        bundled = runtime / relative
        if not bundled.exists() or source.read_bytes() != bundled.read_bytes():
            errors.append(f"应用内运行资源不同步：{relative}")

    errors.extend(prepare_release_seed.privacy_issues(runtime))

    embedded_python = ROOT / "Paper Atlas.app" / "Contents" / "Resources" / "python" / "bin" / "python3"
    python_root = embedded_python.parents[1]
    python_manifest = python_root / "paper-atlas-runtime.json"
    if not embedded_python.is_file() or not os.access(embedded_python, os.X_OK):
        errors.append("应用没有内置 Python 运行时")
    else:
        probe = subprocess.run(
            [
                str(embedded_python), "-I", "-B", "-c",
                "import ssl, pypdf; assert ssl.create_default_context().cert_store_stats()['x509_ca'] > 0; print(pypdf.__version__)",
            ],
            cwd="/tmp",
            env={
                "HOME": "/tmp", "PATH": "/usr/bin:/bin",
                "PYTHONNOUSERSITE": "1", "SSL_CERT_FILE": "/etc/ssl/cert.pem",
            },
            capture_output=True,
            text=True,
            check=False,
        )
        if probe.returncode:
            errors.append("应用内置 Python 或 pypdf 无法独立启动")
        architectures = subprocess.run(
            ["lipo", "-archs", str(embedded_python)],
            capture_output=True, text=True, check=False,
        ).stdout.split()
        if not {"x86_64", "arm64"}.issubset(set(architectures)):
            errors.append("应用内置 Python 不是 Intel 与 Apple Silicon 通用版本")
        for item in python_root.rglob("*"):
            if not item.is_file() or item.is_symlink():
                continue
            kind = subprocess.run(
                ["file", "-b", str(item)], capture_output=True, text=True, check=False,
            ).stdout
            if "Mach-O" not in kind:
                continue
            dependencies = subprocess.run(
                ["otool", "-L", str(item)], capture_output=True, text=True, check=False,
            ).stdout
            if "/Library/Frameworks/Python.framework" in dependencies:
                errors.append(f"内置 Python 仍包含不可移动的系统路径：{item.relative_to(python_root)}")
                break
        if not any(python_root.glob("lib/python3.*/LICENSE.txt")):
            errors.append("应用内置 Python 缺少许可证文件")
        if not any(python_root.glob("lib/python3.*/site-packages/pypdf-*.dist-info/licenses/LICENSE")):
            errors.append("应用内置 pypdf 缺少许可证文件")
    try:
        manifest = json.loads(python_manifest.read_text(encoding="utf-8"))
        if (
            not manifest.get("offline_ready")
            or not manifest.get("pypdf_version")
            or not manifest.get("typing_extensions_version")
        ):
            raise ValueError
    except (OSError, ValueError, json.JSONDecodeError):
        errors.append("应用内置 Python 清单缺失或无效")

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
    if public_release:
        signature_details = subprocess.run(
            ["codesign", "-dv", "--verbose=4", str(ROOT / "Paper Atlas.app")],
            capture_output=True, text=True, check=False,
        )
        details = signature_details.stdout + signature_details.stderr
        if "Authority=Developer ID Application:" not in details or "Signature=adhoc" in details:
            errors.append("公开发布包没有使用 Developer ID Application 签名")
        dmg = ROOT / "dist" / f"Paper-Atlas-{version}.dmg"
        if not dmg.exists():
            errors.append("缺少公开发布 DMG")
        else:
            ticket = subprocess.run(
                ["xcrun", "stapler", "validate", str(dmg)],
                capture_output=True, text=True, check=False,
            )
            if ticket.returncode:
                errors.append("DMG 没有有效的 Apple 公证票据")
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--papers-dir", type=Path, default=ROOT.parent)
    parser.add_argument(
        "--skip-library",
        action="store_true",
        help="只检查仓库和应用包；用于没有本地论文 PDF 的 CI 环境",
    )
    parser.add_argument(
        "--public-release",
        action="store_true",
        help="同时要求 Developer ID 签名和 Apple 公证票据",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    papers_dir = None if args.skip_library else args.papers_dir.expanduser().resolve()
    errors = check_release(papers_dir, public_release=args.public_release)
    if errors:
        for error in errors:
            print(f"ERROR\t{error}")
        raise SystemExit(1)
    print(f"Paper Atlas v{version} release check passed")


if __name__ == "__main__":
    main()
