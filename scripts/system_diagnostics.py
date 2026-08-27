#!/usr/bin/env python3
"""Build a copyable Paper Atlas health and discovery diagnostic report."""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import discovery_evaluation
import discover_papers
import library_health
import task_center
from discovery_utils import DEFAULT_CONFIG, DEFAULT_DISCOVERY_JSON, DEFAULT_GRAPH, load_json


USER_AGENT = "PaperAtlas/1.0 (local diagnostics)"


def check(identifier: str, label: str, status: str, summary: str, details: object = None) -> dict:
    return {
        "id": identifier,
        "label": label,
        "status": status,
        "summary": summary,
        "details": details,
    }


def provider_probe(url: str, timeout: int = 12) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    started = datetime.now(timezone.utc)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response.read(256)
            elapsed = (datetime.now(timezone.utc) - started).total_seconds()
            return {"available": True, "http_status": response.status, "latency_ms": round(elapsed * 1000)}
    except urllib.error.HTTPError as error:
        return {
            "available": False,
            "http_status": error.code,
            "error": "请求频率受限" if error.code == 429 else str(error),
        }
    except (urllib.error.URLError, TimeoutError) as error:
        return {"available": False, "error": str(error)}


def recent_debug_events(limit: int = 40) -> list[dict]:
    path = discover_papers.DEFAULT_DEBUG_LOG
    if not path.exists():
        return []
    result = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]:
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            result.append(value)
    return result


def report_text(report: dict) -> str:
    metrics = report["evaluation"]["metrics"]
    lines = [
        "Paper Atlas 诊断报告",
        f"生成时间：{report['generated_at']}",
        f"总体状态：{report['status']}",
        "",
        "发现评测",
        f"Precision {metrics['precision']:.1%} · Recall {metrics['recall']:.1%} · "
        f"分类 {metrics['classification_accuracy']:.1%} · 去重 {metrics['dedupe_accuracy']:.1%}",
        "",
        "检查项",
    ]
    for item in report["checks"]:
        marker = "通过" if item["status"] == "passed" else "提醒" if item["status"] == "warning" else "失败"
        lines.append(f"[{marker}] {item['label']}：{item['summary']}")
    if report.get("recent_filters"):
        lines.extend(("", "最近发现阶段"))
        for item in report["recent_filters"]:
            lines.append(f"- {item['event']}：{json.dumps(item.get('details') or {}, ensure_ascii=False)}")
    return "\n".join(lines)


