#!/usr/bin/env python3
"""Validate the categorized paper library and rebuild all graph data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import build_graph


def paper_files(papers_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in papers_dir.rglob("*")
        if path.is_file()
        and path.suffix.lower() in {".pdf", ".pptx"}
        and build_graph.REPO_ROOT not in path.parents
    )


def validate_taxonomy(papers_dir: Path) -> tuple[list[Path], list[Path]]:
    recognized: list[Path] = []
    unclassified: list[Path] = []
    allowed = set(build_graph.STANDARD_CATEGORIES)
    for path in paper_files(papers_dir):
        if path.parent.parent == papers_dir and path.parent.name in allowed:
            recognized.append(path)
        else:
            unclassified.append(path)
    return recognized, unclassified


def previous_hashes(json_path: Path) -> set[str]:
    if not json_path.exists():
        return set()
    data = json.loads(json_path.read_text(encoding="utf-8"))
    hashes = {node["sha256"] for node in data.get("nodes", []) if node.get("sha256")}
    hashes.update(item["sha256"] for item in data.get("duplicates", []) if item.get("sha256"))
    return hashes


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--papers-dir", type=Path, default=build_graph.DEFAULT_PAPERS_DIR)
    parser.add_argument("--output-json", type=Path, default=build_graph.DEFAULT_JSON)
    parser.add_argument("--output-js", type=Path, default=build_graph.DEFAULT_JS)
    parser.add_argument(
        "--allow-unclassified",
        action="store_true",
        help="Rebuild categorized papers while reporting unrelated files that still await classification.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    papers_dir = args.papers_dir.expanduser().resolve()
    recognized, unclassified = validate_taxonomy(papers_dir)
    if unclassified:
        print("发现尚未归入标准类别的论文文件：")
        for path in unclassified:
            print(f"UNCLASSIFIED\t{path.relative_to(papers_dir)}")
        if not args.allow_unclassified:
            raise SystemExit("请先完成论文分类，再重新运行 make update")

    before = previous_hashes(args.output_json)
    graph = build_graph.build_graph(papers_dir)
    build_graph.write_graph(graph, args.output_json, args.output_js)
    after = {node["sha256"] for node in graph["nodes"]}
    after.update(item["sha256"] for item in graph["duplicates"])

    pdf_count = sum(path.suffix.lower() == ".pdf" for path in recognized)
    pptx_count = sum(path.suffix.lower() == ".pptx" for path in recognized)
    print(
        f"更新完成：PDF {pdf_count}，PPTX {pptx_count}，"
        f"新增 {len(after - before)}，移除 {len(before - after)}，"
        f"内部引用 {graph['metadata']['citation_edges']} 条。"
    )
    for category in graph["categories"]:
        node = next(node for node in graph["nodes"] if node["id"] == category["main_node"])
        print(f"MAIN\t{category['label']}\t{node['citation_count']}\t{node['title']}")


if __name__ == "__main__":
    main()
