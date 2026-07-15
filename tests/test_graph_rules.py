import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_graph.py"
SPEC = importlib.util.spec_from_file_location("build_graph", MODULE_PATH)
build_graph = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(build_graph)


class GraphRuleTests(unittest.TestCase):
    def setUp(self):
        self.nodes = [
            {"id": "a", "title": "Alpha", "year": 2018, "category": "01_Test"},
            {"id": "b", "title": "Beta", "year": 2020, "category": "01_Test"},
            {"id": "c", "title": "Gamma", "year": 2022, "category": "01_Test"},
        ]

    def test_main_node_uses_highest_internal_citation_count(self):
        result = build_graph.choose_main_nodes(self.nodes, {"a": 2, "b": 5, "c": 1})
        self.assertEqual(result["01_Test"], "b")

    def test_time_edges_point_from_older_to_newer(self):
        edges = build_graph.build_time_edges(self.nodes, {"a": 3, "b": 1, "c": 0})
        self.assertEqual(edges, [{"source": "a", "target": "b"}, {"source": "a", "target": "c"}])


if __name__ == "__main__":
    unittest.main()
