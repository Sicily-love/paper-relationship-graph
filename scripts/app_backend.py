#!/usr/bin/env python3
"""Native Paper Atlas command bridge; business logic lives in app_services."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from app_services import AppServices


REPO_ROOT = Path(__file__).resolve().parents[1]
COMMAND_METHODS = {
    "state": "state",
    "topics": "save_topics",
    "discover": "run_discovery",
    "candidate": "review_candidate",
    "feedback": "candidate_feedback",
    "classification": "review_classification",
    "clear": "clear_candidates",
    "maintenance": "rebuild_graph",
    "diagnostics": "run_diagnostics",
    "tasks": "manage_tasks",
    "backup": "manage_backup",
}


def read_body() -> dict:
    try:
        body = json.load(sys.stdin)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("请求内容不是有效 JSON") from error
    if not isinstance(body, dict):
        raise ValueError("请求内容格式无效")
    return body


def prepare(papers_dir: Path) -> dict:
    import start_app

    embedded = os.environ.get("PAPER_ATLAS_USE_CURRENT_PYTHON") == "1"
    python = Path(sys.executable).resolve() if embedded else start_app.ensure_runtime()
    start_app.refresh_graph_if_needed(python, papers_dir)
    return {
        "ready": True,
        "runtime_python": str(python),
        "offline_runtime": embedded,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", *COMMAND_METHODS])
    parser.add_argument("--papers-dir", type=Path, default=REPO_ROOT.parent)
    return parser.parse_args()


def dispatch(command: str, papers_dir: Path) -> dict:
    if command == "prepare":
        return prepare(papers_dir)
    service = AppServices(papers_dir)
    method = getattr(service, COMMAND_METHODS[command])
    return method() if command == "state" else method(read_body())


def main() -> None:
    args = parse_args()
    print(json.dumps(dispatch(args.command, args.papers_dir), ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, SystemExit) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False))
        raise SystemExit(1)
