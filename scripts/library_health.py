#!/usr/bin/env python3
"""Validate Paper Atlas data, files, categories, and recoverable operations."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import build_graph
from discovery_utils import DEFAULT_DISCOVERY_JS, DEFAULT_DISCOVERY_JSON, DEFAULT_GRAPH, load_json


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GRAPH_JS = REPO_ROOT / "web" / "data" / "graph-data.js"
REMOVED_LIBRARY_DIR = ".paper-atlas-removed"


def javascript_payload(path: Path, prefix: str) -> dict:
    text = path.read_text(encoding="utf-8").strip()
    if not text.startswith(prefix) or not text.endswith(";"):
        raise ValueError(f"{path.name} 格式无效")
    value = json.loads(text[len(prefix) : -1])
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} 内容无效")
    return value


def issue(code: str, severity: str, title: str, detail: str, action: str | None = None) -> dict:
    value = {"code": code, "severity": severity, "title": title, "detail": detail}
    if action:
        value["action"] = action
    return value


def validate_library(
    papers_dir: Path,
    graph_path: Path = DEFAULT_GRAPH,
    graph_js_path: Path = DEFAULT_GRAPH_JS,
    discovery_path: Path = DEFAULT_DISCOVERY_JSON,
    discovery_js_path: Path = DEFAULT_DISCOVERY_JS,
) -> dict:
    papers_dir = papers_dir.expanduser().resolve()
    issues: list[dict] = []
    graph: dict = {}
    discovery: dict = {}

    try:
        graph = load_json(graph_path, {})
        if not isinstance(graph, dict) or not graph.get("nodes"):
            raise ValueError("图谱为空")
        browser_graph = {key: value for key, value in graph.items() if key != "external_references"}
        if browser_graph != javascript_payload(graph_js_path, "window.PAPER_GRAPH="):
            issues.append(issue(
                "graph-pair-mismatch", "error", "图谱数据不同步",
                "graph.json 与浏览器使用的 graph-data.js 内容不同。", "rebuild",
            ))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        issues.append(issue("graph-invalid", "error", "图谱数据无法读取", str(error), "rebuild"))

    try:
        discovery = load_json(discovery_path, {"candidates": [], "decisions": {}})
        if not isinstance(discovery, dict):
            raise ValueError("候选数据不是对象")
        if discovery != javascript_payload(discovery_js_path, "window.PAPER_DISCOVERY="):
            issues.append(issue(
                "discovery-pair-mismatch", "error", "候选数据不同步",
                "discovery.json 与浏览器使用的数据不同。", "repair-data",
            ))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        issues.append(issue("discovery-invalid", "error", "候选数据无法读取", str(error), "repair-data"))

    categories = set(build_graph.STANDARD_CATEGORIES)
    missing_categories = sorted(category for category in categories if not (papers_dir / category).is_dir())
    if missing_categories:
        issues.append(issue(
            "categories-missing", "error", "缺少标准分类目录",
            "、".join(missing_categories), "rebuild",
        ))

    library_files = [
        path for path in papers_dir.rglob("*")
        if path.is_file()
        and path.suffix.lower() in {".pdf", ".pptx"}
        and REPO_ROOT not in path.parents
        and REMOVED_LIBRARY_DIR not in path.relative_to(papers_dir).parts
    ]
    unclassified = sorted(
        str(path.relative_to(papers_dir))
        for path in library_files
        if path.parent.parent != papers_dir or path.parent.name not in categories
    )
    if unclassified:
        issues.append(issue(
            "unclassified-files", "error", "存在未分类论文",
            "、".join(unclassified[:8]) + (f" 等 {len(unclassified)} 个文件" if len(unclassified) > 8 else ""),
            "classify",
        ))

    nodes = graph.get("nodes", []) if isinstance(graph, dict) else []
    edges = (graph.get("edges") or {}).get("citation", []) if isinstance(graph, dict) else []
    node_ids = {node.get("id") for node in nodes}
    graph_paths = {str(node.get("path")) for node in nodes}
    pdf_paths = {
        str(path.relative_to(papers_dir))
        for path in library_files
        if path.suffix.lower() == ".pdf" and path.parent.name in categories
    }
    missing_nodes = sorted(pdf_paths - graph_paths)
    stale_nodes = sorted(graph_paths - pdf_paths)
    if missing_nodes or stale_nodes:
        detail_parts = []
        if missing_nodes:
            detail_parts.append(f"{len(missing_nodes)} 篇 PDF 尚未进入图谱")
        if stale_nodes:
            detail_parts.append(f"{len(stale_nodes)} 个节点已找不到 PDF")
        issues.append(issue("graph-files-mismatch", "error", "论文文件与图谱不一致", "；".join(detail_parts), "rebuild"))

    broken_edges = sum(
        edge.get("source") not in node_ids or edge.get("target") not in node_ids
        for edge in edges
    )
    if broken_edges:
        issues.append(issue("broken-edges", "error", "引用关系包含无效节点", f"共 {broken_edges} 条。", "rebuild"))

    metadata = graph.get("metadata", {}) if isinstance(graph, dict) else {}
    if nodes and (
        metadata.get("unique_papers") != len(nodes)
        or metadata.get("citation_edges") != len(edges)
    ):
        issues.append(issue("metadata-counts", "error", "图谱统计与实际数据不符", "论文或引用计数需要重建。", "rebuild"))

    pending = [
        candidate_id for candidate_id, decision in (discovery.get("decisions") or {}).items()
        if decision.get("status") in {"accepted", "replaced"}
        and decision.get("graph_status") == "pending"
    ]
    if pending:
        issues.append(issue(
            "pending-graph", "warning", "有已归档论文等待更新图谱",
            f"共 {len(pending)} 篇，可安全重试图谱更新。", "rebuild",
        ))

    severities = {item["severity"] for item in issues}
    status = "error" if "error" in severities else "warning" if issues else "healthy"
    return {
        "status": status,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "summary": "论文库状态正常" if status == "healthy" else f"发现 {len(issues)} 项需要处理",
        "issues": issues,
        "stats": {
            "papers": len(nodes),
            "pdf_files": len(pdf_paths),
            "pptx_files": sum(path.suffix.lower() == ".pptx" for path in library_files),
            "citations": len(edges),
            "categories": len(categories),
            "pending_graph_updates": len(pending),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--papers-dir", type=Path, default=REPO_ROOT.parent)
    return parser.parse_args()


def main() -> None:
    result = validate_library(parse_args().papers_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(1 if result["status"] == "error" else 0)


if __name__ == "__main__":
    main()
