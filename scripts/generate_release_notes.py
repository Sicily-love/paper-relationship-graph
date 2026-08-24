#!/usr/bin/env python3
"""Generate browser-ready release notes from CHANGELOG.md."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from discovery_utils import write_text_atomic


ROOT = Path(__file__).resolve().parents[1]
CHANGELOG = ROOT / "CHANGELOG.md"
VERSION = ROOT / "VERSION"
OUTPUT_JSON = ROOT / "web" / "data" / "releases.json"
OUTPUT_JS = ROOT / "web" / "data" / "releases-data.js"
RELEASE_HEADING = re.compile(r"^##\s+([^\s—]+)(?:\s+—\s+(\d{4}-\d{2}-\d{2}))?\s*$")


def parse_changelog(text: str) -> list[dict]:
    releases: list[dict] = []
    current: dict | None = None
    for line in text.splitlines():
        heading = RELEASE_HEADING.match(line)
        if heading:
            if current and current["changes"]:
                releases.append(current)
            current = {
                "version": heading.group(1),
                "date": heading.group(2),
                "changes": [],
            }
            continue
        if current is not None and line.startswith("- "):
            current["changes"].append(line[2:].strip())
    if current and current["changes"]:
        releases.append(current)
    return releases


def release_notes() -> dict:
    version = VERSION.read_text(encoding="utf-8").strip()
    releases = parse_changelog(CHANGELOG.read_text(encoding="utf-8"))
    current = next((item for item in releases if item["version"] == version), None)
    if current is None:
        raise ValueError(f"CHANGELOG.md 缺少当前版本 {version}")
    return {"current_version": version, "releases": releases}


def rendered_files() -> tuple[str, str]:
    data = release_notes()
    pretty = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    compact = "window.PAPER_RELEASES=" + json.dumps(
        data, ensure_ascii=False, separators=(",", ":")
    ) + ";\n"
    return pretty, compact


def check_generated_files() -> list[str]:
    expected_json, expected_js = rendered_files()
    issues = []
    if not OUTPUT_JSON.exists() or OUTPUT_JSON.read_text(encoding="utf-8") != expected_json:
        issues.append("web/data/releases.json 与 CHANGELOG.md 不一致")
    if not OUTPUT_JS.exists() or OUTPUT_JS.read_text(encoding="utf-8") != expected_js:
        issues.append("web/data/releases-data.js 与 CHANGELOG.md 不一致")
    return issues


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> None:
    if parse_args().check:
        issues = check_generated_files()
        if issues:
            raise SystemExit("\n".join(issues))
        print("Release notes are up to date")
        return
    output_json, output_js = rendered_files()
    write_text_atomic(OUTPUT_JSON, output_json)
    write_text_atomic(OUTPUT_JS, output_js)
    print(f"Generated release notes for Paper Atlas {release_notes()['current_version']}")


if __name__ == "__main__":
    main()
