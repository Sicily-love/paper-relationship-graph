#!/usr/bin/env python3
"""Export and restore Paper Atlas settings and review history without PDFs."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from discovery_utils import (
    DEFAULT_CONFIG,
    DEFAULT_DISCOVERY_JS,
    DEFAULT_DISCOVERY_JSON,
    DEFAULT_GRAPH,
    load_json,
    write_discovery,
    write_text_atomic,
)
import json


BACKUP_SCHEMA = 1


def create_backup(
    config_path: Path = DEFAULT_CONFIG,
    discovery_path: Path = DEFAULT_DISCOVERY_JSON,
    graph_path: Path = DEFAULT_GRAPH,
    tasks_path: Path | None = None,
) -> dict:
    tasks_path = tasks_path or (config_path.parent / "tasks.json")
    graph = load_json(graph_path, {"metadata": {}, "categories": []})
    return {
        "schema_version": BACKUP_SCHEMA,
        "product": "Paper Atlas",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "config": load_json(config_path, {}),
        "tasks": load_json(tasks_path, {}),
        "discovery": load_json(discovery_path, {"metadata": {}, "candidates": [], "decisions": {}}),
        "graph_manifest": {
            "metadata": graph.get("metadata", {}),
            "categories": graph.get("categories", []),
        },
    }


def validate_backup(value: object) -> dict:
    if not isinstance(value, dict) or value.get("product") != "Paper Atlas":
        raise ValueError("这不是 Paper Atlas 备份文件")
    if value.get("schema_version") != BACKUP_SCHEMA:
        raise ValueError("备份版本暂不支持")
    if not isinstance(value.get("config"), dict):
        raise ValueError("备份缺少搜索主题配置")
    if not isinstance(value.get("tasks"), dict):
        raise ValueError("备份缺少自动任务配置")
    discovery = value.get("discovery")
    if not isinstance(discovery, dict) or not isinstance(discovery.get("candidates", []), list):
        raise ValueError("备份中的候选记录无效")
    if not isinstance(discovery.get("decisions", {}), dict):
        raise ValueError("备份中的审核记录无效")
    return value


def restore_backup(
    value: object,
    config: dict,
    tasks: dict,
    config_path: Path = DEFAULT_CONFIG,
    discovery_path: Path = DEFAULT_DISCOVERY_JSON,
    discovery_js_path: Path = DEFAULT_DISCOVERY_JS,
    tasks_path: Path | None = None,
) -> dict:
    backup = validate_backup(value)
    tasks_path = tasks_path or (config_path.parent / "tasks.json")
    previous_config = config_path.read_bytes() if config_path.exists() else None
    previous_tasks = tasks_path.read_bytes() if tasks_path.exists() else None
    try:
        write_text_atomic(config_path, json.dumps(config, ensure_ascii=False, indent=2) + "\n")
        write_text_atomic(tasks_path, json.dumps(tasks, ensure_ascii=False, indent=2) + "\n")
        write_discovery(backup["discovery"], discovery_path, discovery_js_path)
    except Exception:
        if previous_config is None:
            config_path.unlink(missing_ok=True)
        else:
            config_path.write_bytes(previous_config)
        if previous_tasks is None:
            tasks_path.unlink(missing_ok=True)
        else:
            tasks_path.write_bytes(previous_tasks)
        raise
    return {"message": "备份已恢复", "created_at": backup.get("created_at")}
