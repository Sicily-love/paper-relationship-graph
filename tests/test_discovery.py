import sys
import unittest
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import discover_papers  # noqa: E402


class DiscoveryTests(unittest.TestCase):
    def test_arxiv_id_only_removes_version_suffix(self):
        self.assertEqual(discover_papers.arxiv_id_from_url("https://arxiv.org/abs/2501.01234v3"), "2501.01234")
        self.assertEqual(discover_papers.arxiv_id_from_url("https://arxiv.org/abs/cs/9901001v2"), "cs/9901001")

    def test_parse_arxiv_feed(self):
        payload = b"""<?xml version='1.0' encoding='UTF-8'?>
        <feed xmlns='http://www.w3.org/2005/Atom'>
          <entry>
            <id>https://arxiv.org/abs/2608.12345v2</id>
            <published>2026-08-18T12:00:00Z</published>
            <title>  Faster   GPU Kernels </title>
            <summary> A useful method. </summary>
            <author><name>Ada Example</name></author>
            <link title='pdf' href='https://arxiv.org/pdf/2608.12345v2'/>
          </entry>
        </feed>"""
        result = discover_papers.parse_arxiv_feed(
            payload,
            {"label": "GPU 优化"},
            datetime(2026, 8, 1, tzinfo=timezone.utc),
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "arxiv:2608.12345")
        self.assertEqual(result[0]["title"], "Faster GPU Kernels")
        self.assertEqual(result[0]["authors"], ["Ada Example"])

    def test_rejected_decision_is_not_recommended_again(self):
        candidate = {
            "id": "arxiv:2608.12345",
            "arxiv_id": "2608.12345",
            "title": "Faster GPU Kernels",
            "sources": ["arxiv_topic"],
            "topics": ["GPU 优化"],
            "score": 50,
            "status": "new",
        }
        previous = {
            "decisions": {
                "arxiv:2608.12345": {"status": "rejected", "decided_at": "2026-08-20T00:00:00Z"}
            },
            "candidates": [],
        }
        result = discover_papers.merge_candidates([candidate], previous, set(), 10)
        self.assertEqual(result, [])

    def test_duplicate_sources_are_merged_by_arxiv_id(self):
        arxiv = {
            "id": "arxiv:2608.12345",
            "arxiv_id": "2608.12345",
            "title": "Faster GPU Kernels",
            "sources": ["arxiv_topic"],
            "topics": ["GPU 优化"],
            "score": 50,
            "status": "new",
        }
        shared = {
            "id": "openalex:W1",
            "openalex_id": "https://openalex.org/W1",
            "arxiv_id": "2608.12345",
            "title": "Faster GPU Kernels",
            "sources": ["shared_reference"],
            "topics": [],
            "support_count": 3,
            "score": 110,
            "status": "new",
        }
        result = discover_papers.merge_candidates([arxiv, shared], {}, set(), 10)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "arxiv:2608.12345")
        self.assertEqual(result[0]["sources"], ["arxiv_topic", "shared_reference"])

    def test_unreviewed_candidate_stays_in_queue_during_retention_window(self):
        previous = {
            "candidates": [
                {
                    "id": "arxiv:2608.00001",
                    "arxiv_id": "2608.00001",
                    "title": "Still Worth Reviewing",
                    "sources": ["arxiv_topic"],
                    "score": 50,
                    "status": "new",
                    "last_seen": "2026-08-10T00:00:00+00:00",
                }
            ]
        }
        result = discover_papers.merge_candidates(
            [],
            previous,
            set(),
            10,
            datetime(2026, 8, 20, tzinfo=timezone.utc),
            60,
        )
        self.assertEqual([candidate["title"] for candidate in result], ["Still Worth Reviewing"])

    def test_candidates_are_sorted_newest_first(self):
        older = {
            "id": "openalex:W1",
            "openalex_id": "https://openalex.org/W1",
            "title": "Older Highly Cited Paper",
            "year": 2017,
            "sources": ["shared_reference"],
            "score": 200,
            "status": "new",
        }
        newer = {
            "id": "arxiv:2608.00002",
            "arxiv_id": "2608.00002",
            "title": "New Paper",
            "published": "2026-08-20",
            "year": 2026,
            "sources": ["arxiv_topic"],
            "score": 50,
            "status": "new",
        }
        result = discover_papers.merge_candidates([older, newer], {}, set(), 10)
        self.assertEqual([candidate["title"] for candidate in result], ["New Paper", "Older Highly Cited Paper"])

    def test_shared_reference_threshold_removes_stale_shared_only_candidates(self):
        candidates = [{
            "id": "openalex:W1",
            "title": "Weak Shared Reference",
            "sources": ["shared_reference"],
            "support_count": 2,
        }]
        self.assertEqual(discover_papers.apply_shared_reference_minimum(candidates, 3), [])

    def test_shared_reference_threshold_preserves_arxiv_provenance(self):
        candidates = [{
            "id": "arxiv:1",
            "title": "Found Both Ways",
            "sources": ["arxiv_topic", "shared_reference"],
            "topics": ["GPU"],
            "support_count": 2,
            "supporting_papers": [{"id": "p1"}],
        }]
        result = discover_papers.apply_shared_reference_minimum(candidates, 3)
        self.assertEqual(result[0]["sources"], ["arxiv_topic"])
        self.assertNotIn("support_count", result[0])
        self.assertEqual(result[0]["reason"], "匹配每日主题：GPU")

    def test_topic_query_uses_keywords_and_exclusions(self):
        query = discover_papers.topic_query({
            "label": "GPU",
            "keywords": ["GPU kernel", "Triton"],
            "exclude_keywords": ["survey"],
        })
        self.assertIn('ti:"GPU kernel"', query)
        self.assertIn('abs:"Triton"', query)
        self.assertIn('ANDNOT (all:"survey")', query)

    def test_openalex_topic_query_uses_boolean_search(self):
        query = discover_papers.openalex_topic_query({
            "label": "GPU",
            "keywords": ["GPU kernel", "Triton"],
            "exclude_keywords": ["survey"],
        })
        self.assertEqual(query, '("GPU kernel" OR Triton) NOT (survey)')

    def test_highly_cited_discovery_is_ranked_and_thresholded(self):
        works = [
            {
                "id": "https://openalex.org/W1",
                "display_name": "Highly Cited GPU Kernel Optimization",
                "publication_year": 2022,
                "publication_date": "2022-04-01",
                "ids": {"doi": "https://doi.org/10.1/example"},
                "cited_by_count": 420,
                "authorships": [{"author": {"display_name": "Ada Example"}}],
                "primary_location": {"landing_page_url": "https://example.org/work"},
                "abstract_inverted_index": {"GPU": [0], "kernel": [1], "optimization": [2]},
            },
            {
                "id": "https://openalex.org/W2",
                "display_name": "GPU Kernel Note",
                "publication_year": 2024,
                "cited_by_count": 9,
                "authorships": [],
                "primary_location": {},
            },
        ]
        requested = []

        def fake_request(url):
            requested.append(urllib.parse.urlsplit(url))
            return {"results": works}

        config = {
            "topics": [{
                "id": "category-06-gpu-performance",
                "label": "GPU 性能",
                "keywords": ["GPU kernel"],
            }],
            "highly_cited": {"min_citations": 100, "max_per_topic": 5, "max_candidates": 20},
        }
        with patch.object(discover_papers, "request_json", side_effect=fake_request):
            candidates, errors = discover_papers.discover_highly_cited(config)

        self.assertEqual(errors, [])
        self.assertEqual([candidate["id"] for candidate in candidates], ["openalex:W1"])
        self.assertEqual(candidates[0]["sources"], ["highly_cited"])
        self.assertEqual(candidates[0]["cited_by_count"], 420)
        params = urllib.parse.parse_qs(requested[0].query)
        self.assertEqual(params["sort"], ["cited_by_count:desc"])

    def test_highly_cited_and_arxiv_sources_merge(self):
        arxiv = {
            "id": "arxiv:2608.12345", "arxiv_id": "2608.12345",
            "title": "Faster GPU Kernels", "sources": ["arxiv_topic"],
            "topics": ["GPU"], "score": 50, "status": "new",
        }
        highly_cited = {
            "id": "openalex:W1", "openalex_id": "https://openalex.org/W1",
            "arxiv_id": "2608.12345", "title": "Faster GPU Kernels",
            "sources": ["highly_cited"], "topics": ["GPU"],
            "cited_by_count": 400, "highly_cited_threshold": 100,
            "score": 100, "status": "new",
        }
        result = discover_papers.merge_candidates([arxiv, highly_cited], {}, set(), 10)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["sources"], ["arxiv_topic", "highly_cited"])
        self.assertEqual(result[0]["cited_by_count"], 400)

    def test_highly_cited_candidate_already_in_library_is_excluded(self):
        candidate = {
            "id": "openalex:W1",
            "title": "Attention Is All You Need",
            "sources": ["highly_cited"],
            "cited_by_count": 150000,
            "score": 120,
            "status": "new",
        }
        result = discover_papers.merge_candidates(
            [candidate], {}, {discover_papers.normalize_title(candidate["title"])}, 10
        )
        self.assertEqual(result, [])

    def test_candidate_validation_flags_arxiv_year_conflict(self):
        result = discover_papers.candidate_validation({
            "title": "A Valid Paper Title",
            "authors": ["Ada Example"],
            "year": 2019,
            "arxiv_id": "2608.12345",
            "url": "https://arxiv.org/abs/2608.12345",
            "pdf_url": "https://arxiv.org/pdf/2608.12345",
            "sources": ["arxiv_topic"],
            "published": "2026-08-20",
        }, datetime(2026, 8, 20, tzinfo=timezone.utc))
        self.assertEqual(result["confidence_label"], "需核验")
        self.assertTrue(any("不一致" in warning for warning in result["metadata_warnings"]))

    def test_shared_threshold_preserves_highly_cited_source(self):
        candidate = {
            "id": "openalex:W1", "title": "Established Paper",
            "sources": ["highly_cited", "shared_reference"],
            "topics": ["GPU"], "support_count": 2,
            "cited_by_count": 500,
        }
        result = discover_papers.apply_shared_reference_minimum([candidate], 3)
        self.assertEqual(result[0]["sources"], ["highly_cited"])
        self.assertNotIn("support_count", result[0])
        self.assertIn("被引 500 次", result[0]["reason"])

    def test_candidate_is_automatically_classified_from_title_and_abstract(self):
        result = discover_papers.classify_candidate({
            "title": "KernelArc: A Multi-Agent Framework for GPU Kernel Optimization",
            "abstract": "We generate and tune Triton kernels with several cooperating agents.",
            "supporting_papers": [],
        })
        self.assertEqual(result["suggested_category"], "07_GPU内核智能体与自动调优")
        self.assertEqual(result["category_confidence"], "高")

    def test_attention_quantization_uses_attention_boundary_rule(self):
        result = discover_papers.classify_candidate({
            "title": "Low-Precision Quantized Attention for Long Context",
            "abstract": "An attention-specific quantization method.",
        })
        self.assertEqual(result["suggested_category"], "02_注意力机制与长上下文")

    def test_non_agentic_gpu_compiler_stays_in_performance_engineering(self):
        result = discover_papers.classify_candidate({
            "title": "A Tensor Compiler for Fast GPU Kernels",
            "abstract": "We compile tiled tensor programs into optimized GPU code without agents.",
        })
        self.assertEqual(result["suggested_category"], "06_GPU内核_编译器与性能工程")

    def test_automatic_kernel_generation_is_classified_as_performance_engineering(self):
        result = discover_papers.classify_candidate({
            "title": "AKG: Automatic Kernel Generation for Neural Processing Units",
            "abstract": "We use polyhedral transformations to generate efficient kernels.",
            "topic_ids": ["category-07-kernel-agents"],
        })
        self.assertEqual(result["suggested_category"], "06_GPU内核_编译器与性能工程")

    def test_search_topic_is_used_as_low_confidence_classification_fallback(self):
        result = discover_papers.classify_candidate({
            "title": "A Specialized Method with an Unfamiliar Name",
            "abstract": "No known category phrase is available.",
            "topic_ids": ["category-07-kernel-agents"],
        })
        self.assertEqual(result["suggested_category"], "07_GPU内核智能体与自动调优")
        self.assertEqual(result["category_confidence"], "需确认")

    def test_openalex_abstract_is_restored_in_word_order(self):
        abstract = discover_papers.abstract_from_inverted_index({
            "GPU": [2], "Fast": [0], "kernels": [3], "builds": [1],
        })
        self.assertEqual(abstract, "Fast builds GPU kernels")


if __name__ == "__main__":
    unittest.main()
