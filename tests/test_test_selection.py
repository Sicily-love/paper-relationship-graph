import sys
import unittest
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import run_tests  # noqa: E402


class TestSelectionTests(unittest.TestCase):
    def test_documentation_change_uses_smoke_suite(self):
        self.assertEqual(run_tests.select_tests({"docs/backend-api-v1.md"}), run_tests.SMOKE_TESTS)

    def test_frontend_change_selects_contract_and_ui_tests(self):
        selected = run_tests.select_tests({"web/app.js"})
        self.assertIn("test_api_contract.py", selected)
        self.assertIn("test_v1_foundations.py", selected)
        self.assertNotIn("test_discovery.py", selected)

    def test_discovery_change_selects_discovery_related_tests(self):
        selected = run_tests.select_tests({"scripts/discover_papers.py"})
        self.assertIn("test_discovery.py", selected)
        self.assertIn("test_review_api.py", selected)
        self.assertIn("test_v13_features.py", selected)

    def test_unknown_script_change_falls_back_to_full_suite(self):
        selected = run_tests.select_tests({"scripts/new_core_module.py"})
        self.assertEqual(selected, run_tests.FULL_TESTS)

    def test_dependency_change_runs_full_suite(self):
        self.assertEqual(run_tests.select_tests({"requirements.txt"}), run_tests.FULL_TESTS)


if __name__ == "__main__":
    unittest.main()
