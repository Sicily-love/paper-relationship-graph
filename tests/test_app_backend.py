import sys
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import app_backend  # noqa: E402


class AppBackendTests(unittest.TestCase):
    def test_state_exposes_discovery_topics_and_categories(self):
        modules = {
            "load_json": lambda _path, _fallback: {"topics": [{"label": "GPU"}]},
            "DEFAULT_CONFIG": Path("unused.json"),
            "serve_graph": SimpleNamespace(validated_discovery=lambda: {"candidates": []}),
            "build_graph": SimpleNamespace(STANDARD_CATEGORIES=["01_系统", "02_编译器"]),
        }

        result = app_backend.state(modules)

        self.assertEqual(result["topics"], [{"label": "GPU"}])
        self.assertEqual(result["shared_reference_minimum"], 2)
        self.assertEqual(result["highly_cited_minimum"], 50)
        self.assertEqual(
            result["categories"],
            [{"id": "01_系统", "label": "系统"}, {"id": "02_编译器", "label": "编译器"}],
        )

    def test_archived_candidate_is_returned_even_when_graph_refresh_fails(self):
        data = {"candidates": [{"id": "arxiv:1", "status": "new"}]}
        candidate = data["candidates"][0]
        modules = {
            "load_json": lambda _path, _fallback: data,
            "DEFAULT_DISCOVERY_JSON": Path("discovery.json"),
            "DEFAULT_DISCOVERY_JS": Path("discovery.js"),
            "manage_candidate": SimpleNamespace(
                apply_decision=lambda *_args: candidate | {"status": "accepted"},
            ),
            "write_discovery": lambda *_args: None,
            "serve_graph": SimpleNamespace(
                validated_discovery=lambda: {"candidates": [{"id": "arxiv:1", "status": "accepted"}]},
            ),
        }

        with patch.object(app_backend.subprocess, "run", return_value=SimpleNamespace(returncode=1)):
            result = app_backend.review_candidate(
                modules,
                {"action": "accept", "id": "arxiv:1", "category": "06_GPU"},
                Path("papers"),
            )

        self.assertFalse(result["graph_updated"])
        self.assertEqual(result["discovery"]["candidates"][0]["status"], "accepted")
        self.assertIn("已归档", result["message"])

    def test_discovery_sources_use_separate_commands(self):
        config = {
            "shared_references": {"min_library_citations": 2},
            "highly_cited": {"min_citations": 50},
        }
        writes = []
        modules = {
            "load_json": lambda _path, _fallback: config,
            "DEFAULT_CONFIG": Path("config.json"),
            "serve_graph": SimpleNamespace(
                discovery_mode=lambda value: value,
                validate_shared_reference_minimum=lambda value: int(value),
                validate_highly_cited_minimum=lambda value: int(value),
                write_json_atomic=lambda path, data: writes.append((path, data.copy())),
                validated_discovery=lambda: {"candidates": []},
            ),
        }
        completed = SimpleNamespace(returncode=0, stdout="", stderr="")
        with patch.object(app_backend.subprocess, "run", return_value=completed) as run:
            arxiv = app_backend.run_discovery(modules, {"mode": "arxiv"})
            highly_cited = app_backend.run_discovery(
                modules, {"mode": "highly_cited", "min_citations": 75}
            )
            shared = app_backend.run_discovery(
                modules, {"mode": "shared", "min_library_citations": 4}
            )

        self.assertEqual(arxiv["mode"], "arxiv")
        self.assertEqual(highly_cited["mode"], "highly_cited")
        self.assertEqual(shared["mode"], "shared")
        self.assertIn("--skip-shared", run.call_args_list[0].args[0])
        self.assertIn("--skip-highly-cited", run.call_args_list[0].args[0])
        self.assertIn("--skip-arxiv", run.call_args_list[1].args[0])
        self.assertIn("--skip-shared", run.call_args_list[1].args[0])
        self.assertIn("--skip-arxiv", run.call_args_list[2].args[0])
        self.assertIn("--skip-highly-cited", run.call_args_list[2].args[0])
        self.assertEqual(config["highly_cited"]["min_citations"], 75)
        self.assertEqual(config["shared_references"]["min_library_citations"], 4)
        self.assertEqual(len(writes), 2)

    def test_clear_candidates_returns_updated_queue(self):
        data = {"candidates": [{"id": "new", "status": "new"}]}
        modules = {
            "load_json": lambda _path, _fallback: data,
            "DEFAULT_DISCOVERY_JSON": Path("discovery.json"),
            "DEFAULT_DISCOVERY_JS": Path("discovery.js"),
            "write_discovery": lambda *_args: None,
            "serve_graph": SimpleNamespace(
                clear_new_candidates=lambda value: value.update({"candidates": []}) or 1,
                validated_discovery=lambda: {"candidates": []},
            ),
        }
        result = app_backend.clear_candidates(modules)
        self.assertEqual(result["removed_count"], 1)
        self.assertEqual(result["discovery"]["candidates"], [])

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
