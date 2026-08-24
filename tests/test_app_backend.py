import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import app_backend  # noqa: E402
import app_services  # noqa: E402


class AppServicesTests(unittest.TestCase):
    def test_state_exposes_topics_categories_health_and_tasks(self):
        config = {
            "topics": [{"label": "GPU"}],
            "shared_references": {"min_library_citations": 3},
            "highly_cited": {"min_citations": 75},
        }
        with (
            patch.object(app_services, "load_json", return_value=config),
            patch.object(app_services, "validated_discovery", return_value={"candidates": []}),
            patch.object(app_services.build_graph, "STANDARD_CATEGORIES", ["01_系统", "02_编译器"]),
            patch.object(app_services.library_health, "validate_library", return_value={"status": "healthy"}),
            patch.object(app_services.task_center, "task_state", return_value={"tasks": []}),
        ):
            result = app_services.AppServices(Path("papers")).state()

        self.assertEqual(result["topics"], [{"label": "GPU"}])
        self.assertEqual(result["shared_reference_minimum"], 3)
        self.assertEqual(result["highly_cited_minimum"], 75)
        self.assertEqual(
            result["categories"],
            [{"id": "01_系统", "label": "系统"}, {"id": "02_编译器", "label": "编译器"}],
        )
        self.assertEqual(result["health"]["status"], "healthy")

    def test_archived_candidate_is_returned_even_when_graph_refresh_fails(self):
        candidate = {"id": "arxiv:1", "status": "accepted"}
        manager = app_services.manage_candidate
        completed = SimpleNamespace(returncode=1, stdout="", stderr="graph failed")
        service = app_services.AppServices(Path("papers"))
        with (
            patch.object(app_services, "load_json", return_value={"candidates": [candidate]}),
            patch.object(manager, "commit_decision", return_value=candidate),
            patch.object(manager, "mark_graph_status") as mark_status,
            patch.object(service, "_run_graph_update", return_value=completed),
            patch.object(app_services, "validated_discovery", return_value={"candidates": [candidate]}),
        ):
            result = service.review_candidate({
                "action": "accept", "id": "arxiv:1", "category": "06_GPU",
            })

        self.assertFalse(result["graph_updated"])
        self.assertEqual(result["candidate"]["status"], "accepted")
        self.assertIn("已归档", result["message"])
        self.assertEqual(mark_status.call_args.args[2], "pending")

    def test_discovery_sources_use_clear_command_arguments(self):
        config = {
            "shared_references": {"min_library_citations": 2},
            "highly_cited": {"min_citations": 50},
        }
        completed = SimpleNamespace(returncode=0, stdout="", stderr="")
        service = app_services.AppServices(Path("papers"))
        with (
            patch.object(app_services, "load_json", return_value=config),
            patch.object(app_services, "write_json_atomic") as write_config,
            patch.object(app_services, "validated_discovery", return_value={"candidates": []}),
            patch.object(app_services.subprocess, "run", return_value=completed) as run,
        ):
            topics = service.run_discovery({"mode": "topics"})
            arxiv = service.run_discovery({"mode": "arxiv"})
            highly_cited = service.run_discovery({"mode": "highly_cited", "min_citations": 75})
            shared = service.run_discovery({"mode": "shared", "min_library_citations": 4})

        self.assertEqual(topics["message"], "主题论文发现已完成")
        self.assertEqual(arxiv["mode"], "arxiv")
        self.assertEqual(highly_cited["mode"], "highly_cited")
        self.assertEqual(shared["mode"], "shared")
        commands = [call.args[0] for call in run.call_args_list]
        self.assertIn("--skip-shared", commands[0])
        self.assertNotIn("--skip-arxiv", commands[0])
        self.assertNotIn("--skip-highly-cited", commands[0])
        self.assertIn("--skip-highly-cited", commands[1])
        self.assertIn("--skip-arxiv", commands[2])
        self.assertIn("--skip-shared", commands[2])
        self.assertIn("--skip-arxiv", commands[3])
        self.assertIn("--skip-highly-cited", commands[3])
        self.assertEqual(config["highly_cited"]["min_citations"], 75)
        self.assertEqual(config["shared_references"]["min_library_citations"], 4)
        self.assertEqual(write_config.call_count, 2)

    def test_clear_candidates_returns_updated_queue(self):
        data = {"candidates": [{"id": "new", "status": "new"}]}
        service = app_services.AppServices(Path("papers"))
        with (
            patch.object(app_services, "load_json", return_value=data),
            patch.object(app_services, "write_discovery"),
            patch.object(app_services, "validated_discovery", return_value={"candidates": []}),
        ):
            result = service.clear_candidates()
        self.assertEqual(result["removed_count"], 1)
        self.assertEqual(result["discovery"]["candidates"], [])


class NativeBridgeTests(unittest.TestCase):
    def test_prepare_uses_embedded_python_without_bootstrapping(self):
        embedded = Path(sys.executable).resolve()
        with patch.dict(os.environ, {"PAPER_ATLAS_USE_CURRENT_PYTHON": "1"}):
            with patch("start_app.ensure_runtime") as ensure_runtime:
                with patch("start_app.refresh_graph_if_needed") as refresh:
                    result = app_backend.prepare(Path("papers"))
        ensure_runtime.assert_not_called()
        refresh.assert_called_once_with(embedded, Path("papers"))
        self.assertTrue(result["offline_runtime"])


if __name__ == "__main__":
    unittest.main()
