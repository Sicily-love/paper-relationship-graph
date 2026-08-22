#!/usr/bin/env python3
"""Serve the graph UI, local PDFs, and a localhost-only review API."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import threading
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

import build_graph
import discover_papers
import manage_candidate
from discovery_utils import DEFAULT_CONFIG, DEFAULT_DISCOVERY_JS, DEFAULT_DISCOVERY_JSON, load_json, write_discovery


REPO_ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = REPO_ROOT / "web"
MAX_BODY_BYTES = 1024 * 1024
MUTATION_LOCK = threading.Lock()


def topic_id(label: str, index: int) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
    return value[:48] or f"topic-{index + 1}"


def validate_topics(raw_topics: object) -> list[dict]:
    if not isinstance(raw_topics, list) or len(raw_topics) > 20:
        raise ValueError("搜索主题必须是列表，且最多 20 个")
    topics: list[dict] = []
    seen_ids: set[str] = set()
    for index, raw in enumerate(raw_topics):
        if not isinstance(raw, dict):
            raise ValueError("搜索主题格式无效")
        label = str(raw.get("label") or "").strip()
        if not 1 <= len(label) <= 80:
            raise ValueError("每个主题都需要一个不超过 80 字的名称")
        keywords = [str(item).strip() for item in raw.get("keywords", []) if str(item).strip()]
        excluded = [str(item).strip() for item in raw.get("exclude_keywords", []) if str(item).strip()]
        if not 1 <= len(keywords) <= 12 or any(len(item) > 80 for item in keywords):
            raise ValueError(f"“{label}”需要 1–12 个关键词，每个不超过 80 字")
        if len(excluded) > 12 or any(len(item) > 80 for item in excluded):
            raise ValueError(f"“{label}”的排除词最多 12 个，每个不超过 80 字")
        identifier = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(raw.get("id") or "")).strip("-")[:64]
        identifier = identifier or topic_id(label, index)
        base = identifier
        suffix = 2
        while identifier in seen_ids:
            identifier = f"{base}-{suffix}"
            suffix += 1
        seen_ids.add(identifier)
        try:
            maximum = int(raw.get("max_results", 10))
        except (TypeError, ValueError) as error:
            raise ValueError(f"“{label}”的每日数量无效") from error
        if not 1 <= maximum <= 50:
            raise ValueError(f"“{label}”的每日数量需要在 1–50 之间")
        topics.append({
            "id": identifier,
            "label": label,
            "keywords": keywords,
            "exclude_keywords": excluded,
            "enabled": bool(raw.get("enabled", True)),
            "max_results": maximum,
        })
    return topics


def write_json_atomic(path: Path, data: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def validate_shared_reference_minimum(value: object) -> int:
    try:
        minimum = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError("共同引用次数下限必须是整数") from error
    if not 2 <= minimum <= 20:
        raise ValueError("共同引用次数下限需要在 2–20 之间")
    return minimum


def discovery_mode(value: object) -> str:
    mode = str(value or "arxiv")
    if mode not in {"arxiv", "shared"}:
        raise ValueError("未知的论文发现方式")
    return mode


def clear_new_candidates(data: dict) -> int:
    candidates = data.get("candidates", [])
    retained = [candidate for candidate in candidates if candidate.get("status") != "new"]
    removed = len(candidates) - len(retained)
    data["candidates"] = retained
    metadata = data.setdefault("metadata", {})
    metadata.update({
        "candidate_count": len(retained),
        "new_count": 0,
        "shared_reference_count": sum(
            "shared_reference" in candidate.get("sources", []) for candidate in retained
        ),
        "arxiv_topic_count": sum("arxiv_topic" in candidate.get("sources", []) for candidate in retained),
        "cleared_at": datetime.now(timezone.utc).isoformat(),
    })
    return removed


def validated_discovery() -> dict:
    data = load_json(DEFAULT_DISCOVERY_JSON, {"metadata": {}, "candidates": []})
    for candidate in data.get("candidates", []):
        candidate.update(discover_papers.candidate_validation(candidate))
    return data


class GraphRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, papers_dir: Path, **kwargs):
        self.papers_dir = papers_dir.resolve()
        super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

    def translate_path(self, path: str) -> str:
        url_path = unquote(urlsplit(path).path)
        if url_path.startswith("/papers/"):
            relative = Path(url_path.removeprefix("/papers/"))
            candidate = (self.papers_dir / relative).resolve()
            try:
                candidate.relative_to(self.papers_dir)
            except ValueError:
                return str(self.papers_dir / "__not_found__")
            if candidate.suffix.lower() != ".pdf":
                return str(self.papers_dir / "__not_found__")
            return str(candidate)
        return super().translate_path(path)

    def api_allowed(self) -> bool:
        host = self.headers.get("Host", "").split(":", 1)[0]
        origin = self.headers.get("Origin")
        if host not in {"127.0.0.1", "localhost", "[::1]"}:
            return False
        if origin and urlsplit(origin).hostname not in {"127.0.0.1", "localhost", "::1"}:
            return False
        return True

    def send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def read_json(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise ValueError("请求大小无效") from error
        if length < 1 or length > MAX_BODY_BYTES:
            raise ValueError("请求内容为空或过大")
        try:
            value = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("请求内容不是有效 JSON") from error
        if not isinstance(value, dict):
            raise ValueError("请求内容格式无效")
        return value

    def state(self) -> dict:
        config = load_json(DEFAULT_CONFIG, {})
        return {
            "discovery": validated_discovery(),
            "topics": config.get("topics", []),
            "shared_reference_minimum": int(
                config.get("shared_references", {}).get("min_library_citations", 2)
            ),
            "categories": [
                {"id": identifier, "label": re.sub(r"^\d+_", "", identifier)}
                for identifier in build_graph.STANDARD_CATEGORIES
            ],
        }

    def do_GET(self) -> None:
        if urlsplit(self.path).path == "/api/state":
            if not self.api_allowed():
                self.send_json(403, {"error": "本地管理接口仅允许从当前页面访问"})
                return
            self.send_json(200, self.state())
            return
        super().do_GET()

    def do_PUT(self) -> None:
        if urlsplit(self.path).path != "/api/topics":
            self.send_json(404, {"error": "接口不存在"})
            return
        self.handle_api(self.save_topics)

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        if path == "/api/candidates/action":
            self.handle_api(self.review_candidate)
        elif path == "/api/candidates/clear":
            self.handle_api(self.clear_candidates)
        elif path == "/api/discover":
            self.handle_api(self.run_discovery)
        else:
            self.send_json(404, {"error": "接口不存在"})

    def handle_api(self, action) -> None:
        if not self.api_allowed():
            self.send_json(403, {"error": "本地管理接口仅允许从当前页面访问"})
            return
        try:
            with MUTATION_LOCK:
                payload = action(self.read_json())
            self.send_json(200, payload)
        except (ValueError, SystemExit) as error:
            self.send_json(400, {"error": str(error)})
        except subprocess.TimeoutExpired:
            self.send_json(504, {"error": "任务运行超时，请稍后重试"})
        except Exception as error:  # pragma: no cover
            self.log_error("API error: %s", error)
            self.send_json(500, {"error": "本地任务运行失败，请查看终端提示"})

    def save_topics(self, body: dict) -> dict:
        topics = validate_topics(body.get("topics"))
        config = load_json(DEFAULT_CONFIG, {})
        config["topics"] = topics
        write_json_atomic(DEFAULT_CONFIG, config)
        return {"message": "搜索主题已保存", "topics": topics}

    def review_candidate(self, body: dict) -> dict:
        action = str(body.get("action") or "")
        candidate_id = str(body.get("id") or "")
        category = str(body.get("category") or "") or None
        data = load_json(DEFAULT_DISCOVERY_JSON, {"metadata": {}, "candidates": []})
        candidate = manage_candidate.apply_decision(data, candidate_id, action, self.papers_dir, category)
        write_discovery(data, DEFAULT_DISCOVERY_JSON, DEFAULT_DISCOVERY_JS)
        if action == "accept":
            try:
                result = subprocess.run(
                    [
                        sys.executable,
                        str(REPO_ROOT / "scripts" / "update_library.py"),
                        "--papers-dir",
                        str(self.papers_dir),
                        "--allow-unclassified",
                    ],
                    cwd=REPO_ROOT,
                    capture_output=True,
                    text=True,
                    timeout=360,
                    check=False,
                )
                graph_updated = result.returncode == 0
            except (subprocess.TimeoutExpired, OSError):
                graph_updated = False
        else:
            graph_updated = None
        return {
            "message": (
                "已加入论文库并更新图谱"
                if action == "accept" and graph_updated
                else "论文已归档；图谱将在下次整理时更新"
                if action == "accept"
                else "已忽略该候选"
            ),
            "graph_updated": graph_updated,
            "candidate": candidate,
            "discovery": validated_discovery(),
        }

    def clear_candidates(self, _body: dict) -> dict:
        data = load_json(DEFAULT_DISCOVERY_JSON, {"metadata": {}, "candidates": []})
        removed = clear_new_candidates(data)
        write_discovery(data, DEFAULT_DISCOVERY_JSON, DEFAULT_DISCOVERY_JS)
        return {
            "message": f"已清空 {removed} 篇待审核候选",
            "removed_count": removed,
            "discovery": validated_discovery(),
        }

    def run_discovery(self, body: dict) -> dict:
        mode = discovery_mode(body.get("mode"))
        arguments = [sys.executable, str(REPO_ROOT / "scripts" / "discover_papers.py")]
        if mode == "arxiv":
            arguments.append("--skip-shared")
        else:
            config = load_json(DEFAULT_CONFIG, {})
            minimum = validate_shared_reference_minimum(body.get("min_library_citations", 2))
            config.setdefault("shared_references", {})["min_library_citations"] = minimum
            write_json_atomic(DEFAULT_CONFIG, config)
            arguments.append("--skip-arxiv")
        result = subprocess.run(
            arguments,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=360,
            check=False,
        )
        if result.returncode:
            message = (result.stderr or result.stdout or "论文发现失败").strip().splitlines()[-1]
            raise ValueError(message)
        return {
            "message": "arXiv 搜索已完成" if mode == "arxiv" else "共同引用计算已完成",
            "mode": mode,
            "discovery": validated_discovery(),
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--papers-dir", type=Path, default=REPO_ROOT.parent)
    parser.add_argument("--port", type=int, default=8000)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    papers_dir = args.papers_dir.expanduser().resolve()
    handler = partial(GraphRequestHandler, papers_dir=papers_dir)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    print(f"Paper graph: http://127.0.0.1:{args.port}")
    print(f"PDF root: {papers_dir}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
