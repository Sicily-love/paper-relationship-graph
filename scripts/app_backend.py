#!/usr/bin/env python3
"""Command bridge used by the native Paper Atlas app without a localhost server."""

from __future__ import annotations

import argparse
import json
import os
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
    import backup_restore
    import build_graph
    import discover_papers
    import library_health
    import manage_candidate
    import serve_graph
    import task_center
    from discovery_utils import (
        DEFAULT_CONFIG,
        DEFAULT_DISCOVERY_JS,
        DEFAULT_DISCOVERY_JSON,
        load_json,
        write_discovery,
    )

    return {
        "backup_restore": backup_restore,
        "build_graph": build_graph,
        "discover_papers": discover_papers,
        "library_health": library_health,
        "manage_candidate": manage_candidate,
        "serve_graph": serve_graph,
        "task_center": task_center,
        "DEFAULT_CONFIG": DEFAULT_CONFIG,
        "DEFAULT_DISCOVERY_JS": DEFAULT_DISCOVERY_JS,
        "DEFAULT_DISCOVERY_JSON": DEFAULT_DISCOVERY_JSON,
        "load_json": load_json,
        "write_discovery": write_discovery,
    }


def state(modules: dict, papers_dir: Path | None = None) -> dict:
    config = modules["load_json"](modules["DEFAULT_CONFIG"], {})
    result = {
        "discovery": modules["serve_graph"].validated_discovery(),
        "topics": config.get("topics", []),
        "shared_reference_minimum": int(
            config.get("shared_references", {}).get("min_library_citations", 2)
        ),
        "highly_cited_minimum": int(
            config.get("highly_cited", {}).get("min_citations", 50)
        ),
        "categories": [
            {"id": identifier, "label": re.sub(r"^\d+_", "", identifier)}
            for identifier in modules["build_graph"].STANDARD_CATEGORIES
        ],
    }
    if papers_dir is not None and modules.get("library_health"):
        result["health"] = modules["library_health"].validate_library(papers_dir)
    if modules.get("task_center"):
        result["tasks"] = modules["task_center"].task_state()
    return result


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
    manager = modules["manage_candidate"]
    if hasattr(manager, "commit_decision"):
        candidate = manager.commit_decision(
            data, candidate_id, action, papers_dir, category,
            modules["DEFAULT_DISCOVERY_JSON"], modules["DEFAULT_DISCOVERY_JS"],
        )
    else:  # Backward-compatible test doubles.
        candidate = manager.apply_decision(data, candidate_id, action, papers_dir, category)
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
            graph_error = None if graph_updated else (
                (getattr(result, "stderr", "") or getattr(result, "stdout", "") or "图谱更新失败")
                .strip().splitlines()[-1]
            )
        except (subprocess.TimeoutExpired, OSError) as error:
            graph_updated = False
            graph_error = str(error)
        if hasattr(manager, "mark_graph_status"):
            manager.mark_graph_status(
                data, candidate_id, "complete" if graph_updated else "pending",
                modules["DEFAULT_DISCOVERY_JSON"], modules["DEFAULT_DISCOVERY_JS"],
                graph_error,
            )
    else:
        graph_updated = None
        graph_error = None
    return {
        "message": (
            "已加入论文库并更新图谱"
            if action == "accept" and graph_updated
            else "论文已归档；图谱将在下次整理时更新"
            if action == "accept"
            else "已忽略该候选"
        ),
        "graph_updated": graph_updated,
        "graph_error": graph_error,
        "candidate": candidate,
        "discovery": modules["serve_graph"].validated_discovery(),
    }


def rebuild_graph(modules: dict, papers_dir: Path) -> dict:
    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "update_library.py"),
            "--papers-dir", str(papers_dir), "--allow-unclassified",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=360,
        check=False,
    )
    if result.returncode:
        message = (result.stderr or result.stdout or "图谱更新失败").strip().splitlines()[-1]
        raise ValueError(message)
    data = modules["load_json"](
        modules["DEFAULT_DISCOVERY_JSON"], {"metadata": {}, "candidates": [], "decisions": {}}
    )
    manager = modules["manage_candidate"]
    changed = False
    for candidate_id, decision in (data.get("decisions") or {}).items():
        if decision.get("status") != "accepted" or decision.get("graph_status") != "pending":
            continue
        decision["graph_status"] = "complete"
        decision.pop("graph_error", None)
        candidate = next((item for item in data.get("candidates", []) if item.get("id") == candidate_id), None)
        if candidate:
            candidate["graph_status"] = "complete"
        changed = True
    if changed:
        modules["write_discovery"](
            data, modules["DEFAULT_DISCOVERY_JSON"], modules["DEFAULT_DISCOVERY_JS"]
        )
    health = modules["library_health"].validate_library(papers_dir) if modules.get("library_health") else None
    return {"message": "图谱已重新生成", "graph_updated": True, "health": health}