def run(papers_dir: Path, include_network: bool = True) -> dict:
    papers_dir = papers_dir.expanduser().resolve()
    checks = []
    health = library_health.validate_library(papers_dir)
    checks.append(check(
        "library", "论文库与图谱",
        "passed" if health.get("status") == "healthy" else "warning" if health.get("status") == "warning" else "failed",
        health.get("summary") or "状态未知", health.get("issues") or [],
    ))

    graph = load_json(DEFAULT_GRAPH, {"metadata": {}})
    graph_metadata = graph.get("metadata", {}) if isinstance(graph, dict) else {}
    checks.append(check(
        "graph_index", "增量图谱与外部引用索引",
        "passed" if "external_references" in graph else "warning",
        f"库外引用 {int(graph_metadata.get('external_references') or 0):,} 条；"
        f"本次复用 {int(graph_metadata.get('reused_papers') or 0)} 篇，"
        f"重解析 {int(graph_metadata.get('parsed_papers') or 0)} 篇",
        {
            "external_references": graph_metadata.get("external_references", 0),
            "reused_papers": graph_metadata.get("reused_papers", 0),
            "parsed_papers": graph_metadata.get("parsed_papers", 0),
        },
    ))

    try:
        evaluation = discovery_evaluation.run()
        evaluation_error = None
    except (OSError, ValueError, json.JSONDecodeError) as error:
        evaluation_error = str(error)
        evaluation = {
            "status": "failed",
            "case_count": 0,
            "metrics": {
                "precision": 0.0,
                "recall": 0.0,
                "classification_accuracy": 0.0,
                "dedupe_accuracy": 0.0,
            },
            "cases": [],
        }
    checks.append(check(
        "evaluation", "固定发现评测",
        "passed" if evaluation["status"] == "passed" else "failed",
        (
            f"评测集无法读取：{evaluation_error}"
            if evaluation_error
            else f"{evaluation['case_count']} 个样本；召回率 {evaluation['metrics']['recall']:.0%}，"
                 f"精确率 {evaluation['metrics']['precision']:.0%}"
        ),
        evaluation["metrics"],
    ))

    cache_path = DEFAULT_CONFIG.parents[1] / ".cache" / "openalex-library.json"
    cache = load_json(cache_path, {})
    reference_index = cache.get("reference_index", {}) if isinstance(cache, dict) else {}
    cache_ok = cache.get("version") == 3 and isinstance(reference_index, dict)
    checks.append(check(
        "reference_cache", "共同引用证据缓存",
        "passed" if cache_ok and reference_index else "warning",
        f"缓存版本 {cache.get('version') or '未知'}，持久证据 {len(reference_index) if isinstance(reference_index, dict) else 0} 篇",
        {"path": str(cache_path), "reference_index_count": len(reference_index) if isinstance(reference_index, dict) else 0},
    ))

    discovery = load_json(DEFAULT_DISCOVERY_JSON, {"metadata": {}, "candidates": [], "decisions": {}})
    metadata = discovery.get("metadata", {}) if isinstance(discovery, dict) else {}
    decisions = discovery.get("decisions", {}) if isinstance(discovery, dict) else {}
    unique_decisions = {
        (
            value.get("decided_at"), value.get("status"), value.get("accepted_path"),
            value.get("superseded_path"),
        )
        for value in decisions.values()
        if isinstance(value, dict)
    }
    errors = metadata.get("errors") or []
    checks.append(check(
        "last_discovery", "最近一次论文发现",
        "warning" if errors else "passed",
        f"候选 {int(metadata.get('candidate_count') or 0)} 篇，错误 {len(errors)} 条",
        {
            "updated_at": metadata.get("updated_at"),
            "run_mode": metadata.get("run_mode"),
            "errors": errors,
            "decision_counts": {
                status: sum(1 for value in unique_decisions if value[1] == status)
                for status in ("accepted", "dismissed", "rejected", "replaced", "purged")
            },
        },
    ))

    task_state = task_center.task_state()
    enabled_tasks = [item for item in task_state.get("tasks", []) if item.get("enabled")]
    failed_tasks = [item for item in enabled_tasks if item.get("last_status") == "failed"]
    checks.append(check(
        "tasks", "App 本机任务",
        "warning" if failed_tasks else "passed",
        f"已启用 {len(enabled_tasks)} 项" + (f"，失败 {len(failed_tasks)} 项" if failed_tasks else ""),
        [{"id": item.get("id"), "last_status": item.get("last_status"), "next_run": item.get("next_run")} for item in enabled_tasks],
    ))

    if include_network:
        arxiv = provider_probe("https://export.arxiv.org/api/query?id_list=1706.03762&max_results=1")
        openalex = provider_probe("https://api.openalex.org/works/W2741809807?select=id")
        if arxiv.get("available"):
            provider_status = "passed"
            provider_summary = f"arXiv {arxiv.get('latency_ms')} ms；OpenAlex " + (
                f"{openalex.get('latency_ms')} ms" if openalex.get("available") else "不可用"
            )
        elif arxiv.get("http_status") == 429 and openalex.get("available"):
            provider_status = "warning"
            provider_summary = "arXiv 当前限流，OpenAlex 回退可用"
        else:
            provider_status = "warning" if openalex.get("available") else "failed"
            provider_summary = "arXiv 不可用，OpenAlex 回退可用" if openalex.get("available") else "arXiv 与 OpenAlex 均不可用"
        checks.append(check(
            "providers", "论文数据服务", provider_status, provider_summary,
            {"arxiv": arxiv, "openalex": openalex},
        ))

    events = recent_debug_events()
    interesting = []
    for event in events:
        if event.get("event") not in {
            "arxiv_topic", "arxiv_fallback", "highly_cited_topic",
            "shared_reference_summary", "candidate_merge", "discovery_finished",
        }:
            continue
        interesting.append({
            "event": event.get("event"),
            "timestamp": event.get("timestamp"),
            "details": {key: value for key, value in event.items() if key not in {"event", "timestamp"}},
        })
    failed = any(item["status"] == "failed" for item in checks)
    warning = any(item["status"] == "warning" for item in checks)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "failed" if failed else "warning" if warning else "healthy",
        "checks": checks,
        "evaluation": evaluation,
        "recent_filters": interesting[-8:],
        "paths": {
            "papers": str(papers_dir),
            "graph": str(DEFAULT_GRAPH),
            "discovery": str(DEFAULT_DISCOVERY_JSON),
            "config": str(DEFAULT_CONFIG),
        },
    }
    report["copy_text"] = report_text(report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--papers-dir", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(args.papers_dir, not args.offline), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
