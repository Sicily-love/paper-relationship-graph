#!/usr/bin/env python3
"""Accept or reject a reviewed discovery candidate."""

from __future__ import annotations

import argparse
import copy
import hashlib
import re
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
import urllib.request
from pathlib import Path

from pypdf import PdfReader

import build_graph
from discovery_utils import DEFAULT_DISCOVERY_JS, DEFAULT_DISCOVERY_JSON, load_json, write_discovery


USER_AGENT = "PaperAtlas/1.0 (local research library discovery)"


@dataclass
class ArchiveReceipt:
    destination: Path
    moved_from: Path | None = None
    created: bool = False

    def rollback(self) -> None:
        if self.moved_from is not None and self.destination.exists():
            self.moved_from.parent.mkdir(parents=True, exist_ok=True)
            self.destination.replace(self.moved_from)
        elif self.created:
            self.destination.unlink(missing_ok=True)


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


def archive_candidate(candidate: dict, category: str, papers_dir: Path) -> ArchiveReceipt:
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
            return ArchiveReceipt(categorized_match)
        unclassified_match = matches[0] if matches else None
        if destination.exists():
            raise SystemExit(f"目标位置已有同名但内容不同的文件：{destination.relative_to(papers_dir)}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        if unclassified_match is not None:
            unclassified_match.replace(destination)
            receipt = ArchiveReceipt(destination, moved_from=unclassified_match)
        else:
            temporary_path.replace(destination)
            receipt = ArchiveReceipt(destination, created=True)
    finally:
        temporary_path.unlink(missing_ok=True)
    return receipt


def accept(candidate: dict, category: str, papers_dir: Path) -> Path:
    """Archive a candidate and return its final path (legacy command API)."""
    return archive_candidate(candidate, category, papers_dir).destination


def record_decision(
    data: dict,
    candidate: dict,
    action: str,
    category: str | None = None,
    destination: Path | None = None,
    papers_dir: Path | None = None,
) -> None:
    decision = {"status": action + "ed", "decided_at": datetime.now(timezone.utc).isoformat()}
    if action == "accept":
        if destination is None or papers_dir is None or not category:
            raise ValueError("归档决策缺少目标位置")
        candidate["status"] = "accepted"
        candidate["accepted_path"] = str(destination.relative_to(papers_dir))
        candidate["graph_status"] = "pending"
        decision.update({
            "accepted_path": candidate["accepted_path"],
            "category": category,
            "graph_status": "pending",
        })
    else:
        candidate["status"] = "rejected"
    data.setdefault("decisions", {})[candidate["id"]] = decision


def apply_decision(data: dict, candidate_id: str, action: str, papers_dir: Path, category: str | None = None) -> dict:
    """Apply a reviewed candidate decision and return the updated candidate."""
    if action not in {"accept", "reject"}:
        raise ValueError("未知审核操作")
    candidate = find_candidate(data, candidate_id)
    if action == "accept":
        if not category:
            raise ValueError("请选择论文类别")
        destination = accept(candidate, category, papers_dir.resolve())
        record_decision(data, candidate, action, category, destination, papers_dir.resolve())
    else:
        record_decision(data, candidate, action)
    return candidate


def commit_decision(
    data: dict,
    candidate_id: str,
    action: str,
    papers_dir: Path,
    category: str | None,
    discovery_json: Path,
    discovery_js: Path,
) -> dict:
    """Archive and persist a review decision, rolling the file back if persistence fails."""
    if action not in {"accept", "reject"}:
        raise ValueError("未知审核操作")
    original = copy.deepcopy(data)
    candidate = find_candidate(data, candidate_id)
    receipt: ArchiveReceipt | None = None
    try:
        if action == "accept":
            if not category:
                raise ValueError("请选择论文类别")
            papers_dir = papers_dir.resolve()
            receipt = archive_candidate(candidate, category, papers_dir)
            record_decision(
                data, candidate, action, category, receipt.destination, papers_dir
            )
        else:
            record_decision(data, candidate, action)
        write_discovery(data, discovery_json, discovery_js)
    except Exception:
        if receipt is not None:
            receipt.rollback()
        data.clear()
        data.update(original)
        raise
    return candidate


def mark_graph_status(
    data: dict,
    candidate_id: str,
    status: str,
    discovery_json: Path,
    discovery_js: Path,
    error: str | None = None,
) -> None:
    if status not in {"complete", "pending"}:
        raise ValueError("未知图谱状态")
    candidate = find_candidate(data, candidate_id)
    candidate["graph_status"] = status
    decision = data.setdefault("decisions", {}).setdefault(candidate_id, {})
    decision["graph_status"] = status
    decision["graph_updated_at"] = datetime.now(timezone.utc).isoformat()
    if error:
        decision["graph_error"] = error
    else:
        decision.pop("graph_error", None)
    write_discovery(data, discovery_json, discovery_js)


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
    candidate = commit_decision(
        data,
        args.id,
        args.action,
        args.papers_dir.expanduser().resolve(),
        args.category,
        args.discovery_json,
        args.discovery_js,
    )
    if args.action == "accept":
        print(f"已加入论文库：{candidate['accepted_path']}")
    else:
        print(f"已忽略候选：{candidate['title']}")


if __name__ == "__main__":
    main()
