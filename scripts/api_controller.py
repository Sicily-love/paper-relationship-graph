"""Transport-neutral v1 API controller.

HTTP and the macOS bridge both call this controller.  It intentionally wraps
the existing AppServices instead of duplicating discovery or graph logic.
"""

from __future__ import annotations

from pathlib import Path
import time
from urllib.parse import unquote

from api_contract import ApiProblem, ApiRequest, find_operation, problem_from_exception, success
from app_services import AppServices, validated_discovery
import build_graph
import classify_library
import discovery_utils
from job_manager import JobManager
from shared_lock import data_lock
from api_logging import log_event


class ApiController:
    def __init__(self, papers_dir: Path, *, jobs: JobManager | None = None) -> None:
        self.papers_dir = papers_dir.expanduser().resolve()
        self.services = AppServices(self.papers_dir)
        cache_dir = discovery_utils.DEFAULT_CONFIG.parents[1] / ".cache"
        self.cache_dir = cache_dir
        self.jobs = jobs or JobManager(cache_dir)

    def _revision(self) -> str | None:
        graph = discovery_utils.DEFAULT_GRAPH
        if not graph.exists():
            return None
        stat = graph.stat()
        return f"{stat.st_mtime_ns}:{stat.st_size}"

    def _bootstrap(self) -> dict:
        state = self.services.state()
        return {
            "version": "1",
            "capabilities": {
                "async_jobs": True,
                "native_transport": True,
                "http_transport": True,
                "offline": True,
            },
            "revisions": {
                "graph": self._revision(),
                "discovery": state.get("discovery", {}).get("metadata", {}).get("updated_at"),
            },
            "counts": {
                "candidates": len(state.get("discovery", {}).get("candidates", [])),
                "classification_reviews": len(state.get("classification_review", {}).get("items", [])),
                "papers": state.get("health", {}).get("paper_count"),
            },
        }

    def _job(self, request: ApiRequest, job_type: str, operation, *, lock_key: str, metadata: dict | None = None):
        key = request.headers.get("Idempotency-Key") or request.body.get("idempotency_key")
        def guarded_operation():
            if lock_key in {"library-write", "discovery", "backup"}:
                with data_lock(self.cache_dir):
                    return operation()
            return operation()

        record = self.jobs.submit(job_type, guarded_operation, request_id=request.request_id,
                                  idempotency_key=key, lock_key=lock_key, metadata=metadata)
        return success({"job": record}, request.request_id, status=202)

    def _new_request_body(self, request: ApiRequest, params: dict[str, str]) -> dict:
        body = dict(request.body)
        body.update({key: unquote(value) for key, value in params.items()})
        return body

    def handle(self, request: ApiRequest) -> tuple[int, dict]:
        started = time.monotonic()
        operation_name = "unknown"
        result_status = "failed"
        job_id = None
        match = find_operation(request.method, request.path)
        if match is None:
            log_event(self.cache_dir, operation="unknown", request_id=request.request_id, status="not_found", elapsed_ms=round((time.monotonic() - started) * 1000)) if hasattr(self, "cache_dir") else None
            return 404, ApiProblem("not_found", "接口不存在", 404).as_dict(request.request_id)
        name, params, _spec = match
        operation_name = name
        body = self._new_request_body(request, params)
        try:
            status, result = self._dispatch(name, request, body)
            job_id = (((result.get("data") or {}).get("job") or {}).get("id") if isinstance(result, dict) else None)
            result_status = "accepted" if status == 202 else "completed"
            return status, result
        except Exception as error:
            status, result = problem_from_exception(error, request.request_id)
            result_status = "failed"
            return status, {"error": result.get("error", result), "meta": result.get("meta", {"request_id": request.request_id})}
        finally:
            if hasattr(self, "cache_dir"):
                error_code = None
                if isinstance(result if 'result' in locals() else None, dict):
                    error_code = ((result.get("error") or {}).get("code") if isinstance(result.get("error"), dict) else None)
                log_event(self.cache_dir, operation=operation_name, request_id=request.request_id,
                          status=result_status, elapsed_ms=round((time.monotonic() - started) * 1000),
                          job_id=job_id, error_code=error_code)

    def _dispatch(self, name: str, request: ApiRequest, body: dict) -> tuple[int, dict]:
        if name == "bootstrap":
            return success(self._bootstrap(), request.request_id, revision=self._revision())
        if name == "state":
            return success(self.services.state(), request.request_id, revision=self._revision())
        if name == "topics.read":
            return success(self.services.state().get("topics", []), request.request_id)
        if name == "topics.update":
            return success(self.services.save_topics(body), request.request_id)
        if name == "graph.read":
            return success(discovery_utils.load_json(discovery_utils.DEFAULT_GRAPH, {"nodes": [], "edges": {}}), request.request_id, revision=self._revision())
        if name == "candidates.list":
            data = validated_discovery()
            candidates = [item for item in data.get("candidates", []) if item.get("status") == request.query.get("status", "new")]
            source = request.query.get("source")
            category = request.query.get("category")
            if source:
                candidates = [item for item in candidates if source in item.get("sources", [])]
            if category:
                candidates = [item for item in candidates if item.get("suggested_category") == category]
            candidates.sort(key=lambda item: item.get("discovered_at") or item.get("updated_at") or "", reverse=True)
            try:
                limit = max(1, min(int(request.query.get("limit", "50")), 200))
            except ValueError:
                limit = 50
            return success({"items": candidates[:limit], "next_cursor": None, "total": len(candidates)}, request.request_id)
        if name == "classification.reviews":
            return success(classify_library.load_review_queue(), request.request_id)
        if name == "classification.decision":
            return self._job(request, "classification-review", lambda: self.services.review_classification(body),
                             lock_key="library-write", metadata={"item_id": body.get("id")})
        if name == "discovery.create":
            return self._job(request, "discovery", lambda: self.services.run_discovery(body), lock_key="discovery")
        if name == "candidates.decision":
            return self._job(request, "candidate-decision", lambda: self.services.review_candidate(body),
                             lock_key=f"candidate:{body.get('id')}", metadata={"candidate_id": body.get("id"), "action": body.get("action")})
        if name == "candidates.clear":
            return success(self.services.clear_candidates(body), request.request_id)
        if name == "candidates.feedback":
            return success(self.services.candidate_feedback(body), request.request_id)
        if name == "graph.remove":
            return self._job(request, "graph-remove", lambda: self.services.remove_graph_node(body), lock_key="library-write", metadata={"node_id": body.get("id")})
        if name == "graph.build":
            return self._job(request, "graph-build", lambda: self.services.rebuild_graph(body), lock_key="library-write")
        if name == "diagnostics.create":
            return self._job(request, "diagnostics", lambda: self.services.run_diagnostics(body), lock_key="diagnostics")
        if name == "maintenance.create":
            return self._job(request, "maintenance", lambda: self.services.run_maintenance(body), lock_key="library-write")
        if name == "tasks.read":
            return success(self.services.manage_tasks({"action": "state"}), request.request_id)
        if name == "tasks.run":
            task_id = body.get("id")
            return self._job(request, "task-run", lambda: self.services.manage_tasks({"action": "run", "task_id": task_id}),
                             lock_key=f"task:{task_id}", metadata={"task_id": task_id})
        if name == "tasks.update":
            return success(self.services.manage_tasks({"action": "configure", "tasks": body.get("tasks")}), request.request_id)
        if name == "backups.create":
            return self._job(request, "backup-export", lambda: self.services.manage_backup({"action": "export"}), lock_key="backup")
        if name == "backups.restore":
            return self._job(request, "backup-restore", lambda: self.services.manage_backup({"action": "restore", "backup": body.get("backup")}), lock_key="backup")
        if name == "jobs.get":
            return success(self.jobs.get(body["id"]), request.request_id)
        if name == "jobs.list":
            return success({"items": self.jobs.list(status=request.query.get("status"), job_type=request.query.get("type"))}, request.request_id)
        if name == "jobs.cancel":
            return success(self.jobs.cancel(body["id"]), request.request_id)
        if name == "logs.read":
            return success(self.services.runtime_logs(body), request.request_id)
        raise ApiProblem("not_implemented", "接口尚未实现", 501)
