#!/usr/bin/env python3
"""Manage Paper Atlas daily tasks and their local execution history."""

from __future__ import annotations

import argparse
import json
import os
import plistlib
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

from discovery_utils import load_json, write_text_atomic


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO_ROOT / "config" / "tasks.json"
DEFAULT_STATUS = REPO_ROOT / ".cache" / "task-status.json"
TASK_DEFINITIONS = {
    "classification": {
        "label": "论文分类整理",
        "time": "10:30",
        "command": "classify",
    },
    "arxiv": {
        "label": "arXiv 论文发现",
        "time": "11:00",
        "command": "discover",
    },
}


def default_config() -> dict:
    return {
        "version": 1,
        "tasks": {
            identifier: {"enabled": True, "time": definition["time"]}
            for identifier, definition in TASK_DEFINITIONS.items()
        },
    }


def validate_time(value: object) -> str:
    text = str(value or "")
    match = re.fullmatch(r"([01]\d|2[0-3]):([0-5]\d)", text)
    if not match:
        raise ValueError("任务时间需要使用 HH:MM 格式")
    return text


def validate_config(raw: object) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("自动任务配置无效")
    raw_tasks = raw.get("tasks") or {}
    tasks = {}
    for identifier, definition in TASK_DEFINITIONS.items():
        item = raw_tasks.get(identifier) or {}
        tasks[identifier] = {
            "enabled": bool(item.get("enabled", True)),
            "time": validate_time(item.get("time", definition["time"])),
        }
    return {"version": 1, "tasks": tasks}


def load_config(path: Path = DEFAULT_CONFIG) -> dict:
    return validate_config(load_json(path, default_config()))


def save_config(config: dict, path: Path = DEFAULT_CONFIG) -> dict:
    normalized = validate_config(config)
    write_text_atomic(path, json.dumps(normalized, ensure_ascii=False, indent=2) + "\n")
    return normalized


def next_run(time_text: str, now: datetime | None = None) -> str:
    now = now or datetime.now().astimezone()
    hour, minute = (int(value) for value in time_text.split(":"))
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=1)
    return candidate.isoformat()


def task_state(config_path: Path = DEFAULT_CONFIG, status_path: Path = DEFAULT_STATUS) -> dict:
    config = load_config(config_path)
    history = load_json(status_path, {"tasks": {}})
    tasks = []
    for identifier, definition in TASK_DEFINITIONS.items():
        item = config["tasks"][identifier]
        status = (history.get("tasks") or {}).get(identifier, {})
        agent_path = Path.home() / "Library" / "LaunchAgents" / f"com.liangchenyu.paperatlas.{identifier}.plist"
        installed = sys.platform == "darwin" and agent_path.exists()
        tasks.append({
            "id": identifier,
            "label": definition["label"],
            "enabled": item["enabled"],
            "time": item["time"],
            "installed": installed,
            "next_run": next_run(item["time"]) if item["enabled"] and installed else None,
            "last_status": status.get("status", "never"),
            "last_started_at": status.get("started_at"),
            "last_finished_at": status.get("finished_at"),
            "last_message": status.get("message", "尚未安装" if item["enabled"] and not installed else "尚未运行"),
            "last_log": status.get("log", ""),
        })
    return {
        "supported": sys.platform == "darwin",
        "scheduler": "launchd" if sys.platform == "darwin" else "manual",
        "tasks": tasks,
    }


