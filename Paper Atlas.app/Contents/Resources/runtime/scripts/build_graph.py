#!/usr/bin/env python3
"""Build the local paper citation graph and timeline metadata for the web app."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import unicodedata
from collections import Counter
from pathlib import Path

from pypdf import PdfReader
from discovery_utils import write_text_atomic


logging.getLogger("pypdf").setLevel(logging.ERROR)

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PAPERS_DIR = REPO_ROOT.parent
DEFAULT_JSON = REPO_ROOT / "web" / "data" / "graph.json"
DEFAULT_JS = REPO_ROOT / "web" / "data" / "graph-data.js"

STANDARD_CATEGORIES = (
    "01_模型架构与训练优化",
    "02_注意力机制与长上下文",
    "03_MoE与稀疏模型",
    "04_量化与低精度计算",
    "05_分布式训练与数据基础设施",
    "06_GPU内核_编译器与性能工程",
    "07_GPU内核智能体与自动调优",
    "08_通用智能体与自主学习",
    "09_生成模型与视频系统",
    "10_大模型技术报告与推理训练",
)


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).lower()
    text = re.sub(r"([a-z])-\s+([a-z])", r"\1\2", text)
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def short_label(title: str, limit: int = 30) -> str:
    if len(title) <= limit:
        return title
    words = title.split()
    label = words[0]
    for word in words[1:]:
        if len(label) + len(word) + 1 > limit:
            break
        label += " " + word
    return label + "…"


def clean_inline(text: str) -> str:
    text = re.sub(r"([a-zA-Z])-\s+([a-zA-Z])", r"\1\2", text)
    return re.sub(r"\s+", " ", text).strip()


def extract_abstract(text: str, limit: int = 1800) -> str | None:
    match = re.search(
        r"(?:^|\n)\s*abstract\s*[:—–-]?\s*(.*?)"
        r"(?=\n\s*(?:\d+(?:\.\d+)*|[IVX]+)[\s.]+(?:introduction|background)\b"
        r"|\n\s*(?:keywords?|index terms)\s*[:—–-]|\Z)",
        text,
        re.I | re.S,
    )
    if not match:
        return None
    raw_abstract = re.split(
        r"\n\s*(?:[∗*†‡].{0,100}|\d+\s*\n\s*arxiv\s*:)",
        match.group(1),
        maxsplit=1,
        flags=re.I,
    )[0]
    abstract = clean_inline(raw_abstract)
    abstract = re.sub(r"(?<=[.!?])(?=[A-Z])", " ", abstract)
    if len(abstract) < 40:
        return None
    return abstract if len(abstract) <= limit else abstract[: limit - 1].rstrip() + "…"


def extract_authors(first_page: str, title: str, metadata: dict[str, object]) -> str | None:
    metadata_author = clean_inline(str(metadata.get("/Author") or ""))
    if metadata_author and metadata_author.lower() not in {"anonymous", "unknown", "liangchenyu03"}:
        return metadata_author if len(metadata_author) <= 600 else metadata_author[:599].rstrip(" ,;") + "…"

    blog_author = re.search(r"\|\s*([^|\n]+?)\s+blog\b", first_page, re.I)
    if blog_author:
        return clean_inline(blog_author.group(1))

    lines = [clean_inline(line) for line in first_page.splitlines() if clean_inline(line)]
    abstract_index = next(
        (index for index, line in enumerate(lines) if re.match(r"abstract\b", line, re.I)),
        min(len(lines), 40),
    )
    title_tokens = set(normalize(title).split())
    title_end = None
    best_title_score: tuple[float, int, int] | None = None
    for start in range(min(16, abstract_index)):
        for end in range(start + 1, min(start + 5, abstract_index) + 1):
            candidate_tokens = set(normalize(" ".join(lines[start:end])).split())
            if not candidate_tokens or not title_tokens:
                continue
            overlap = len(candidate_tokens & title_tokens) / len(title_tokens)
            extras = len(candidate_tokens - title_tokens)
            if overlap >= 0.72 and extras <= 3:
                score = (overlap, -extras, -len(candidate_tokens))
                if best_title_score is None or score > best_title_score:
                    best_title_score = score
                    title_end = end

    if title_end is None:
        return None

    affiliation_terms = re.compile(
        r"university|institute|laborator|department|school|college|research|"
        r"google|meta ai|nvidia|microsoft|deepmind|bytedance|alibaba|tencent|"
        r"amazon|siemens|huawei|github|https?://|www\.|@|facebook ai|"
        r"conference paper|arxiv|technical report|blog|germany|china|beijing|"
        r"shanghai|california|new york|carnegie mellon|technology|company|"
        r"national key|operational systems|neudesic|peking|imperial|berkeley|"
        r"january|february|march|april|may|june|"
        r"july|august|september|october|november|december",
        re.I,
    )
    prose_terms = re.compile(
        r"\b(?:the|this|that|we|our|is|are|was|were|has|have|using|based|"
        r"paper|figure|model|method|training|inference|workloads?)\b",
        re.I,
    )
    author_lines: list[str] = []
    for line in lines[title_end:abstract_index]:
        if line.strip().lower() == "deepseek-ai":
            author_lines.append("DeepSeek-AI")
            break
        collaboration = re.match(r"(.+?)\s+in collaboration\b", line, re.I)
        if collaboration:
            author_lines.append(clean_inline(collaboration.group(1)))
            continue
        stripped = affiliation_terms.split(line, maxsplit=1)[0]
        stripped = re.sub(r"[∗*†‡\d]+", "", stripped).strip(" ,;|")
        words = stripped.split()
        if not stripped or len(words) > 20 or prose_terms.search(stripped):
            continue
        if not re.search(r"[A-Za-zÀ-ž]", stripped):
            continue
        name_like = sum(bool(re.match(r"^[A-ZÀ-Þ][A-Za-zÀ-ž'.-]*$", word.strip(",;&()"))) for word in words)
        if name_like < 2 or name_like / len(words) < 0.55:
            continue
        author_lines.append(stripped)
        if len(author_lines) == 5:
            break

    authors = ", ".join(author_lines)
    if len(authors) > 600:
        authors = authors[:599].rstrip(" ,;") + "…"
    return authors or None


def extract_year(text: str, metadata: dict[str, object]) -> int | None:
    arxiv = re.search(r"arxiv\s*:\s*(\d{2})\d{2}\.\d+", text, re.I)
    if arxiv:
        yy = int(arxiv.group(1))
        return 2000 + yy if yy < 90 else 1900 + yy

    patterns = (
        r"published as a conference paper at\s+[^\n]{0,60}?(20\d{2})",
        r"(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+(?:\d{1,2},?\s+)?(20\d{2})",
        r"(?:copyright|©)\s*(20\d{2})",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return int(match.group(1))

    years = [int(year) for year in re.findall(r"\b(20(?:1[0-9]|2[0-9]))\b", text[:8000])]
    if years:
        return Counter(years).most_common(1)[0][0]

    metadata_text = " ".join(str(value) for value in metadata.values())
    match = re.search(r"D:(20\d{2})", metadata_text)
    return int(match.group(1)) if match else None


def reference_section(text: str) -> str:
    lowered = text.lower()
    start = max(lowered.rfind("\nreferences"), lowered.rfind("\nbibliography"))
    if start >= len(text) * 0.45:
        return text[start:]
    return text[int(len(text) * 0.65) :]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def discover_pdfs(papers_dir: Path) -> list[Path]:
    return sorted(
        path
        for category in STANDARD_CATEGORIES
        for path in (papers_dir / category).glob("*.pdf")
    )


def extract_nodes(papers_dir: Path) -> tuple[list[dict], dict[str, str], list[dict]]:
    nodes: list[dict] = []
    full_text: dict[str, str] = {}
    duplicates: list[dict] = []
    hashes: dict[str, str] = {}

    for path in discover_pdfs(papers_dir):
        digest = sha256(path)
        relative_path = str(path.relative_to(papers_dir))
        if digest in hashes:
            duplicates.append({"path": relative_path, "duplicate_of": hashes[digest], "sha256": digest})
            continue

        reader = PdfReader(path)
        pages = [(page.extract_text() or "") for page in reader.pages]
        text = "\n".join(pages)
        metadata = dict(reader.metadata or {})
        title = path.stem.replace(" (重复副本)", "")
        node_id = f"p{len(nodes):02d}"
        node = {
            "id": node_id,
            "title": title,
            "label": short_label(title),
            "year": extract_year("\n".join(pages[:2]), metadata),
            "authors": extract_authors(pages[0] if pages else "", title, metadata),
            "abstract": extract_abstract("\n".join(pages[:3])),
            "category": path.parent.name,
            "path": relative_path,
            "sha256": digest,
        }
        nodes.append(node)
        full_text[node_id] = text
        hashes[digest] = relative_path

    return nodes, full_text, duplicates


def build_citation_edges(nodes: list[dict], full_text: dict[str, str]) -> list[dict]:
    edges: dict[tuple[str, str], dict] = {}
    for source in nodes:
        references = normalize(reference_section(full_text[source["id"]]))
        for target in nodes:
            if source["id"] == target["id"]:
                continue
            if source["year"] and target["year"] and source["year"] < target["year"]:
                continue

            title = normalize(target["title"])
            title_tokens = title.split()
            probes = [(title, "high")]
            if len(title_tokens) > 10:
                probes.append((" ".join(title_tokens[:10]), "medium"))
            if len(title_tokens) > 6:
                probes.append((" ".join(title_tokens[:7]), "medium"))
            match = next(
                ((probe, confidence) for probe, confidence in probes if len(probe) >= 24 and probe in references),
                None,
            )
            if match:
                probe, confidence = match
                edges[(source["id"], target["id"])] = {
                    "source": source["id"],
                    "target": target["id"],
                    "confidence": confidence,
                    "evidence": "完整标题匹配" if confidence == "high" else f"参考文献标题片段匹配：{probe}",
                }

    return [edges[key] for key in sorted(edges)]


def citation_counts(nodes: list[dict], citation_edges: list[dict]) -> dict[str, int]:
    counts = {node["id"]: 0 for node in nodes}
    for edge in citation_edges:
        counts[edge["target"]] += 1
    return counts


def choose_main_nodes(nodes: list[dict], counts: dict[str, int]) -> dict[str, str]:
    main_nodes: dict[str, str] = {}
    categories = sorted({node["category"] for node in nodes})
    for category in categories:
        candidates = [node for node in nodes if node["category"] == category]
        winner = max(
            candidates,
            key=lambda node: (
                counts[node["id"]],
                -(node["year"] or 9999),
                node["title"],
            ),
        )
        main_nodes[category] = winner["id"]
    return main_nodes


def build_graph(papers_dir: Path) -> dict:
    nodes, full_text, duplicates = extract_nodes(papers_dir)
    if not nodes:
        raise RuntimeError(f"No categorized PDFs found below {papers_dir}")

    citation_edges = build_citation_edges(nodes, full_text)
    counts = citation_counts(nodes, citation_edges)
    main_nodes = choose_main_nodes(nodes, counts)

    for node in nodes:
        node["citation_count"] = counts[node["id"]]
        node["is_main"] = main_nodes[node["category"]] == node["id"]

    categories = []
    for category in sorted(main_nodes):
        categories.append(
            {
                "id": category,
                "label": re.sub(r"^\d+_", "", category),
                "main_node": main_nodes[category],
                "paper_count": sum(node["category"] == category for node in nodes),
            }
        )

    years = [node["year"] for node in nodes if node["year"]]
    return {
        "metadata": {
            "paper_files": len(nodes) + len(duplicates),
            "unique_papers": len(nodes),
            "duplicate_files": len(duplicates),
            "citation_edges": len(citation_edges),
            "year_min": min(years) if years else None,
            "year_max": max(years) if years else None,
            "citation_direction": "citing_paper -> cited_paper",
            "time_encoding": "horizontal_timeline: older -> newer",
        },
        "categories": categories,
        "nodes": nodes,
        "edges": {"citation": citation_edges},
        "duplicates": duplicates,
    }


def write_graph(graph: dict, json_path: Path, js_path: Path) -> None:
    pretty = json.dumps(graph, ensure_ascii=False, indent=2)
    compact = json.dumps(graph, ensure_ascii=False, separators=(",", ":"))
    previous_json = json_path.read_bytes() if json_path.exists() else None
    previous_js = js_path.read_bytes() if js_path.exists() else None
    try:
        write_text_atomic(json_path, pretty + "\n")
        write_text_atomic(js_path, "window.PAPER_GRAPH=" + compact + ";\n")
    except Exception:
        if previous_json is None:
            json_path.unlink(missing_ok=True)
        else:
            json_path.write_bytes(previous_json)
        if previous_js is None:
            js_path.unlink(missing_ok=True)
        else:
            js_path.write_bytes(previous_js)
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--papers-dir", type=Path, default=DEFAULT_PAPERS_DIR)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--output-js", type=Path, default=DEFAULT_JS)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    papers_dir = args.papers_dir.expanduser().resolve()
    graph = build_graph(papers_dir)
    write_graph(graph, args.output_json, args.output_js)
    metadata = graph["metadata"]
    print(
        f"Built {metadata['unique_papers']} unique papers, "
        f"{metadata['citation_edges']} citation edges"
    )
    for category in graph["categories"]:
        node = next(node for node in graph["nodes"] if node["id"] == category["main_node"])
        print(f"MAIN\t{category['label']}\t{node['citation_count']}\t{node['title']}")


if __name__ == "__main__":
    main()
