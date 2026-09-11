import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfWriter


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_graph.py"
sys.path.insert(0, str(MODULE_PATH.parent))
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

    def test_main_node_tie_prefers_earlier_paper(self):
        result = build_graph.choose_main_nodes(self.nodes, {"a": 2, "b": 2, "c": 1})
        self.assertEqual(result["01_Test"], "a")

    def test_extract_abstract_stops_before_introduction(self):
        text = """Paper title
Abstract
We introduce a fast and accurate method for long-context inference.
1 Introduction
This should not appear in the abstract.
"""
        self.assertEqual(
            build_graph.extract_abstract(text),
            "We introduce a fast and accurate method for long-context inference.",
        )

    def test_extract_authors_uses_first_page_when_metadata_is_empty(self):
        text = """Example Paper
Ada Lovelace & Alan Turing
Example University
Abstract
Example abstract.
"""
        authors = build_graph.extract_authors(text, "Example Paper", {"/Author": ""})
        self.assertEqual(authors, "Ada Lovelace & Alan Turing")

    def test_extract_authors_recognizes_blog_byline(self):
        text = "Muon: An optimizer | Keller Jordan blog\nMuon: An optimizer"
        authors = build_graph.extract_authors(text, "Muon: An optimizer", {"/Author": "liangchenyu03"})
        self.assertEqual(authors, "Keller Jordan")

    def test_extract_authors_recognizes_collaboration_byline(self):
        text = """On-Policy Distillation
Kevin Lu in collaboration with others at Thinking Machines
Oct 27, 2025
"""
        authors = build_graph.extract_authors(text, "On-Policy Distillation", {"/Author": ""})
        self.assertEqual(authors, "Kevin Lu")

    def test_same_title_versions_share_one_graph_node(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            category = build_graph.STANDARD_CATEGORIES[0]
            folder = root / category
            folder.mkdir()
            for name, author in (
                ("Example Paper.pdf", "Ada"),
                ("Example Paper (重复版本).pdf", "Alan"),
            ):
                writer = PdfWriter()
                writer.add_blank_page(width=72, height=72)
                writer.add_metadata({"/Author": author})
                with (folder / name).open("wb") as handle:
                    writer.write(handle)

            nodes, _text, duplicates, _stats = build_graph.extract_nodes(root)

            self.assertEqual(len(nodes), 1)
            self.assertEqual(nodes[0]["title"], "Example Paper")
            self.assertEqual(len(duplicates), 1)
            self.assertEqual(duplicates[0]["match"], "normalized_title")


if __name__ == "__main__":
    unittest.main()
