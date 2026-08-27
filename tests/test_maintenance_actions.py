import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import app_services  # noqa: E402
import library_health  # noqa: E402
import maintenance_actions  # noqa: E402
import system_diagnostics  # noqa: E402


class MaintenanceActionTests(unittest.TestCase):
    def test_issue_exposes_human_readable_action(self):
        item = library_health.issue(
            "graph-files-mismatch", "error", "图谱不同步", "少一个节点", "rebuild",
        )
        self.assertEqual(item["action"], "rebuild")
        self.assertEqual(item["action_label"], "重新生成图谱")
        self.assertTrue(item["action_description"])

    def test_actions_for_issues_deduplicates_repairs(self):
        actions = maintenance_actions.actions_for_issues([
            {"code": "graph-invalid", "action": "rebuild"},
            {"code": "broken-edges", "action": "rebuild"},
            {"code": "unclassified-files", "action": "classify"},
        ])
        self.assertEqual([item["id"] for item in actions], ["rebuild", "classify"])
        self.assertEqual(
            actions[0]["issue_codes"], ["graph-invalid", "broken-edges"],
        )

    def test_repair_discovery_pair_prefers_valid_json(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            json_path, js_path = root / "discovery.json", root / "discovery.js"
            data = {"candidates": [{"id": "paper-1"}], "decisions": {}}
            json_path.write_text(json.dumps(data), encoding="utf-8")
            js_path.write_text("broken", encoding="utf-8")

            result = maintenance_actions.repair_discovery_pair(json_path, js_path)

            self.assertEqual(result, {"source": "json", "candidate_count": 1})
            self.assertTrue(js_path.read_text(encoding="utf-8").startswith("window.PAPER_DISCOVERY="))

    def test_repair_discovery_pair_recovers_from_browser_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            json_path, js_path = root / "discovery.json", root / "discovery.js"
            data = {"candidates": [{"id": "paper-1"}], "decisions": {}}
            json_path.write_text("{", encoding="utf-8")
            js_path.write_text(
                "window.PAPER_DISCOVERY=" + json.dumps(data) + ";", encoding="utf-8",
            )

            result = maintenance_actions.repair_discovery_pair(json_path, js_path)

            self.assertEqual(result["source"], "javascript")
            self.assertEqual(json.loads(json_path.read_text(encoding="utf-8")), data)

    def test_repair_discovery_pair_never_overwrites_two_invalid_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            json_path, js_path = root / "discovery.json", root / "discovery.js"
            json_path.write_text("{", encoding="utf-8")
            js_path.write_text("broken", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "均无法读取"):
                maintenance_actions.repair_discovery_pair(json_path, js_path)
            self.assertEqual(json_path.read_text(encoding="utf-8"), "{")
            self.assertEqual(js_path.read_text(encoding="utf-8"), "broken")


class MaintenanceServiceTests(unittest.TestCase):
    def test_default_maintenance_action_remains_graph_rebuild(self):
        service = app_services.AppServices(Path("papers"))
        with patch.object(service, "rebuild_graph", return_value={"message": "done"}) as rebuild:
            result = service.run_maintenance({})
        rebuild.assert_called_once_with()
        self.assertEqual(result["message"], "done")

    def test_classification_action_returns_review_and_health(self):
        service = app_services.AppServices(Path("papers"))
        task_result = {
            "message": "task done", "status": "success",
            "result": {"graph_updated": True},
        }
        with (
            patch.object(app_services.task_center, "run_task", return_value=task_result),
            patch.object(
                app_services.classify_library, "load_review_queue",
                return_value={"items": [{"id": "review-1"}]},
            ),
            patch.object(
                app_services.library_health, "validate_library",
                return_value={"status": "warning"},
            ),
        ):
            result = service.run_maintenance({"action": "classify"})

        self.assertTrue(result["graph_updated"])
        self.assertEqual(result["classification_review"]["items"][0]["id"], "review-1")
        self.assertEqual(result["health"]["status"], "warning")

    def test_diagnostic_report_collects_action_buttons(self):
        papers = Path("papers")
        healthy = {"status": "healthy", "summary": "ok", "issues": [], "actions": []}
        evaluation = {
            "status": "passed", "case_count": 1,
            "metrics": {
                "precision": 1.0, "recall": 1.0,
                "classification_accuracy": 1.0, "dedupe_accuracy": 1.0,
            },
            "cases": [],
        }
        graph = {"metadata": {}, "external_references": {}}
        discovery = {"metadata": {"errors": ["network failed"], "run_mode": "arxiv"}}

        def fake_load(path, default):
            if path == system_diagnostics.DEFAULT_GRAPH:
                return graph
            if path == system_diagnostics.DEFAULT_DISCOVERY_JSON:
                return discovery
            return {"version": 3, "reference_index": {"x": {}}}

        with (
            patch.object(system_diagnostics.library_health, "validate_library", return_value=healthy),
            patch.object(system_diagnostics.discovery_evaluation, "run", return_value=evaluation),
            patch.object(system_diagnostics, "load_json", side_effect=fake_load),
            patch.object(system_diagnostics.task_center, "task_state", return_value={"tasks": []}),
            patch.object(system_diagnostics, "recent_debug_events", return_value=[]),
        ):
            report = system_diagnostics.run(papers, include_network=False)

        self.assertEqual(report["status"], "warning")
        self.assertIn("retry-discovery", {item["id"] for item in report["actions"]})


if __name__ == "__main__":
    unittest.main()
