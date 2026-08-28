import json
import tempfile
import time
import unittest
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
        self.assertIsNone(find_operation("GET", "/api/state"))

    def test_controller_returns_versioned_bootstrap(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = ApiController(Path(directory), jobs=JobManager(Path(directory) / ".cache"))
            status, payload = controller.handle(ApiRequest("GET", "/api/v1/bootstrap"))
            self.assertEqual(status, 200)
            self.assertEqual(payload["meta"]["api_version"], "1")
            self.assertIn("capabilities", payload["data"])
            controller.jobs.close()

    def test_score_palette_is_per_candidate_and_review_footer_can_scroll(self):
        styles = (ROOT / "web" / "styles.css").read_text(encoding="utf-8")
        script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
        self.assertIn("function scoreColor", script)
        self.assertNotIn("candidate-score-track i { display: block; height: 100%; border-radius: inherit; background: linear-gradient", styles)
        self.assertIn(".candidate-detail-footer { position: absolute", styles)

    def test_runtime_uses_versioned_api_and_native_bridge_has_no_route_table(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        native = (ROOT / "platform" / "macos" / "PaperAtlasLauncher.m").read_text(encoding="utf-8")
        self.assertNotIn('src="data/discovery-data.js', html)
        self.assertNotIn('@"/api/state"', native)
        self.assertIn("runBackendRequestPath", native)


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
