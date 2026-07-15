#!/usr/bin/env python3
"""Build the local paper citation/time graph used by the static web app."""

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


logging.getLogger("pypdf").setLevel(logging.ERROR)

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PAPERS_DIR = REPO_ROOT.parent
DEFAULT_JSON = REPO_ROOT / "web" / "data" / "graph.json"
DEFAULT_JS = REPO_ROOT / "web" / "data" / "graph-data.js"


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
        for path in papers_dir.glob("*/*.pdf")
        if re.match(r"^\d+_", path.parent.name)
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
        title = path.stem.replace(" (重复副本)", "")
        node_id = f"p{len(nodes):02d}"
        node = {
            "id": node_id,
            "title": title,
            "label": short_label(title),
            "year": extract_year("\n".join(pages[:2]), dict(reader.metadata or {})),
            "category": path.parent.name,
            "path": relative_path,
            "sha256": digest,
        }
        nodes.append(node)
        full_text[node_id] = text
        hashes[digest] = relative_path

    return nodes, full_text, duplicates


def build_citation_edges(nodes: list[dict], full_text: dict[str, str]) -> list[dict]:
    edges: set[tuple[str, str]] = set()
    for source in nodes:
        references = normalize(reference_section(full_text[source["id"]]))
        for target in nodes:
            if source["id"] == target["id"]:
                continue
            if source["year"] and target["year"] and source["year"] < target["year"]:
                continue

            title = normalize(target["title"])
            title_tokens = title.split()
            probes = [title]
            if len(title_tokens) > 10:
                probes.append(" ".join(title_tokens[:10]))
            if len(title_tokens) > 6:
                probes.append(" ".join(title_tokens[:7]))
            if any(len(probe) >= 24 and probe in references for probe in probes):
                edges.add((source["id"], target["id"]))

    return [{"source": source, "target": target} for source, target in sorted(edges)]


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


def build_time_edges(nodes: list[dict], counts: dict[str, int]) -> list[dict]:
    """Connect each paper from the strongest earlier paper in its category."""
    edges: list[dict] = []
    categories = sorted({node["category"] for node in nodes})
    for category in categories:
        group = [node for node in nodes if node["category"] == category and node["year"]]
        group.sort(key=lambda node: (node["year"], node["title"]))
        for node in group:
            earlier = [candidate for candidate in group if candidate["year"] < node["year"]]
            if not earlier:
                continue
            predecessor = max(
                earlier,
                key=lambda candidate: (
                    counts[candidate["id"]],
                    candidate["year"],
                    candidate["title"],
                ),
            )
            edges.append({"source": predecessor["id"], "target": node["id"]})
    return edges


def build_graph(papers_dir: Path) -> dict:
    nodes, full_text, duplicates = extract_nodes(papers_dir)
    if not nodes:
        raise RuntimeError(f"No categorized PDFs found below {papers_dir}")

    citation_edges = build_citation_edges(nodes, full_text)
    counts = citation_counts(nodes, citation_edges)
    main_nodes = choose_main_nodes(nodes, counts)
    time_edges = build_time_edges(nodes, counts)

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
            "time_edges": len(time_edges),
            "year_min": min(years) if years else None,
            "year_max": max(years) if years else None,
            "citation_direction": "citing_paper -> cited_paper",
            "time_direction": "older_paper -> newer_paper",
        },
        "categories": categories,
        "nodes": nodes,
        "edges": {"citation": citation_edges, "time": time_edges},
        "duplicates": duplicates,
    }


def write_graph(graph: dict, json_path: Path, js_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    js_path.parent.mkdir(parents=True, exist_ok=True)
    pretty = json.dumps(graph, ensure_ascii=False, indent=2)
    compact = json.dumps(graph, ensure_ascii=False, separators=(",", ":"))
    json_path.write_text(pretty + "\n", encoding="utf-8")
    js_path.write_text("window.PAPER_GRAPH=" + compact + ";\n", encoding="utf-8")


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
        f"{metadata['citation_edges']} citation edges, "
        f"{metadata['time_edges']} time edges"
    )
    for category in graph["categories"]:
        node = next(node for node in graph["nodes"] if node["id"] == category["main_node"])
        print(f"MAIN\t{category['label']}\t{node['citation_count']}\t{node['title']}")


if __name__ == "__main__":
    main()
