#!/usr/bin/env python3
"""Replace mutable personal state in an app runtime with public release defaults."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from discovery_utils import load_json, write_discovery, write_text_atomic


EMPTY_DISCOVERY = {
    "metadata": {
        "candidate_count": 0,
        "new_count": 0,
        "shared_reference_count": 0,
        "arxiv_topic_count": 0,
        "errors": [],
    },
    "topics": [],
    "decisions": {},
    "candidates": [],
}


def sanitize_runtime(runtime: Path) -> None:
    runtime = runtime.expanduser().resolve()
    config_path = runtime / "config" / "discovery.json"
    config = load_json(config_path, {})
    if not isinstance(config, dict):
        raise ValueError("搜索配置格式无效")
    config["topics"] = []
    write_text_atomic(config_path, json.dumps(config, ensure_ascii=False, indent=2) + "\n")
    write_discovery(
        EMPTY_DISCOVERY,
        runtime / "web" / "data" / "discovery.json",
        runtime / "web" / "data" / "discovery-data.js",
    )


def privacy_issues(runtime: Path) -> list[str]:
    runtime = runtime.expanduser().resolve()
    issues: list[str] = []
    config = load_json(runtime / "config" / "discovery.json", {})
    discovery = load_json(runtime / "web" / "data" / "discovery.json", {})
    if not isinstance(config, dict):
        issues.append("发布包的搜索配置格式无效")
        config = {}
    if not isinstance(discovery, dict):
        issues.append("发布包的候选数据格式无效")
        discovery = {}
    discovery_js_path = runtime / "web" / "data" / "discovery-data.js"
    try:
        discovery_js = discovery_js_path.read_text(encoding="utf-8").strip()
        prefix = "window.PAPER_DISCOVERY="
        if not discovery_js.startswith(prefix) or not discovery_js.endswith(";"):
            raise ValueError
        if json.loads(discovery_js[len(prefix) : -1]) != discovery:
            issues.append("发布包的候选 JSON 与页面数据不一致")
    except (OSError, ValueError, json.JSONDecodeError):
        issues.append("发布包的候选页面数据无法读取")
    if config.get("topics"):
        issues.append("发布包包含自定义搜索主题")
    if discovery.get("topics"):
        issues.append("发布包包含最近搜索主题")
    if discovery.get("candidates"):
        issues.append("发布包包含推荐候选")
    if discovery.get("decisions"):
        issues.append("发布包包含候选审核记录")

    sensitive_path = re.compile(r"(?:/Users/|/home/|[A-Za-z]:\\\\Users\\\\)")
    for relative in (
        "config/discovery.json",
        "config/tasks.json",
        "web/data/discovery.json",
        "web/data/discovery-data.js",
        "web/data/graph.json",
        "web/data/graph-data.js",
    ):
        path = runtime / relative
        if path.exists() and sensitive_path.search(path.read_text(encoding="utf-8")):
            issues.append(f"发布包包含绝对用户路径：{relative}")
    return issues


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runtime", type=Path)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.check:
        sanitize_runtime(args.runtime)
    issues = privacy_issues(args.runtime)
    if issues:
        for issue in issues:
            print(f"ERROR\t{issue}")
        raise SystemExit(1)
    print("发布运行包隐私检查通过")


if __name__ == "__main__":
    main()
