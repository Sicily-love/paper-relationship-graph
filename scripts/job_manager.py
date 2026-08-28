"""Small persistent job runner for offline Paper Atlas operations."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import threading
import uuid
from typing import Any, Callable

from api_contract import ApiProblem, now_iso
from runtime_store import RuntimeStore

try:  # macOS and Linux; the fallback keeps unit tests portable.
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None


class JobManager:
    """Run bounded local work and persist status so a UI can reconnect later."""

    def __init__(self, cache_dir: Path, max_workers: int = 2) -> None:
        self.root = cache_dir / "jobs"
        self.root.mkdir(parents=True, exist_ok=True)
        self.store = RuntimeStore(cache_dir / "paper-atlas.db")
        self._lock = threading.RLock()
        self._futures: dict[str, Future[Any]] = {}
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="paper-atlas-job")
        self._mark_interrupted()

    def close(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _path(self, job_id: str) -> Path:
        return self.root / f"{job_id}.json"

    def _locked_write(self, path: Path, record: dict[str, Any]) -> None:
        lock_path = self.root / ".lock"
        lock_path.touch(exist_ok=True)
        with lock_path.open("r+", encoding="utf-8") as lock:
            if fcntl is not None:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            temporary = path.with_suffix(path.suffix + ".tmp")
            temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            os.replace(temporary, path)
            try:
                self.store.put("jobs", path.stem, record)
            except Exception:
                pass
            if fcntl is not None:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    def _read(self, job_id: str) -> dict[str, Any] | None:
        path = self._path(job_id)
        if not path.is_file():
            return None
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return record if isinstance(record, dict) else None

    def _records(self) -> list[dict[str, Any]]:
        records = []
        for path in sorted(self.root.glob("job_*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(record, dict):
                records.append(record)
        return records

    def _mark_interrupted(self) -> None:
        for record in self._records():
            if record.get("status") in {"queued", "running"}:
                record["status"] = "interrupted"
                record["finished_at"] = now_iso()
                record["error"] = {
                    "code": "job_interrupted",
                    "message": "应用在任务完成前退出，可重新运行",
                    "retryable": True,
                }
                self._locked_write(self._path(str(record.get("id"))), record)

    def submit(
        self,
        job_type: str,
        operation: Callable[[], Any],
        *,
        request_id: str,
        idempotency_key: str | None = None,
        lock_key: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            records = self._records()
            if idempotency_key:
                for record in records:
                    if record.get("idempotency_key") == idempotency_key and record.get("type") == job_type:
                        return record
            if lock_key:
                for record in records:
                    if record.get("lock_key") == lock_key and record.get("status") in {"queued", "running"}:
                        raise ApiProblem(
                            "job_conflict",
                            "相同类型的任务正在运行，请等待完成",
                            409,
                            retryable=True,
                            details={"job_id": record.get("id")},
                        )
            job_id = f"job_{uuid.uuid4().hex[:20]}"
            record: dict[str, Any] = {
                "id": job_id,
                "type": job_type,
                "status": "queued",
                "progress": {"phase": "queued", "current": 0, "total": 0, "percent": 0, "message": "等待运行"},
                "created_at": now_iso(),
                "started_at": None,
                "finished_at": None,
                "result": None,
                "error": None,
                "request_id": request_id,
                "idempotency_key": idempotency_key,
                "lock_key": lock_key,
                "metadata": metadata or {},
            }
            self._locked_write(self._path(job_id), record)
            self._futures[job_id] = self._executor.submit(self._run, job_id, operation)
            return record

    def _update(self, job_id: str, **changes: Any) -> dict[str, Any] | None:
        with self._lock:
            record = self._read(job_id)
            if record is None:
                return None
            record.update(changes)
            self._locked_write(self._path(job_id), record)
            return record

    def update_progress(self, job_id: str, phase: str, current: int = 0, total: int = 0, message: str = "") -> None:
        percent = round(current / total * 100) if total else 0
        self._update(job_id, progress={"phase": phase, "current": current, "total": total, "percent": percent, "message": message})

    def _run(self, job_id: str, operation: Callable[[], Any]) -> None:
        self._update(job_id, status="running", started_at=now_iso())
        try:
            result = operation()
        except Exception as error:  # The API never leaks a traceback to the UI.
            problem = error if isinstance(error, ApiProblem) else ApiProblem(
                "job_failed", str(error) or type(error).__name__, 500, retryable=True,
            )
            self._update(job_id, status="failed", finished_at=now_iso(), error={
                "code": problem.code,
                "message": problem.message,
                "retryable": problem.retryable,
                "details": problem.details,
            })
        else:
            self._update(job_id, status="succeeded", finished_at=now_iso(), result=result,
                         progress={"phase": "complete", "current": 1, "total": 1, "percent": 100, "message": "已完成"})
        finally:
            with self._lock:
                self._futures.pop(job_id, None)

    def get(self, job_id: str) -> dict[str, Any]:
        record = self._read(job_id)
        if record is None:
            raise ApiProblem("not_found", "任务不存在", 404)
        return record

    def list(self, *, status: str | None = None, job_type: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        records = self._records()
        if status:
            records = [record for record in records if record.get("status") == status]
        if job_type:
            records = [record for record in records if record.get("type") == job_type]
        return records[: max(1, min(limit, 200))]

    def cancel(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            record = self.get(job_id)
            if record.get("status") == "queued":
                future = self._futures.get(job_id)
                if future and future.cancel():
                    return self._update(job_id, status="cancelled", finished_at=now_iso()) or record
            if record.get("status") == "running":
                raise ApiProblem("job_not_cancellable", "任务已经开始运行，只能等待完成", 409, retryable=True)
            return record
