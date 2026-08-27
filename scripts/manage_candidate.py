#!/usr/bin/env python3
"""Accept or reject a reviewed discovery candidate."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

import build_graph
from discovery_utils import (
    DEFAULT_DISCOVERY_JS,
    DEFAULT_DISCOVERY_JSON,
    candidate_key,
    load_json,
    normalize_title,
    write_discovery,
    write_text_atomic,
)


USER_AGENT = "PaperAtlas/1.0 (local research library discovery)"
REMOVED_LIBRARY_DIR = ".paper-atlas-removed"


@dataclass
class ArchiveReceipt:
    destination: Path
    moved_from: Path | None = None
    created: bool = False
    replaced_backup: Path | None = None
    replaced_original: Path | None = None

    def rollback(self) -> None:
        if self.replaced_backup is not None and self.replaced_original is not None:
            self.destination.unlink(missing_ok=True)
            if self.replaced_backup.exists():
                self.replaced_backup.replace(self.replaced_original)
        elif self.moved_from is not None and self.destination.exists():
            self.moved_from.parent.mkdir(parents=True, exist_ok=True)
            self.destination.replace(self.moved_from)
        elif self.created:
            self.destination.unlink(missing_ok=True)

    def finalize(self) -> None:
        if self.replaced_backup is not None:
            self.replaced_backup.unlink(missing_ok=True)


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
        and REMOVED_LIBRARY_DIR not in path.relative_to(papers_dir).parts
    )


def is_standard_location(path: Path, papers_dir: Path) -> bool:
    return path.parent.parent == papers_dir and path.parent.name in build_graph.STANDARD_CATEGORIES


def arxiv_id_from_value(value: object) -> str | None:
    text = str(value or "")
    match = re.search(r"arxiv\.org/(?:abs|pdf)/([^?#/]+)", text, flags=re.IGNORECASE)
    if not match:
        match = re.fullmatch(r"(?:arxiv:)?(\d{4}\.\d{4,5})(?:v\d+)?", text, flags=re.IGNORECASE)
    if not match:
        return None
    return re.sub(r"v\d+$", "", match.group(1), flags=re.IGNORECASE)


def candidate_pdf_urls(candidate: dict) -> list[str]:
    """Collect direct and arXiv PDF alternatives already present in candidate metadata."""
    values: list[object] = [
        candidate.get("pdf_url"), candidate.get("url"), candidate.get("arxiv_id"),
    ]
    for version in candidate.get("versions") or []:
        if isinstance(version, dict):
            values.extend((version.get("pdf_url"), version.get("url"), version.get("arxiv_id")))
    urls: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and (text.lower().endswith(".pdf") or "/pdf/" in text.lower() or "doi/pdf" in text.lower()):
            urls.append(text)
        arxiv_id = arxiv_id_from_value(text)
        if arxiv_id:
            urls.append(f"https://arxiv.org/pdf/{arxiv_id}")
    return list(dict.fromkeys(urls))


def openalex_pdf_urls(candidate: dict) -> list[str]:
    """Resolve OA alternatives on demand when a publisher PDF rejects the request."""
    work_id = str(candidate.get("openalex_id") or "").strip().rsplit("/", 1)[-1]
    if not work_id:
        return []
    url = (
        f"https://api.openalex.org/works/{urllib.parse.quote(work_id)}"
        "?select=ids,best_oa_location,locations"
    )
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            work = json.load(response)
    except (OSError, ValueError, urllib.error.URLError):
        return []
    if not isinstance(work, dict):
        return []
    locations = [work.get("best_oa_location"), *(work.get("locations") or [])]
    values: list[object] = list((work.get("ids") or {}).values())
    for location in locations:
        if isinstance(location, dict):
            values.extend((location.get("pdf_url"), location.get("landing_page_url")))
    resolved: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and (text.lower().endswith(".pdf") or "/pdf/" in text.lower() or "doi/pdf" in text.lower()):
            resolved.append(text)
        arxiv_id = arxiv_id_from_value(text)
        if arxiv_id:
            resolved.append(f"https://arxiv.org/pdf/{arxiv_id}")
    return list(dict.fromkeys(resolved))


def arxiv_title_pdf_urls(candidate: dict) -> list[str]:
    """Find the preprint when publisher/OpenAlex metadata omits its arXiv identifier."""
    title = str(candidate.get("title") or "").strip()
    normalized = normalize_title(title)
    if len(normalized) < 12:
        return []
    query = urllib.parse.urlencode({
        "search_query": f'ti:"{title}"',
        "start": 0,
        "max_results": 5,
    })
    request = urllib.request.Request(
        f"https://export.arxiv.org/api/query?{query}", headers={"User-Agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            root = ET.parse(response).getroot()
    except (OSError, ET.ParseError, urllib.error.URLError):
        return []
    namespace = {"atom": "http://www.w3.org/2005/Atom"}
    matches: list[str] = []
    for entry in root.findall("atom:entry", namespace):
        entry_title = normalize_title(entry.findtext("atom:title", default="", namespaces=namespace))
        if not entry_title or not (
            entry_title == normalized
            or (len(entry_title) >= 24 and (entry_title in normalized or normalized in entry_title))
        ):
            continue
        for link in entry.findall("atom:link", namespace):
            href = str(link.attrib.get("href") or "")
            if link.attrib.get("title") == "pdf" or link.attrib.get("type") == "application/pdf":
                matches.append(href)
        identifier = arxiv_id_from_value(entry.findtext("atom:id", default="", namespaces=namespace))
        if identifier:
            matches.append(f"https://arxiv.org/pdf/{identifier}")
    return list(dict.fromkeys(filter(None, matches)))


def download_candidate_pdf(candidate: dict, destination: Path) -> str:
    urls = candidate_pdf_urls(candidate)
    if not urls and not candidate.get("openalex_id"):
        raise SystemExit("该候选没有可下载的 PDF，请从来源页人工获取")
    failures: list[str] = []
    tried: set[str] = set()
    resolvers = (
        lambda: urls,
        lambda: openalex_pdf_urls(candidate),
        lambda: arxiv_title_pdf_urls(candidate),
    )
    for resolver in resolvers:
        candidates = resolver()
        for url in candidates:
            if url in tried:
                continue
            tried.add(url)
            try:
                destination.unlink(missing_ok=True)
                request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(request, timeout=90) as response, destination.open("wb") as output:
                    shutil.copyfileobj(response, output)
                reader = PdfReader(destination)
                if not reader.pages:
                    raise ValueError("文件没有页面")
                return url
            except (OSError, ValueError, urllib.error.URLError, PdfReadError) as error:
                status = getattr(error, "code", None)
                failures.append(f"{urllib.parse.urlsplit(url).netloc or '来源'} {status or type(error).__name__}")
    detail = "、".join(dict.fromkeys(failures)) or "未找到开放 PDF 地址"
    raise SystemExit(f"PDF 下载失败：{detail}。可稍后重试或从来源页人工获取")


def archive_candidate(candidate: dict, category: str, papers_dir: Path) -> ArchiveReceipt:
    if category not in build_graph.STANDARD_CATEGORIES:
        raise SystemExit(f"未知类别：{category}")
    destination = papers_dir / category / safe_filename(candidate["title"])

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temporary:
        temporary_path = Path(temporary.name)
    try:
        download_candidate_pdf(candidate, temporary_path)
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


def replace_candidate(candidate: dict, replace_path: str, papers_dir: Path) -> ArchiveReceipt:
    """Replace one explicitly selected library PDF while preserving rollback data."""
    original = (papers_dir / replace_path).resolve()
    try:
        original.relative_to(papers_dir)
    except ValueError as error:
        raise SystemExit("被替换论文路径无效") from error
    if not original.is_file() or original.suffix.lower() != ".pdf":
        raise SystemExit("被替换的库内论文已不存在")
    destination = original.parent / safe_filename(candidate["title"])
    if destination != original and destination.exists():
        raise SystemExit("目标类别中已有同名论文，无法替换版本")
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temporary:
        downloaded = Path(temporary.name)
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as backup_file:
        backup = Path(backup_file.name)
    backup.unlink(missing_ok=True)
    completed = False
    try:
        download_candidate_pdf(candidate, downloaded)
        original.replace(backup)
        try:
            downloaded.replace(destination)
        except Exception:
            backup.replace(original)
            raise
        receipt = ArchiveReceipt(
            destination=destination,
            replaced_backup=backup,
            replaced_original=original,
        )
        completed = True
        return receipt
    finally:
        downloaded.unlink(missing_ok=True)
        if not completed:
            backup.unlink(missing_ok=True)


def purge_reference_evidence(candidate: dict, cache_path: Path) -> int:
    cache = load_json(cache_path, {"version": 3, "nodes": {}, "reference_index": {}})
    if not isinstance(cache, dict):
        return 0
    work_id = str(candidate.get("openalex_id") or "")
    title = normalize_title(str(candidate.get("title") or ""))
    arxiv_id = str(candidate.get("arxiv_id") or "")
    removed = 0
    reference_index = cache.get("reference_index") or {}
    for key, value in list(reference_index.items()):
        cached_title = normalize_title(str((value or {}).get("title") or "")) if isinstance(value, dict) else ""
        if (work_id and key == work_id) or (title and cached_title == title):
            reference_index.pop(key, None)
            removed += 1
    external_references = cache.get("external_references") or {}
    for key, value in list(external_references.items()):
        work = ((value or {}).get("work") or {}) if isinstance(value, dict) else {}
        cached_title = normalize_title(str(
            work.get("display_name") or (value or {}).get("title") or ""
        ))
        if (work_id and work.get("id") == work_id) or (title and cached_title == title):
            external_references.pop(key, None)
            removed += 1
    nodes = cache.get("nodes") or {}
    for key, value in list(nodes.items()):
        work = ((value or {}).get("work") or {}) if isinstance(value, dict) else {}
        ids = work.get("ids") or {}
        cached_arxiv = str(ids.get("arxiv") or "").rsplit("/", 1)[-1]
        cached_title = normalize_title(str(work.get("display_name") or (value or {}).get("title") or ""))
        if (
            (work_id and work.get("id") == work_id)
            or (arxiv_id and cached_arxiv.startswith(arxiv_id))
            or (title and cached_title == title)
        ):
            nodes.pop(key, None)
            removed += 1
    cache["reference_index"] = reference_index
    cache["external_references"] = external_references
    cache["nodes"] = nodes
    write_text_atomic(cache_path, json.dumps(cache, ensure_ascii=False, indent=2) + "\n")
    return removed


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
    replace_path: str | None = None,
) -> None:
    statuses = {
        "accept": "accepted", "dismiss": "dismissed", "reject": "rejected",
        "replace": "replaced", "purge": "purged",
    }
    decision = {"status": statuses[action], "decided_at": datetime.now(timezone.utc).isoformat()}
    if action in {"accept", "replace"}:
        if destination is None or papers_dir is None or not category:
            raise ValueError("归档决策缺少目标位置")
        candidate["status"] = statuses[action]
        candidate["accepted_path"] = str(destination.relative_to(papers_dir))
        candidate["graph_status"] = "pending"
        decision.update({
            "accepted_path": candidate["accepted_path"],
            "category": category,
            "graph_status": "pending",
        })
        if action == "replace" and replace_path:
            decision["superseded_path"] = replace_path
    else:
        candidate["status"] = statuses[action]
    decisions = data.setdefault("decisions", {})
    decisions[candidate["id"]] = decision
    decisions[candidate_key(candidate)] = decision


def apply_decision(data: dict, candidate_id: str, action: str, papers_dir: Path, category: str | None = None) -> dict:
    """Apply a reviewed candidate decision and return the updated candidate."""
    if action not in {"accept", "dismiss", "reject", "purge"}:
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
    replace_path: str | None = None,
    cache_path: Path | None = None,
) -> dict:
    """Archive and persist a review decision, rolling the file back if persistence fails."""
    if action not in {"accept", "dismiss", "reject", "replace", "purge"}:
        raise ValueError("未知审核操作")
    original = copy.deepcopy(data)
    candidate = find_candidate(data, candidate_id)
    receipt: ArchiveReceipt | None = None
    previous_cache = cache_path.read_bytes() if cache_path and cache_path.exists() else None
    try:
        if action in {"accept", "replace"}:
            if not category:
                raise ValueError("请选择论文类别")
            papers_dir = papers_dir.resolve()
            receipt = (
                replace_candidate(candidate, str(replace_path or ""), papers_dir)
                if action == "replace"
                else archive_candidate(candidate, category, papers_dir)
            )
            record_decision(
                data, candidate, action, category, receipt.destination, papers_dir, replace_path
            )
        else:
            record_decision(data, candidate, action)
        if action == "purge" and cache_path is not None:
            purge_reference_evidence(candidate, cache_path)
        write_discovery(data, discovery_json, discovery_js)
        if receipt is not None:
            receipt.finalize()
    except Exception:
        if receipt is not None:
            receipt.rollback()
        data.clear()
        data.update(original)
        if cache_path is not None:
            if previous_cache is None:
                cache_path.unlink(missing_ok=True)
            else:
                cache_path.write_bytes(previous_cache)
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
    alias = candidate_key(candidate)
    if alias != candidate_id:
        data["decisions"][alias] = decision
    write_discovery(data, discovery_json, discovery_js)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("accept", "dismiss", "reject", "purge"))
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
