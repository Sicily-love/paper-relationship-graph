#!/usr/bin/env python3
"""Accept or reject a reviewed discovery candidate."""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import tempfile
from datetime import datetime, timezone
import urllib.request
from pathlib import Path

from pypdf import PdfReader

import build_graph
from discovery_utils import DEFAULT_DISCOVERY_JS, DEFAULT_DISCOVERY_JSON, load_json, write_discovery


USER_AGENT = "PaperAtlas/1.0 (local research library discovery)"


def find_candidate(data: dict, candidate_id: str) -> dict:
    candidate = next((item for item in data.get("candidates", []) if item.get("id") == candidate_id), None)
    if not candidate:
        raise SystemExit(f"未找到候选：{candidate_id}")
    return candidate


def safe_filename(title: str) -> str:
    filename = re.sub(r"[/:*?\"<>|]+", " ", title)
    filename = re.sub(r"\s+", " ", filename).strip(" .")
    return (filename[:180].rstrip() or "paper") + ".pdf"


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def library_paper_files(papers_dir: Path) -> list[Path]:
    """Return every library paper, including files waiting at the root."""
    return sorted(
        path
        for path in papers_dir.rglob("*")
        if path.is_file()
        and path.suffix.lower() in {".pdf", ".pptx"}
        and build_graph.REPO_ROOT not in path.parents
    )


def is_standard_location(path: Path, papers_dir: Path) -> bool:
    return path.parent.parent == papers_dir and path.parent.name in build_graph.STANDARD_CATEGORIES


def accept(candidate: dict, category: str, papers_dir: Path) -> Path:
    if category not in build_graph.STANDARD_CATEGORIES:
        raise SystemExit(f"未知类别：{category}")
    pdf_url = candidate.get("pdf_url")
    if not pdf_url:
        raise SystemExit("该候选没有可下载的 PDF，请从来源页人工获取")
    destination = papers_dir / category / safe_filename(candidate["title"])

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temporary:
        temporary_path = Path(temporary.name)
    try:
        request = urllib.request.Request(str(pdf_url), headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=90) as response, temporary_path.open("wb") as output:
            shutil.copyfileobj(response, output)
        reader = PdfReader(temporary_path)
        if not reader.pages:
            raise SystemExit("下载文件不是可读 PDF")
        new_hash = file_hash(temporary_path)
        matches = [path for path in library_paper_files(papers_dir) if file_hash(path) == new_hash]
        categorized_match = next(
            (path for path in matches if is_standard_location(path, papers_dir)),
            None,
        )
        if categorized_match is not None:
            return categorized_match
        unclassified_match = matches[0] if matches else None
        if destination.exists():
            raise SystemExit(f"目标位置已有同名但内容不同的文件：{destination.relative_to(papers_dir)}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        if unclassified_match is not None:
            unclassified_match.replace(destination)
        else:
            temporary_path.replace(destination)
    finally:
        temporary_path.unlink(missing_ok=True)
    return destination


def apply_decision(data: dict, candidate_id: str, action: str, papers_dir: Path, category: str | None = None) -> dict:
    """Apply a reviewed candidate decision and return the updated candidate."""
    if action not in {"accept", "reject"}:
        raise ValueError("未知审核操作")
    candidate = find_candidate(data, candidate_id)
    decision = {"status": action + "ed", "decided_at": datetime.now(timezone.utc).isoformat()}
    if action == "accept":
        if not category:
            raise ValueError("请选择论文类别")
        destination = accept(candidate, category, papers_dir.resolve())
        candidate["status"] = "accepted"
        candidate["accepted_path"] = str(destination.relative_to(papers_dir.resolve()))
        decision["accepted_path"] = candidate["accepted_path"]
        decision["category"] = category
    else:
        candidate["status"] = "rejected"
    data.setdefault("decisions", {})[candidate["id"]] = decision
    return candidate


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("accept", "reject"))
    parser.add_argument("--id", required=True)
    parser.add_argument("--category")
    parser.add_argument("--papers-dir", type=Path, default=build_graph.DEFAULT_PAPERS_DIR)
    parser.add_argument("--discovery-json", type=Path, default=DEFAULT_DISCOVERY_JSON)
    parser.add_argument("--discovery-js", type=Path, default=DEFAULT_DISCOVERY_JS)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data = load_json(args.discovery_json, {"candidates": []})
    candidate = apply_decision(
        data,
        args.id,
        args.action,
        args.papers_dir.expanduser().resolve(),
        args.category,
    )
    write_discovery(data, args.discovery_json, args.discovery_js)
    if args.action == "accept":
        print(f"已加入论文库：{candidate['accepted_path']}")
    else:
        print(f"已忽略候选：{candidate['title']}")


if __name__ == "__main__":
    main()
