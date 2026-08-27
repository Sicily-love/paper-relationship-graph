import sys
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pypdf import PdfWriter


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import manage_candidate  # noqa: E402
import app_services  # noqa: E402
import serve_graph  # noqa: E402


class ReviewApiTests(unittest.TestCase):
    def test_validate_topics_normalizes_human_friendly_fields(self):
        topics = serve_graph.validate_topics([{
            "label": " 长上下文 ",
            "keywords": [" long context ", "KV cache"],
            "exclude_keywords": ["survey"],
            "enabled": True,
            "max_results": 8,
        }])
        self.assertEqual(topics[0]["label"], "长上下文")
        self.assertEqual(topics[0]["keywords"], ["long context", "KV cache"])
        self.assertEqual(topics[0]["max_results"], 8)

    def test_validate_topics_requires_keywords(self):
        with self.assertRaisesRegex(ValueError, "1–12"):
            serve_graph.validate_topics([{"label": "空主题", "keywords": []}])

    def test_shared_reference_minimum_is_bounded(self):
        self.assertEqual(serve_graph.validate_shared_reference_minimum("4"), 4)
        with self.assertRaisesRegex(ValueError, "2–20"):
            serve_graph.validate_shared_reference_minimum(1)

    def test_highly_cited_minimum_is_bounded(self):
        self.assertEqual(serve_graph.validate_highly_cited_minimum("75"), 75)
        with self.assertRaisesRegex(ValueError, "1–1,000,000"):
            serve_graph.validate_highly_cited_minimum(0)
        with self.assertRaisesRegex(ValueError, "1–1,000,000"):
            serve_graph.validate_highly_cited_minimum(1_000_001)

    def test_topic_discovery_mode_combines_arxiv_and_highly_cited(self):
        self.assertEqual(serve_graph.discovery_mode("topics"), "topics")

    def test_existing_unclassified_candidate_is_classified_when_loaded(self):
        candidate = {
            "id": "openalex:W1",
            "title": "AKG: Automatic Kernel Generation for Neural Processing Units",
            "abstract": "Polyhedral transformations generate efficient kernels.",
            "sources": ["highly_cited"],
            "authors": ["Example Author"],
            "year": 2021,
            "url": "https://openalex.org/W1",
            "cited_by_count": 77,
            "highly_cited_threshold": 50,
        }
        with patch.object(app_services, "load_json", return_value={"candidates": [candidate]}):
            result = app_services.validated_discovery()
        self.assertEqual(
            result["candidates"][0]["suggested_category"],
            "07_GPU内核_编译器与性能工程",
        )

    def test_clear_candidates_keeps_archived_records_and_decisions(self):
        data = {
            "candidates": [
                {"id": "new", "status": "new", "sources": ["shared_reference"]},
                {"id": "kept", "status": "accepted", "sources": ["arxiv_topic"]},
            ],
            "decisions": {"kept": {"status": "accepted"}},
        }
        removed = serve_graph.clear_new_candidates(data)
        self.assertEqual(removed, 1)
        self.assertEqual([item["id"] for item in data["candidates"]], ["kept"])
        self.assertEqual(data["decisions"]["kept"]["status"], "accepted")

    def test_reject_records_decision(self):
        data = {"candidates": [{"id": "arxiv:1", "title": "Example", "status": "new"}]}
        with tempfile.TemporaryDirectory() as directory:
            candidate = manage_candidate.apply_decision(data, "arxiv:1", "reject", Path(directory))
        self.assertEqual(candidate["status"], "rejected")
        self.assertEqual(data["decisions"]["arxiv:1"]["status"], "rejected")

    def test_accept_requires_category_before_download(self):
        data = {"candidates": [{"id": "arxiv:1", "title": "Example", "status": "new"}]}
        with tempfile.TemporaryDirectory() as directory, patch.object(manage_candidate, "accept") as accept:
            with self.assertRaisesRegex(ValueError, "请选择"):
                manage_candidate.apply_decision(data, "arxiv:1", "accept", Path(directory))
        accept.assert_not_called()

    def test_accept_downloads_valid_pdf_into_selected_category(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.pdf"
            writer = PdfWriter()
            writer.add_blank_page(width=100, height=100)
            with source.open("wb") as output:
                writer.write(output)
            papers = root / "papers"
            category = "07_GPU内核_编译器与性能工程"
            data = {"candidates": [{
                "id": "arxiv:1",
                "title": "A Safe GPU Paper",
                "pdf_url": source.as_uri(),
                "status": "new",
            }]}
            candidate = manage_candidate.apply_decision(data, "arxiv:1", "accept", papers, category)
            destination = papers / candidate["accepted_path"]
            self.assertTrue(destination.is_file())
            self.assertEqual(destination.parent.name, category)

    def test_accept_moves_matching_unclassified_copy_instead_of_duplicating_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.pdf"
            writer = PdfWriter()
            writer.add_blank_page(width=100, height=100)
            with source.open("wb") as output:
                writer.write(output)
            papers = root / "papers"
            papers.mkdir()
            unclassified = papers / "Existing Download.pdf"
            shutil.copyfile(source, unclassified)
            category = "07_GPU内核_编译器与性能工程"
            data = {"candidates": [{
                "id": "arxiv:1",
                "title": "A Safe GPU Paper",
                "pdf_url": source.as_uri(),
                "status": "new",
            }]}

            candidate = manage_candidate.apply_decision(data, "arxiv:1", "accept", papers, category)

            self.assertFalse(unclassified.exists())
            self.assertTrue((papers / candidate["accepted_path"]).is_file())
            self.assertEqual(len(manage_candidate.library_paper_files(papers)), 1)

    def test_openalex_fallback_recovers_arxiv_pdf_for_publisher_only_candidate(self):
        work = {
            "ids": {"doi": "https://doi.org/10.1145/example"},
            "best_oa_location": {"landing_page_url": "https://arxiv.org/abs/2309.06180"},
            "locations": [{"pdf_url": "https://arxiv.org/pdf/2309.06180"}],
        }
        response = io.BytesIO(json.dumps(work).encode("utf-8"))
        with patch.object(manage_candidate.urllib.request, "urlopen", return_value=response):
            urls = manage_candidate.openalex_pdf_urls({"openalex_id": "https://openalex.org/W4387321091"})
        self.assertIn("https://arxiv.org/pdf/2309.06180", urls)

    def test_arxiv_title_fallback_recovers_paged_attention_preprint(self):
        feed = b'''<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom"><entry>
          <id>http://arxiv.org/abs/2309.06180v1</id>
          <title>Efficient Memory Management for Large Language Model Serving with PagedAttention</title>
          <link title="pdf" href="https://arxiv.org/pdf/2309.06180v1" type="application/pdf"/>
        </entry></feed>'''
        with patch.object(manage_candidate.urllib.request, "urlopen", return_value=io.BytesIO(feed)):
            urls = manage_candidate.arxiv_title_pdf_urls({
                "title": "Efficient Memory Management for Large Language Model Serving with PagedAttention",
            })
        self.assertIn("https://arxiv.org/pdf/2309.06180v1", urls)


if __name__ == "__main__":
    unittest.main()
