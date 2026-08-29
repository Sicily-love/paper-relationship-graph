#!/usr/bin/env python3
"""Conservatively classify new papers and rebuild the Paper Atlas graph."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader

import build_graph
import discover_papers
import update_library
from discovery_utils import normalize_title, load_json, write_text_atomic


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REVIEW_QUEUE = REPO_ROOT / ".cache" / "classification-review.json"


def review_item_id(relative_path: str) -> str:
    return hashlib.sha256(relative_path.encode("utf-8")).hexdigest()[:16]


def normalize_pending(items: list[dict]) -> list[dict]:
    return [
        {"id": review_item_id(str(item["path"])), **item}
        for item in items
    ]


def write_review_queue(items: list[dict], path: Path = DEFAULT_REVIEW_QUEUE) -> dict:
    data = {
        "version": 1,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "items": normalize_pending(items),
    }
    write_text_atomic(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    return data


def load_review_queue(path: Path = DEFAULT_REVIEW_QUEUE) -> dict:
    data = load_json(path, {"version": 1, "updated_at": None, "items": []})
    return data if isinstance(data, dict) else {"version": 1, "updated_at": None, "items": []}


def paper_candidate(path: Path) -> dict:
    text = ""
    if path.suffix.lower() == ".pdf":
        reader = PdfReader(path)
        text = "\n".join((page.extract_text() or "") for page in reader.pages[:3])
    return {
        "title": path.stem,
        "abstract": build_graph.extract_abstract(text) or text[:1800],
        "topics": [],
        "supporting_papers": [],
    }


def classify_files(papers_dir: Path, dry_run: bool = False) -> dict:
    papers_dir = papers_dir.expanduser().resolve()
    _recognized, unclassified = update_library.validate_taxonomy(papers_dir)
    known_papers = [
        path for path in papers_dir.rglob("*.pdf")
        if path.parent.parent == papers_dir and path.parent.name in build_graph.STANDARD_CATEGORIES
    ]
    moved: list[dict] = []
    pending: list[dict] = []
    for path in unclassified:
        normalized_stem = normalize_title(path.stem)
        matching_paper = next(
            (
                known for known in known_papers
                if len(normalized_stem) >= 8
                and (
                    normalized_stem in normalize_title(known.stem)
                    or normalize_title(known.stem) in normalized_stem
                )
            ),
            None,
        )
        try:
            classification = (
                {
                    "suggested_category": matching_paper.parent.name,
                    "category_confidence": "高",
                    "category_reason": f"标题与已归档论文 {matching_paper.stem} 匹配",
                    "category_rule_version": discover_papers.CATEGORY_RULE_VERSION,
                }
                if matching_paper is not None
                else discover_papers.classify_candidate(paper_candidate(path))
            )
        except Exception as error:
            pending.append({
                "path": str(path.relative_to(papers_dir)),
                "suggested_category": "",
                "confidence": "读取失败",
                "reason": f"无法读取论文内容：{type(error).__name__}",
            })
            continue
        category = classification.get("suggested_category")
        confidence = classification.get("category_confidence")
        if not category or confidence != "高":
            pending.append({
                "path": str(path.relative_to(papers_dir)),
                "suggested_category": category or "",
                "confidence": confidence or "需确认",
                "reason": classification.get("category_reason"),
                "rule_version": classification.get("category_rule_version", discover_papers.CATEGORY_RULE_VERSION),
            })
            continue
        destination = papers_dir / str(category) / path.name
        if destination.exists():
            pending.append({
                "path": str(path.relative_to(papers_dir)),
                "suggested_category": category,
                "confidence": "需确认",
                "reason": "目标类别已有同名文件",
            })
            continue
        if not dry_run:
            destination.parent.mkdir(parents=True, exist_ok=True)
            path.replace(destination)
        moved.append({
            "path": str(path.relative_to(papers_dir)),
            "destination": str(destination.relative_to(papers_dir)),
            "reason": classification.get("category_reason"),
            "rule_version": classification.get("category_rule_version", discover_papers.CATEGORY_RULE_VERSION),
        })
    return {"classified": moved, "pending": pending, "dry_run": dry_run}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--papers-dir", type=Path, default=build_graph.DEFAULT_PAPERS_DIR)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = classify_files(args.papers_dir, args.dry_run)
    result["review"] = write_review_queue(result["pending"])
    result["graph_updated"] = False
    if not args.dry_run:
        graph = build_graph.build_graph(
            args.papers_dir.expanduser().resolve(), build_graph.DEFAULT_EXTRACTION_CACHE
        )
        build_graph.write_graph(graph, build_graph.DEFAULT_JSON, build_graph.DEFAULT_JS)
        result["graph_updated"] = True
    print(json.dumps(result, ensure_ascii=False))
    print(f"分类完成：自动归档 {len(result['classified'])}，等待确认 {len(result['pending'])}。")


if __name__ == "__main__":
    main()
