"""Structured, bounded operation logging shared by all transports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from api_contract import now_iso
from runtime_store import RuntimeStore


def log_event(cache_dir: Path, *, operation: str, request_id: str, status: str, elapsed_ms: int, job_id: str | None = None, error_code: str | None = None) -> None:
    event: dict[str, Any] = {
        "timestamp": now_iso(),
        "operation": operation,
        "request_id": request_id,
        "status": status,
        "elapsed_ms": elapsed_ms,
    }
    if job_id:
        event["job_id"] = job_id
    if error_code:
        event["error_code"] = error_code
    path = cache_dir / "operation-log.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")
    try:
        RuntimeStore(cache_dir / "paper-atlas.db").append_event(
            operation=operation, request_id=request_id, status=status,
            elapsed_ms=elapsed_ms, job_id=job_id, error_code=error_code,
        )
    except Exception:
        # JSONL remains the last-resort diagnostic path if the DB is damaged.
        pass
