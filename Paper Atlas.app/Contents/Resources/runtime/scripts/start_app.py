#!/usr/bin/env python3
"""One-step launcher for Paper Atlas; no manual build command is required."""

from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import threading
import venv
import webbrowser
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PAPERS_DIR = REPO_ROOT.parent
RUNTIME_DIR = REPO_ROOT / ".cache"
RUNTIME_URL = RUNTIME_DIR / "paper-atlas-url"
RUNTIME_PID = RUNTIME_DIR / "paper-atlas-server.pid"


def runtime_python() -> Path:
    if sys.platform == "win32":
        return REPO_ROOT / ".venv" / "Scripts" / "python.exe"
    return REPO_ROOT / ".venv" / "bin" / "python"


def ensure_runtime() -> Path:
    python = runtime_python()
    if not python.exists():
        print("首次启动：正在准备本地运行环境…")
        venv.EnvBuilder(with_pip=True).create(REPO_ROOT / ".venv")
    available = subprocess.run(
        [str(python), "-c", "import pypdf"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if available.returncode:
        print("首次启动：正在安装 PDF 读取组件…")
        subprocess.run(
            [str(python), "-m", "pip", "install", "-r", str(REPO_ROOT / "requirements.txt")],
            cwd=REPO_ROOT,
            check=True,
        )
    return python


def library_files(papers_dir: Path) -> list[Path]:
    files = []
    for path in papers_dir.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".pdf", ".pptx"}:
            continue
        if REPO_ROOT == path or REPO_ROOT in path.parents:
            continue
        files.append(path)
    return files


def refresh_graph_if_needed(python: Path, papers_dir: Path) -> None:
    sources = library_files(papers_dir)
    graph_path = REPO_ROOT / "web" / "data" / "graph.json"
    if not sources:
        return
    needs_refresh = not graph_path.exists() or max(path.stat().st_mtime for path in sources) > graph_path.stat().st_mtime
    if not needs_refresh:
        return
    print("检测到论文库变化，正在自动更新图谱…")
    result = subprocess.run(
        [str(python), str(REPO_ROOT / "scripts" / "update_library.py"), "--papers-dir", str(papers_dir)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        unclassified = [
            line.removeprefix("UNCLASSIFIED\t")
            for line in result.stdout.splitlines()
            if line.startswith("UNCLASSIFIED\t")
        ]
        if unclassified:
            print(f"发现 {len(unclassified)} 篇待分类论文，暂时使用上一次图谱：")
            for path in unclassified:
                print(f"  · {path}")
            print("每日分类任务处理后，下次启动会自动更新，无需手动构建。")
        else:
            print("自动更新未完成，暂时使用上一次生成的图谱。")
    elif result.stdout.strip():
        print(result.stdout.strip())


def available_port(preferred: int) -> int:
    for port in range(preferred, preferred + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                continue
        return port
    raise SystemExit("没有找到可用的本地端口，请关闭其他本地服务后重试")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--papers-dir", type=Path, default=DEFAULT_PAPERS_DIR)
    parser.add_argument("--port", type=int, default=int(os.environ.get("PAPER_ATLAS_PORT", "8000")))
    parser.add_argument("--no-browser", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    papers_dir = args.papers_dir.expanduser().resolve()
    python = ensure_runtime()
    refresh_graph_if_needed(python, papers_dir)
    port = available_port(args.port)
    url = f"http://127.0.0.1:{port}"
    print(f"Paper Atlas 已启动：{url}")
    print("退出 Paper Atlas 应用即可停止服务。")
    process = subprocess.Popen(
        [
            str(python),
            str(REPO_ROOT / "scripts" / "serve_graph.py"),
            "--papers-dir",
            str(papers_dir),
            "--port",
            str(port),
        ],
        cwd=REPO_ROOT,
    )
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    RUNTIME_URL.write_text(url + "\n", encoding="utf-8")
    RUNTIME_PID.write_text(str(process.pid) + "\n", encoding="utf-8")
    if not args.no_browser and os.environ.get("PAPER_ATLAS_NO_BROWSER") != "1":
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        process.wait()
    except KeyboardInterrupt:
        process.terminate()
        process.wait(timeout=10)
    finally:
        if RUNTIME_PID.exists() and RUNTIME_PID.read_text(encoding="utf-8").strip() == str(process.pid):
            RUNTIME_PID.unlink(missing_ok=True)
            RUNTIME_URL.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
