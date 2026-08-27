#!/usr/bin/env python3
"""Describe and perform the small, recoverable Paper Atlas maintenance actions."""

from __future__ import annotations

import json
from pathlib import Path

import build_graph
from discovery_utils import (
    DEFAULT_DISCOVERY_JS,
    DEFAULT_DISCOVERY_JSON,
    load_json,
    write_discovery,
)


ACTION_SPECS = {
    "rebuild": {
        "label": "重新生成图谱",
        "description": "重新读取论文文件并生成图谱数据。",
    },
    "classify": {
        "label": "整理未分类论文",
        "description": "自动归档高置信度论文，其余论文进入分类待审核。",
    },
    "repair-data": {
        "label": "修复候选数据",
        "description": "以可读取的一份候选数据为准，重新生成 JSON 与页面数据。",
    },
    "ensure-categories": {
        "label": "补齐分类目录",
        "description": "创建缺失的标准分类目录，然后重新生成图谱。",
    },
    "refresh-shared": {
        "label": "刷新共同引用",
        "description": "重新查询论文库的共同引用证据。",
    },
    "retry-discovery": {
        "label": "重试论文发现",
        "description": "使用最近一次发现方式重新搜索。",
    },
}


def action_spec(identifier: str, issue_codes: list[str] | None = None) -> dict:
    """Return a stable frontend-safe action descriptor."""
    spec = ACTION_SPECS.get(identifier)
    if spec is None:
        raise ValueError(f"未知维护操作：{identifier}")
    result = {"id": identifier, **spec}
    if issue_codes:
        result["issue_codes"] = list(dict.fromkeys(issue_codes))
    return result


def actions_for_issues(issues: list[dict]) -> list[dict]:
    """Collapse repeated issue actions while preserving the first-seen order."""
    grouped: dict[str, list[str]] = {}
    for item in issues:
        identifier = str(item.get("action") or "")
        if identifier not in ACTION_SPECS:
            continue
        grouped.setdefault(identifier, []).append(str(item.get("code") or ""))
    return [action_spec(identifier, codes) for identifier, codes in grouped.items()]


def ensure_category_directories(papers_dir: Path) -> list[str]:
    """Create only missing standard directories and report what changed."""
    papers_dir = papers_dir.expanduser().resolve()
    created = []
    for category in build_graph.STANDARD_CATEGORIES:
        path = papers_dir / category
        if not path.is_dir():
            path.mkdir(parents=True, exist_ok=True)
            created.append(category)
    return created


def _load_browser_discovery(path: Path) -> dict:
    text = path.read_text(encoding="utf-8").strip()
    prefix = "window.PAPER_DISCOVERY="
    if not text.startswith(prefix) or not text.endswith(";"):
        raise ValueError(f"{path.name} 格式无效")
    value = json.loads(text[len(prefix) : -1])
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} 内容无效")
    return value


def repair_discovery_pair(
    json_path: Path = DEFAULT_DISCOVERY_JSON,
    javascript_path: Path = DEFAULT_DISCOVERY_JS,
) -> dict:
    """Repair the discovery pair without discarding recoverable user data."""
    try:
        data = load_json(json_path, None)
    except (OSError, json.JSONDecodeError):
        data = None
    source = "json"
    if not isinstance(data, dict):
        try:
            data = _load_browser_discovery(javascript_path)
            source = "javascript"
        except (OSError, ValueError) as error:
            raise ValueError("候选 JSON 与页面数据均无法读取，未执行覆盖") from error
    write_discovery(data, json_path, javascript_path)
    return {"source": source, "candidate_count": len(data.get("candidates") or [])}
