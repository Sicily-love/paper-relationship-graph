#!/usr/bin/env python3
"""Serve Paper Atlas through a localhost-only HTTP transport."""

from __future__ import annotations

import argparse
import json
import threading
import secrets
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from api_contract import ApiRequest
from api_controller import ApiController
from app_services import (
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


class GraphRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, papers_dir: Path, **kwargs):
        self.papers_dir = papers_dir.resolve()
        server = args[-1] if args else None
        self.controller = getattr(server, "controller", None) or ApiController(self.papers_dir)
        self.services = self.controller.services
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
        api_token = getattr(self.server, "api_token", "")
        token = self.headers.get("X-Paper-Atlas-Token", "")
        token_ok = not api_token or secrets.compare_digest(token, api_token)
        return token_ok and (
            host in {"127.0.0.1", "localhost", "[::1]"}
            and (not origin or urlsplit(origin).hostname in {"127.0.0.1", "localhost", "::1"})
        )

    def serve_index(self) -> None:
        path = WEB_ROOT / "index.html"
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            self.send_error(404)
            return
        api_token = getattr(self.server, "api_token", "")
        if api_token:
            content = content.replace("</head>", f'<meta name="paper-atlas-token" content="{api_token}"></head>', 1)
        body = content.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

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
        if length == 0:
            return {}
        if length > MAX_BODY_BYTES:
            raise ValueError("请求内容过大")
        try:
            value = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("请求内容不是有效 JSON") from error
        if not isinstance(value, dict):
            raise ValueError("请求内容格式无效")
        return value

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/":
            self.serve_index()
            return
        if not path.startswith("/api/"):
            super().do_GET()
            return
        if not self.api_allowed():
            self.send_json(403, {"error": "本地管理接口令牌无效或来源不受信任"})
            return
        self.handle_controller("GET")

    def do_PUT(self) -> None:
        self.handle_controller("PUT")

    def do_POST(self) -> None:
        self.handle_controller("POST")

    def do_DELETE(self) -> None:
        self.handle_controller("DELETE")

    def handle_controller(self, method: str) -> None:
        if not self.api_allowed():
            self.send_json(403, {"error": "本地管理接口令牌无效或来源不受信任"})
            return
        if method in {"POST", "PUT", "DELETE"} and self.headers.get("Content-Length") and "application/json" not in self.headers.get("Content-Type", ""):
            self.send_json(415, {"error": "请求必须使用 application/json"})
            return
        url = urlsplit(self.path)
        body = {}
        if method in {"POST", "PUT"} or (method == "DELETE" and self.headers.get("Content-Length")):
            try:
                body = self.read_json()
            except ValueError as error:
                self.send_json(422, {"error": str(error)})
                return
        query = {key: values[-1] for key, values in __import__("urllib.parse", fromlist=["parse_qs"]).parse_qs(url.query).items() if values}
        request = ApiRequest(method=method, path=url.path, body=body,
                             headers={key: value for key, value in self.headers.items()}, query=query)
        try:
            status, payload = self.controller.handle(request)
            self.send_json(status, payload)
        except Exception as error:  # pragma: no cover
            self.log_error("API error: %s", error)
            self.send_json(500, {"error": "本地任务运行失败，请查看运行日志"})

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
    server.api_token = secrets.token_urlsafe(24)
    server.controller = ApiController(papers_dir)
    print(f"Paper graph: http://127.0.0.1:{args.port}")
    print(f"PDF root: {papers_dir}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        server.controller.jobs.close()


if __name__ == "__main__":
    main()
