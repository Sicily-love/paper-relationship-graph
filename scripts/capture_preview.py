#!/usr/bin/env python3
"""Capture a deterministic local preview with an installed Chromium browser."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "preview.png"
CHROME_CANDIDATES = (
    Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
    Path("/Applications/Chromium.app/Contents/MacOS/Chromium"),
)


def find_browser() -> str | None:
    for candidate in CHROME_CANDIDATES:
        if candidate.is_file():
            return str(candidate)
    for name in ("google-chrome", "chromium", "chromium-browser"):
        executable = shutil.which(name)
        if executable:
            return executable
    return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    browser = find_browser()
    if not browser:
        print("未找到 Chrome/Chromium，已跳过 preview.png 更新。", file=sys.stderr)
        return
    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    url = (REPO_ROOT / "web" / "index.html").resolve().as_uri()
    subprocess.run(
        [
            browser,
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            "--window-size=1440,1000",
            "--virtual-time-budget=2500",
            f"--screenshot={output}",
            url,
        ],
        check=True,
    )
    print(f"Updated {output}")


if __name__ == "__main__":
    main()
