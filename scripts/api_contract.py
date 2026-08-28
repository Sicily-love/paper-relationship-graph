"""Versioned API contracts shared by the HTTP and native transports.

The application deliberately keeps this module dependency free so it can be
bundled into the offline macOS runtime.  Transport adapters should translate
their native request format into :class:`ApiRequest` and use the same helpers
for success and error responses.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid
import subprocess
from typing import Any, Callable


def request_id(prefix: str = "req") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:20]}"


@dataclass(frozen=True)
class ApiRequest:
    method: str
    path: str
    body: dict[str, Any] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    query: dict[str, str] = field(default_factory=dict)
    request_id: str = field(default_factory=request_id)


class ApiProblem(Exception):
    """A stable, serialisable application error."""

    def __init__(
        self,
        code: str,
        message: str,
        status: int = 400,
        *,
        retryable: bool = False,
        details: dict[str, Any] | None = None,
        field: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.retryable = retryable
        self.details = details or {}
        self.field = field

    def as_dict(self, request: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "error": {
                "code": self.code,
                "message": self.message,
                "retryable": self.retryable,
            },
            "meta": {
                "api_version": "1",
                "request_id": request or request_id(),
            },
        }
        if self.field:
            payload["error"]["field"] = self.field
        if self.details:
            payload["error"]["details"] = self.details
        return payload


def success(data: Any, request: str, *, revision: str | None = None, status: int = 200) -> tuple[int, dict[str, Any]]:
    meta: dict[str, Any] = {
        "api_version": "1",
        "request_id": request,
    }
    if revision is not None:
        meta["revision"] = revision
    return status, {"data": data, "meta": meta}


def problem_from_exception(error: Exception, request: str) -> tuple[int, dict[str, Any]]:
    if isinstance(error, ApiProblem):
        return error.status, error.as_dict(request)
    if isinstance(error, ValueError):
        return 422, ApiProblem("validation_failed", str(error), 422).as_dict(request)
    if isinstance(error, (TimeoutError, subprocess.TimeoutExpired)):
        return 504, ApiProblem("job_timeout", "任务运行超时，请稍后重试", 504, retryable=True).as_dict(request)
    return 500, ApiProblem(
        "internal_error",
        "本地任务运行失败，请查看运行日志",
        500,
        details={"exception": type(error).__name__},
    ).as_dict(request)


# A single registry is the source of truth for documentation and adapters.
# All runtime callers use the versioned paths below.
OPERATIONS: dict[str, dict[str, Any]] = {
    "bootstrap": {"method": "GET", "path": "/api/v1/bootstrap", "kind": "query"},
    "state": {"method": "GET", "path": "/api/v1/state", "kind": "query"},
    "topics.read": {"method": "GET", "path": "/api/v1/topics", "kind": "query"},
    "topics.update": {"method": "PUT", "path": "/api/v1/topics", "kind": "mutation"},
    "discovery.create": {"method": "POST", "path": "/api/v1/discovery-runs", "kind": "job"},
    "candidates.list": {"method": "GET", "path": "/api/v1/candidates", "kind": "query"},
    "candidates.decision": {"method": "POST", "path": "/api/v1/candidates/{id}/decision", "kind": "job"},
    "candidates.feedback": {"method": "POST", "path": "/api/v1/candidates/{id}/feedback", "kind": "mutation"},
    "candidates.clear": {"method": "DELETE", "path": "/api/v1/candidates", "kind": "mutation"},
    "classification.reviews": {"method": "GET", "path": "/api/v1/classification-reviews", "kind": "query"},
    "classification.decision": {"method": "POST", "path": "/api/v1/classification-reviews/{id}/decision", "kind": "job"},
    "graph.read": {"method": "GET", "path": "/api/v1/graph", "kind": "query"},
    "graph.build": {"method": "POST", "path": "/api/v1/graph-builds", "kind": "job"},
    "graph.remove": {"method": "DELETE", "path": "/api/v1/graph/nodes/{id}", "kind": "job"},
    "jobs.get": {"method": "GET", "path": "/api/v1/jobs/{id}", "kind": "query"},
    "jobs.list": {"method": "GET", "path": "/api/v1/jobs", "kind": "query"},
    "jobs.cancel": {"method": "POST", "path": "/api/v1/jobs/{id}/cancel", "kind": "mutation"},
    "logs.read": {"method": "GET", "path": "/api/v1/logs", "kind": "query"},
    "diagnostics.create": {"method": "POST", "path": "/api/v1/diagnostic-runs", "kind": "job"},
    "maintenance.create": {"method": "POST", "path": "/api/v1/maintenance-runs", "kind": "job"},
    "tasks.read": {"method": "GET", "path": "/api/v1/tasks", "kind": "query"},
    "tasks.run": {"method": "POST", "path": "/api/v1/tasks/{id}/runs", "kind": "job"},
    "tasks.update": {"method": "PUT", "path": "/api/v1/tasks", "kind": "mutation"},
    "backups.create": {"method": "POST", "path": "/api/v1/backups", "kind": "job"},
    "backups.restore": {"method": "POST", "path": "/api/v1/backup-restores", "kind": "job"},
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def route_match(pattern: str, path: str) -> dict[str, str] | None:
    pattern_parts = pattern.strip("/").split("/")
    path_parts = path.strip("/").split("/")
    if len(pattern_parts) != len(path_parts):
        return None
    values: dict[str, str] = {}
    for expected, actual in zip(pattern_parts, path_parts):
        if expected.startswith("{") and expected.endswith("}"):
            values[expected[1:-1]] = actual
        elif expected != actual:
            return None
    return values


def find_operation(method: str, path: str) -> tuple[str, dict[str, str], dict[str, Any]] | None:
    method = method.upper()
    for name, spec in OPERATIONS.items():
        if spec["method"] != method:
            continue
        for candidate in (spec["path"],):
            if not candidate:
                continue
            params = route_match(candidate, path)
            if params is not None:
                return name, params, spec
    return None
