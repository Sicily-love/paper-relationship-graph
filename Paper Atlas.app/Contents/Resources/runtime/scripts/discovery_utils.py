"""Shared helpers for paper discovery and recommendation management."""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO_ROOT / "config" / "discovery.json"
DEFAULT_GRAPH = REPO_ROOT / "web" / "data" / "graph.json"
DEFAULT_DISCOVERY_JSON = REPO_ROOT / "web" / "data" / "discovery.json"
DEFAULT_DISCOVERY_JS = REPO_ROOT / "web" / "data" / "discovery-data.js"


def normalize_title(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).lower()
    return re.sub(r"\s+", " ", "".join(character if character.isalnum() else " " for character in text)).strip()


def compact_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def load_json(path: Path, default: object) -> object:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_text_atomic(path: Path, text: str) -> None:
    """Replace a UTF-8 text file without exposing a partially written value."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def write_discovery(data: dict, json_path: Path, js_path: Path) -> None:
    """Commit the JSON and browser payload as one recoverable pair."""
    pretty = json.dumps(data, ensure_ascii=False, indent=2)
    compact = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    json_text = pretty + "\n"
    js_text = "window.PAPER_DISCOVERY=" + compact + ";\n"
    previous_json = json_path.read_bytes() if json_path.exists() else None
    previous_js = js_path.read_bytes() if js_path.exists() else None
    try:
        write_text_atomic(json_path, json_text)
        write_text_atomic(js_path, js_text)
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


def candidate_key(candidate: dict) -> str:
    arxiv_id = candidate.get("arxiv_id")
    if arxiv_id:
        return f"arxiv:{arxiv_id}"
    openalex_id = str(candidate.get("openalex_id") or "").rsplit("/", 1)[-1]
    if openalex_id:
        return f"openalex:{openalex_id}"
    return "title:" + normalize_title(str(candidate.get("title") or ""))
