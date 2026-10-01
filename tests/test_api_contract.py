import json
import tempfile
import time
import unittest
from unittest import mock
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from api_contract import ApiRequest, find_operation  # noqa: E402
from api_controller import ApiController  # noqa: E402
from job_manager import JobManager  # noqa: E402
from runtime_store import RuntimeStore  # noqa: E402


class ContractTests(unittest.TestCase):
    def test_versioned_routes_are_the_only_runtime_contract(self):
        self.assertEqual(find_operation("GET", "/api/v1/state")[0], "state")
        self.assertEqual(find_operation("POST", "/api/v1/discovery-runs")[0], "discovery.create")
        self.assertEqual(find_operation("DELETE", "/api/v1/candidates")[0], "candidates.clear")
        self.assertEqual(find_operation("DELETE", "/api/v1/graph/nodes/paper-1")[0], "graph.remove")
        self.assertEqual(find_operation("PUT", "/api/v1/papers/paper-1/read-status")[0], "papers.read_status")
        self.assertIsNone(find_operation("GET", "/api/state"))

    def test_controller_returns_versioned_bootstrap(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = ApiController(Path(directory), jobs=JobManager(Path(directory) / ".cache"))
            status, payload = controller.handle(ApiRequest("GET", "/api/v1/bootstrap"))
            self.assertEqual(status, 200)
            self.assertEqual(payload["meta"]["api_version"], "1")
            self.assertIn("capabilities", payload["data"])
            controller.jobs.close()

    def test_controller_updates_paper_read_status(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = ApiController(Path(directory), jobs=JobManager(Path(directory) / ".cache"))
            controller.services.set_paper_read_status = lambda body: {
                "paper": {"id": body["id"], "read": body["read"]},
            }
            status, payload = controller.handle(ApiRequest(
                "PUT", "/api/v1/papers/p00/read-status", {"read": True},
            ))
            self.assertEqual(status, 200)
            self.assertEqual(payload["data"]["paper"], {"id": "p00", "read": True})
            controller.jobs.close()

    def test_graph_response_excludes_discovery_only_external_references(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = ApiController(Path(directory), jobs=JobManager(Path(directory) / ".cache"))
            with mock.patch.object(
                sys.modules["api_controller"].discovery_utils,
                "load_json",
                return_value={"nodes": [], "edges": {}, "external_references": [{"title": "large"}]},
            ):
                status, payload = controller.handle(ApiRequest("GET", "/api/v1/graph"))
            self.assertEqual(status, 200)
            self.assertNotIn("external_references", payload["data"])
            controller.jobs.close()

    def test_score_palette_is_per_candidate_and_review_footer_stays_fixed_without_compositor_ghosts(self):
        styles = (ROOT / "web" / "styles.css").read_text(encoding="utf-8")
        script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
        formatting = (ROOT / "web" / "core" / "format.js").read_text(encoding="utf-8")
        self.assertIn("function scoreColor", formatting)
        self.assertIn("scoreColor", script)
        self.assertNotIn("candidate-score-track i { display: block; height: 100%; border-radius: inherit; background: linear-gradient", styles)
        self.assertIn(".candidate-detail-footer { position: relative", styles)
        self.assertIn("flex: 0 0 auto", styles)
        self.assertNotIn("backdrop-filter: blur(12px)", styles)
        self.assertIn("progressHost.appendChild(progress)", script)

    def test_topic_editor_supports_library_reference_papers(self):
        styles = (ROOT / "web" / "styles.css").read_text(encoding="utf-8")
        script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
        self.assertIn("reference_paper_ids", script)
        self.assertIn("topic-reference-picker", script)
        self.assertIn(".topic-reference-options { max-height:", styles)
        self.assertIn("selectedDiscoveryTopicIds", script)
        self.assertIn("topic_ids: [...selectedDiscoveryTopicIds]", script)

    def test_runtime_uses_versioned_api_and_native_bridge_has_no_route_table(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        native = (ROOT / "platform" / "macos" / "PaperAtlasLauncher.m").read_text(encoding="utf-8")
        self.assertNotIn('src="data/discovery-data.js', html)
        self.assertIn('src="core/runtime.js', html)
        self.assertNotIn('@"/api/state"', native)
        self.assertIn("runBackendRequestPath", native)
        self.assertIn('@"web/core"', native)


class JobTests(unittest.TestCase):
    def test_idempotency_and_reconnect(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = JobManager(Path(directory))
            first = manager.submit("test", lambda: {"ok": True}, request_id="req_1", idempotency_key="same", lock_key="test")
            second = manager.submit("test", lambda: {"ok": False}, request_id="req_2", idempotency_key="same", lock_key=None)
            self.assertEqual(first["id"], second["id"])
            for _ in range(50):
                if manager.get(first["id"])["status"] == "succeeded":
                    break
                time.sleep(0.01)
            record = manager.get(first["id"])
            self.assertEqual(record["status"], "succeeded")
            self.assertEqual(record["result"], {"ok": True})
            self.assertTrue((Path(directory) / "jobs" / f"{first['id']}.json").is_file())
            manager.close()

    def test_runtime_store_migrates_legacy_snapshots_once(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, discovery, tasks = [root / name for name in ("config.json", "discovery.json", "tasks.json")]
            config.write_text(json.dumps({"topics": []}), encoding="utf-8")
            discovery.write_text(json.dumps({"candidates": []}), encoding="utf-8")
            tasks.write_text(json.dumps({"tasks": {}}), encoding="utf-8")
            store = RuntimeStore(root / "paper-atlas.db")
            self.assertTrue(store.migrate_json(config=config, discovery=discovery, tasks=tasks))
            self.assertFalse(store.migrate_json(config=config, discovery=discovery, tasks=tasks))
            self.assertEqual(store.get("discovery", "current")["candidates"], [])


if __name__ == "__main__":
    unittest.main()
