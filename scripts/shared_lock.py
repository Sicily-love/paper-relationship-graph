"""Cross-process locks for the shared offline data directory."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import threading

try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None


_thread_lock = threading.RLock()


@contextmanager
def data_lock(cache_dir: Path):
    """Serialize library mutations across App, HTTP and launchd processes."""
    lock_path = cache_dir / "paper-atlas-data.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with _thread_lock:
        with lock_path.open("a+", encoding="utf-8") as handle:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                if fcntl is not None:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