def task_action(modules: dict, body: dict, papers_dir: Path) -> dict:
    action = str(body.get("action") or "state")
    task_center = modules["task_center"]
    if action == "state":
        return task_center.task_state()
    if action == "run":
        result = task_center.run_task(str(body.get("task_id") or ""), papers_dir)
        return {**result, **task_center.task_state()}
    if action == "configure":
        return task_center.configure_tasks({"tasks": body.get("tasks")}, papers_dir)
    raise ValueError("未知自动任务操作")


def backup_action(modules: dict, body: dict) -> dict:
    action = str(body.get("action") or "export")
    backup_restore = modules["backup_restore"]
    if action == "export":
        return {"message": "备份已生成", "backup": backup_restore.create_backup()}
    if action != "restore":
        raise ValueError("未知备份操作")
    backup = backup_restore.validate_backup(body.get("backup"))
    config = dict(backup["config"])
    config["topics"] = modules["serve_graph"].validate_topics(config.get("topics"))
    tasks = modules["task_center"].validate_config(backup["tasks"])
    result = backup_restore.restore_backup(backup, config, tasks)
    return {**result, "discovery": modules["serve_graph"].validated_discovery()}


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
        arguments.extend(("--skip-shared", "--skip-highly-cited"))
    elif mode == "highly_cited":
        config = modules["load_json"](modules["DEFAULT_CONFIG"], {})
        minimum = modules["serve_graph"].validate_highly_cited_minimum(
            body.get("min_citations", config.get("highly_cited", {}).get("min_citations", 50))
        )
        config.setdefault("highly_cited", {})["min_citations"] = minimum
        modules["serve_graph"].write_json_atomic(modules["DEFAULT_CONFIG"], config)
        arguments.extend(("--skip-arxiv", "--skip-shared"))
    else:
        config = modules["load_json"](modules["DEFAULT_CONFIG"], {})
        minimum = modules["serve_graph"].validate_shared_reference_minimum(
            body.get("min_library_citations", 2)
        )
        config.setdefault("shared_references", {})["min_library_citations"] = minimum
        modules["serve_graph"].write_json_atomic(modules["DEFAULT_CONFIG"], config)
        arguments.extend(("--skip-arxiv", "--skip-highly-cited"))
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
        "message": (
            "arXiv 搜索已完成" if mode == "arxiv"
            else "领域高被引搜索已完成" if mode == "highly_cited"
            else "共同引用计算已完成"
        ),
        "mode": mode,
        "discovery": modules["serve_graph"].validated_discovery(),
    }


def prepare(papers_dir: Path) -> dict:
    import start_app

    python = (
        Path(sys.executable).resolve()
        if os.environ.get("PAPER_ATLAS_USE_CURRENT_PYTHON") == "1"
        else start_app.ensure_runtime()
    )
    start_app.refresh_graph_if_needed(python, papers_dir)
    return {
        "ready": True,
        "runtime_python": str(python),
        "offline_runtime": os.environ.get("PAPER_ATLAS_USE_CURRENT_PYTHON") == "1",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "state", "topics", "discover", "candidate", "clear", "maintenance", "tasks", "backup"])
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
            result = state(modules, papers_dir)
        elif args.command == "topics":
            result = save_topics(modules, read_body())
        elif args.command == "discover":
            result = run_discovery(modules, read_body())
        elif args.command == "clear":
            result = clear_candidates(modules)
        elif args.command == "maintenance":
            result = rebuild_graph(modules, papers_dir)
        elif args.command == "tasks":
            result = task_action(modules, read_body(), papers_dir)
        elif args.command == "backup":
            result = backup_action(modules, read_body())
        else:
            result = review_candidate(modules, read_body(), papers_dir)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, SystemExit) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False))
        raise SystemExit(1)
