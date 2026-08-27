#!/usr/bin/env python3
"""Native Paper Atlas command bridge; business logic lives in app_services."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
import sys
import traceback
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
    "logs": "runtime_logs",
    "remove_node": "remove_graph_node",
}


def record_operation(command: str, status: str, message: str = "") -> None:
    if command in {"state", "logs", "prepare"}:
        return
    path = REPO_ROOT / ".cache" / "operation-log.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "command": command,
        "status": status,
    }
    if message:
        event["message"] = message
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")


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
    result = dispatch(args.command, args.papers_dir)
    record_operation(args.command, "completed", str(result.get("message") or ""))
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, SystemExit) as error:
        record_operation(sys.argv[1] if len(sys.argv) > 1 else "unknown", "failed", str(error))
        print(json.dumps({"error": str(error)}, ensure_ascii=False))
        raise SystemExit(1)
    except Exception as error:  # Always return a structured error to the native bridge.
        traceback.print_exc(file=sys.stderr)
        message = str(error).strip() or type(error).__name__
        record_operation(sys.argv[1] if len(sys.argv) > 1 else "unknown", "failed", message)
        print(json.dumps({"error": f"本地操作失败：{message}"}, ensure_ascii=False))
        raise SystemExit(1)
