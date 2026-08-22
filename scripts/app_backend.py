#!/usr/bin/env python3
"""Command bridge used by the native Paper Atlas app without a localhost server."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def read_body() -> dict:
    try:
        body = json.load(sys.stdin)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("请求内容不是有效 JSON") from error
    if not isinstance(body, dict):
        raise ValueError("请求内容格式无效")
    return body


def api_modules():
    import build_graph
    import discover_papers
    import manage_candidate
    import serve_graph
    from discovery_utils import (
        DEFAULT_CONFIG,
        DEFAULT_DISCOVERY_JS,
        DEFAULT_DISCOVERY_JSON,
        load_json,
        write_discovery,
    )

    return {
        "build_graph": build_graph,
        "discover_papers": discover_papers,
        "manage_candidate": manage_candidate,
        "serve_graph": serve_graph,
        "DEFAULT_CONFIG": DEFAULT_CONFIG,
        "DEFAULT_DISCOVERY_JS": DEFAULT_DISCOVERY_JS,
        "DEFAULT_DISCOVERY_JSON": DEFAULT_DISCOVERY_JSON,
        "load_json": load_json,
        "write_discovery": write_discovery,
    }


def state(modules: dict) -> dict:
    config = modules["load_json"](modules["DEFAULT_CONFIG"], {})
    return {
        "discovery": modules["serve_graph"].validated_discovery(),
        "topics": config.get("topics", []),
        "shared_reference_minimum": int(
            config.get("shared_references", {}).get("min_library_citations", 2)
        ),
        "categories": [
            {"id": identifier, "label": re.sub(r"^\d+_", "", identifier)}
            for identifier in modules["build_graph"].STANDARD_CATEGORIES
        ],
    }


def save_topics(modules: dict, body: dict) -> dict:
    topics = modules["serve_graph"].validate_topics(body.get("topics"))
    config = modules["load_json"](modules["DEFAULT_CONFIG"], {})
    config["topics"] = topics
    modules["serve_graph"].write_json_atomic(modules["DEFAULT_CONFIG"], config)
    return {"message": "搜索主题已保存", "topics": topics}


def review_candidate(modules: dict, body: dict, papers_dir: Path) -> dict:
    action = str(body.get("action") or "")
    candidate_id = str(body.get("id") or "")
    category = str(body.get("category") or "") or None
    data = modules["load_json"](modules["DEFAULT_DISCOVERY_JSON"], {"metadata": {}, "candidates": []})
    candidate = modules["manage_candidate"].apply_decision(
        data, candidate_id, action, papers_dir, category
    )
    modules["write_discovery"](
        data, modules["DEFAULT_DISCOVERY_JSON"], modules["DEFAULT_DISCOVERY_JS"]
    )
    if action == "accept":
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "update_library.py"),
                    "--papers-dir",
                    str(papers_dir),
                    "--allow-unclassified",
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=360,
                check=False,
            )
            graph_updated = result.returncode == 0
        except (subprocess.TimeoutExpired, OSError):
            graph_updated = False
    else:
        graph_updated = None
    return {
        "message": (
            "已加入论文库并更新图谱"
            if action == "accept" and graph_updated
            else "论文已归档；图谱将在下次整理时更新"
            if action == "accept"
            else "已忽略该候选"
        ),
        "graph_updated": graph_updated,
        "candidate": candidate,
        "discovery": modules["serve_graph"].validated_discovery(),
    }


def clear_candidates(modules: dict) -> dict:
    data = modules["load_json"](modules["DEFAULT_DISCOVERY_JSON"], {"metadata": {}, "candidates": []})
    removed = modules["serve_graph"].clear_new_candidates(data)
    modules["write_discovery"](
        data, modules["DEFAULT_DISCOVERY_JSON"], modules["DEFAULT_DISCOVERY_JS"]
    )
    return {
        "message": f"已清空 {removed} 篇待审核候选",
        "removed_count": removed,
        "discovery": modules["serve_graph"].validated_discovery(),
    }


def run_discovery(modules: dict, body: dict) -> dict:
    mode = modules["serve_graph"].discovery_mode(body.get("mode"))
    arguments = [sys.executable, str(REPO_ROOT / "scripts" / "discover_papers.py")]
    if mode == "arxiv":
        arguments.append("--skip-shared")
    else:
        config = modules["load_json"](modules["DEFAULT_CONFIG"], {})
        minimum = modules["serve_graph"].validate_shared_reference_minimum(
            body.get("min_library_citations", 2)
        )
        config.setdefault("shared_references", {})["min_library_citations"] = minimum
        modules["serve_graph"].write_json_atomic(modules["DEFAULT_CONFIG"], config)
        arguments.append("--skip-arxiv")
    result = subprocess.run(
        arguments,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=360,
        check=False,
    )
    if result.returncode:
        message = (result.stderr or result.stdout or "论文发现失败").strip().splitlines()[-1]
        raise ValueError(message)
    return {
        "message": "arXiv 搜索已完成" if mode == "arxiv" else "共同引用计算已完成",
        "mode": mode,
        "discovery": modules["serve_graph"].validated_discovery(),
    }


def prepare(papers_dir: Path) -> dict:
    import start_app

    python = start_app.ensure_runtime()
    start_app.refresh_graph_if_needed(python, papers_dir)
    return {"ready": True, "runtime_python": str(python)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "state", "topics", "discover", "candidate", "clear"])
    parser.add_argument("--papers-dir", type=Path, default=REPO_ROOT.parent)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    papers_dir = args.papers_dir.expanduser().resolve()
    if args.command == "prepare":
        result = prepare(papers_dir)
    else:
        modules = api_modules()
        if args.command == "state":
            result = state(modules)
        elif args.command == "topics":
            result = save_topics(modules, read_body())
        elif args.command == "discover":
            result = run_discovery(modules, read_body())
        elif args.command == "clear":
            result = clear_candidates(modules)
        else:
            result = review_candidate(modules, read_body(), papers_dir)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, SystemExit) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False))
        raise SystemExit(1)