def update_status(task_id: str, values: dict, status_path: Path = DEFAULT_STATUS) -> None:
    data = load_json(status_path, {"version": 1, "tasks": {}})
    data.setdefault("tasks", {}).setdefault(task_id, {}).update(values)
    write_text_atomic(status_path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def task_command(task_id: str, papers_dir: Path) -> list[str]:
    if task_id == "classification":
        return [sys.executable, str(REPO_ROOT / "scripts" / "classify_library.py"), "--papers-dir", str(papers_dir)]
    if task_id == "arxiv":
        return [sys.executable, str(REPO_ROOT / "scripts" / "discover_papers.py"), "--skip-shared"]
    raise ValueError("未知自动任务")


def run_task(task_id: str, papers_dir: Path, status_path: Path = DEFAULT_STATUS) -> dict:
    if task_id not in TASK_DEFINITIONS:
        raise ValueError("未知自动任务")
    started = datetime.now().astimezone().isoformat()
    update_status(task_id, {"status": "running", "started_at": started, "message": "正在运行"}, status_path)
    result = subprocess.run(
        task_command(task_id, papers_dir.expanduser().resolve()),
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )
    output = "\n".join(part.strip() for part in (result.stdout, result.stderr) if part.strip())
    message = (output.splitlines()[-1] if output else "任务已完成")[:500]
    status = "success" if result.returncode == 0 else "failed"
    update_status(task_id, {
        "status": status,
        "finished_at": datetime.now().astimezone().isoformat(),
        "message": message,
        "log": output[-12000:],
    }, status_path)
    if result.returncode:
        raise ValueError(message)
    return {"message": message, "task_id": task_id, "status": status}


def launch_agent_payload(task_id: str, item: dict, papers_dir: Path) -> dict:
    hour, minute = (int(value) for value in item["time"].split(":"))
    label = f"com.liangchenyu.paperatlas.{task_id}"
    return {
        "Label": label,
        "ProgramArguments": [
            sys.executable,
            str(REPO_ROOT / "scripts" / "task_center.py"),
            "run", "--task", task_id, "--papers-dir", str(papers_dir),
        ],
        "StartCalendarInterval": {"Hour": hour, "Minute": minute},
        "ProcessType": "Background",
        "EnvironmentVariables": {
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
            "SSL_CERT_FILE": "/etc/ssl/cert.pem",
        },
        "StandardOutPath": str(REPO_ROOT / ".cache" / f"{task_id}.log"),
        "StandardErrorPath": str(REPO_ROOT / ".cache" / f"{task_id}.log"),
    }


def install_launch_agents(
    config: dict,
    papers_dir: Path,
    launch_agents_dir: Path | None = None,
    load_agents: bool = True,
) -> list[str]:
    if sys.platform != "darwin" and launch_agents_dir is None:
        return []
    launch_agents_dir = launch_agents_dir or (Path.home() / "Library" / "LaunchAgents")
    launch_agents_dir.mkdir(parents=True, exist_ok=True)
    messages = []
    domain = f"gui/{os.getuid()}"
    for task_id, item in config["tasks"].items():
        label = f"com.liangchenyu.paperatlas.{task_id}"
        path = launch_agents_dir / f"{label}.plist"
        if load_agents:
            subprocess.run(["launchctl", "bootout", domain, str(path)], capture_output=True, check=False)
        if item["enabled"]:
            path.write_bytes(plistlib.dumps(launch_agent_payload(task_id, item, papers_dir)))
            if load_agents:
                result = subprocess.run(["launchctl", "bootstrap", domain, str(path)], capture_output=True, text=True, check=False)
                if result.returncode:
                    raise ValueError((result.stderr or "自动任务安装失败").strip())
            messages.append(f"{TASK_DEFINITIONS[task_id]['label']} {item['time']}")
        else:
            path.unlink(missing_ok=True)
    return messages


def configure_tasks(raw: dict, papers_dir: Path) -> dict:
    config = save_config(raw)
    installed = install_launch_agents(config, papers_dir)
    return {"message": "自动任务已更新", "installed": installed, **task_state()}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("state", "run"))
    parser.add_argument("--task", choices=tuple(TASK_DEFINITIONS))
    parser.add_argument("--papers-dir", type=Path, default=REPO_ROOT.parent)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "state":
        result = task_state()
    else:
        if not args.task:
            raise SystemExit("run 需要 --task")
        result = run_task(args.task, args.papers_dir)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
