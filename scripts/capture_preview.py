#!/usr/bin/env python3
"""Capture the README preview with macOS WebKit, without launching Chrome."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "preview.png"
SOURCE = REPO_ROOT / "platform" / "macos" / "CapturePreview.m"
CACHE = REPO_ROOT / ".cache" / "preview-capture"
EXECUTABLE = CACHE / "CapturePreview"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def build_capture_tool() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    module_cache = CACHE / "clang-modules"
    module_cache.mkdir(parents=True, exist_ok=True)
    if EXECUTABLE.exists() and EXECUTABLE.stat().st_mtime >= SOURCE.stat().st_mtime:
        return

    environment = os.environ.copy()
    environment["CLANG_MODULE_CACHE_PATH"] = str(module_cache)
    subprocess.run(
        [
            "xcrun",
            "clang",
            "-fobjc-arc",
            "-framework",
            "Cocoa",
            "-framework",
            "WebKit",
            "-mmacosx-version-min=10.15",
            "-o",
            str(EXECUTABLE),
            str(SOURCE),
        ],
        check=True,
        env=environment,
    )


def main() -> None:
    args = parse_args()
    if sys.platform != "darwin":
        raise SystemExit("preview.png 目前需要在 macOS 上使用原生 WebKit 生成。")

    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    build_capture_tool()
    subprocess.run(
        [
            str(EXECUTABLE),
            str(REPO_ROOT / "web" / "index.html"),
            str(output),
        ],
        check=True,
    )
    print(f"Updated {output} with macOS WebKit")


if __name__ == "__main__":
    main()
