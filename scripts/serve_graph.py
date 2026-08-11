#!/usr/bin/env python3
"""Serve the graph UI and local PDFs from separate, safe URL roots."""

from __future__ import annotations

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit


REPO_ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = REPO_ROOT / "web"


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
