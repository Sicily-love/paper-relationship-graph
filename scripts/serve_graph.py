#!/usr/bin/env python3
"""Serve Paper Atlas through a localhost-only HTTP transport."""

from __future__ import annotations

import argparse
import json
import subprocess
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from app_services import (
    AppServices,
    clear_new_candidates,
    discovery_mode,
    validate_highly_cited_minimum,
    validate_shared_reference_minimum,
    validate_topics,
    validated_discovery,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = REPO_ROOT / "web"
MAX_BODY_BYTES = 1024 * 1024
MUTATION_LOCK = threading.Lock()


class GraphRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, papers_dir: Path, **kwargs):
        self.papers_dir = papers_dir.resolve()
        self.services = AppServices(self.papers_dir)
        super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

    def translate_path(self, path: str) -> str:
        url_path = unquote(urlsplit(path).path)
        if not url_path.startswith("/papers/"):
            return super().translate_path(path)
        relative = Path(url_path.removeprefix("/papers/"))
        candidate = (self.papers_dir / relative).resolve()
        try:
            candidate.relative_to(self.papers_dir)
        except ValueError:
            return str(self.papers_dir / "__not_found__")
        if candidate.suffix.lower() != ".pdf":
            return str(self.papers_dir / "__not_found__")
        return str(candidate)

    def api_allowed(self) -> bool:
        host = self.headers.get("Host", "").split(":", 1)[0]
        origin = self.headers.get("Origin")
        return (
            host in {"127.0.0.1", "localhost", "[::1]"}
            and (not origin or urlsplit(origin).hostname in {"127.0.0.1", "localhost", "::1"})
        )

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
        if not 1 <= length <= MAX_BODY_BYTES:
            raise ValueError("请求内容为空或过大")
        try:
            value = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("请求内容不是有效 JSON") from error
        if not isinstance(value, dict):
            raise ValueError("请求内容格式无效")
        return value

    def do_GET(self) -> None:
        if urlsplit(self.path).path != "/api/state":
            super().do_GET()
            return
        if not self.api_allowed():
            self.send_json(403, {"error": "本地管理接口仅允许从当前页面访问"})
            return
        self.send_json(200, self.services.state())

    def do_PUT(self) -> None:
        if urlsplit(self.path).path != "/api/topics":
            self.send_json(404, {"error": "接口不存在"})
            return
        self.handle_api(self.services.save_topics)

    def do_POST(self) -> None:
        actions = {
            "/api/candidates/action": self.services.review_candidate,
            "/api/candidates/feedback": self.services.candidate_feedback,
            "/api/classification/action": self.services.review_classification,
            "/api/candidates/clear": self.services.clear_candidates,
            "/api/discover": self.services.run_discovery,
            "/api/maintenance/rebuild": self.services.run_maintenance,
            "/api/diagnostics": self.services.run_diagnostics,
            "/api/tasks": self.services.manage_tasks,
            "/api/backup": self.services.manage_backup,
            "/api/logs": self.services.runtime_logs,
            "/api/graph/node/remove": self.services.remove_graph_node,
        }
        action = actions.get(urlsplit(self.path).path)
        if action is None:
            self.send_json(404, {"error": "接口不存在"})
            return
        self.handle_api(action)

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
