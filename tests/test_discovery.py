import sys
import tempfile
import unittest
import urllib.error
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

    def test_arxiv_kernel_agent_query_looks_deep_without_generic_agent_noise(self):
        payload = b"""<?xml version='1.0' encoding='UTF-8'?>
        <feed xmlns='http://www.w3.org/2005/Atom'>
          <entry>
            <id>https://arxiv.org/abs/2608.17071</id>
            <published>2026-08-17T19:21:23Z</published>
            <title>KernelArc: A Multi-Agent Framework for GPU Kernel Optimization</title>
            <summary>Agents generate and optimize GPU kernels using language models.</summary>
            <author><name>Ada Example</name></author>
          </entry>
        </feed>"""
        requested = []
        config = {
            "topics": [{
                "id": "category-07-kernel-agents",
                "label": "GPU 内核智能体与自动调优",
                "keywords": ["GPU kernel agent", "agent"],
                "max_results": 5,
            }],
            "arxiv": {"fetch_pool_size": 100, "request_delay_seconds": 0},
        }
        with patch.object(
            discover_papers, "request_bytes",
            side_effect=lambda url: requested.append(url) or payload,
        ):
            candidates, errors = discover_papers.discover_arxiv(
                config, datetime(2026, 8, 12, tzinfo=timezone.utc)
            )
        params = urllib.parse.parse_qs(urllib.parse.urlsplit(requested[0]).query)
        self.assertEqual(errors, [])
        self.assertEqual([item["arxiv_id"] for item in candidates], ["2608.17071"])
        self.assertEqual(params["max_results"], ["100"])
        self.assertIn(" AND ", params["search_query"][0])

    def test_arxiv_rate_limit_falls_back_to_recent_openalex_arxiv_records(self):
        work = {
            "id": "https://openalex.org/W7203772857",
            "display_name": "KernelArc: A Multi-Agent Framework for GPU Kernel Optimization",
            "publication_year": 2026,
            "publication_date": "2026-08-17",
            "ids": {"arxiv": "https://arxiv.org/abs/2608.17071"},
            "authorships": [], "primary_location": {},
            "abstract_inverted_index": {
                "Agents": [0], "optimize": [1], "GPU": [2], "kernels": [3],
            },
        }
        config = {
            "topics": [{
                "id": "category-07-kernel-agents",
                "label": "GPU 内核智能体与自动调优",
                "keywords": ["GPU kernel", "multi-agent"],
            }],
            "arxiv": {"request_delay_seconds": 0},
        }
        with patch.object(
            discover_papers, "request_bytes", side_effect=urllib.error.URLError("HTTP 429"),
        ), patch.object(discover_papers, "request_json", return_value={"results": [work]}):
            candidates, errors = discover_papers.discover_arxiv(
                config, datetime(2026, 8, 12, tzinfo=timezone.utc)
            )
        self.assertEqual(errors, [])
        self.assertEqual([item["arxiv_id"] for item in candidates], ["2608.17071"])
        self.assertEqual(candidates[0]["discovery_provider"], "openalex_arxiv_fallback")

    def test_openalex_semantic_query_treats_keywords_as_soft_context(self):
        query = discover_papers.openalex_semantic_query({
            "label": "GPU",
            "keywords": ["GPU kernel", "Triton"],
            "exclude_keywords": ["survey"],
        })
        self.assertEqual(query, "Academic research papers about GPU kernel; Triton")
        self.assertNotIn("survey", query)

    def test_kernel_agent_semantic_query_uses_library_reference_papers(self):
        query = discover_papers.openalex_semantic_query({
            "id": "category-07-kernel-agents",
            "label": "GPU 内核智能体与自动调优",
            "keywords": ["GPU kernel agent"],
            "reference_titles": ["KernelBench: Can LLMs Write Efficient GPU Kernels?"],
        })
        self.assertIn("language models and autonomous agents", query)
        self.assertIn("KernelBench", query)

    def test_live_topic_profile_uses_current_category_papers(self):
        category = "08_GPU内核智能体与自动调优"
        graph = {
            "categories": [{"id": category, "main_node": "p1"}],
            "nodes": [
                {"id": "p1", "category": category, "title": "KernelBench GPU Kernel Agents", "citation_count": 8},
                {"id": "p2", "category": category, "title": "KernelPro GPU Kernel Agents", "citation_count": 2},
            ],
        }
        config, profiles = discover_papers.enrich_topics_from_library({"topics": [{
            "id": "category-07-kernel-agents", "label": "GPU", "keywords": ["CUDA agent"],
        }]}, graph)
        self.assertIn("gpu kernel", config["topics"][0]["dynamic_keywords"])
        self.assertEqual(profiles[0]["paper_count"], 2)
        self.assertEqual(profiles[0]["reference_titles"][0], "KernelBench GPU Kernel Agents")
        self.assertEqual(profiles[0]["reference_mode"], "automatic")

    def test_live_topic_profile_prefers_selected_reference_papers(self):
        category = "08_GPU内核智能体与自动调优"
        graph = {
            "categories": [{"id": category, "main_node": "p1"}],
            "nodes": [
                {"id": "p1", "sha256": "sha-main", "category": category,
                 "title": "KernelBench GPU Kernel Agents", "citation_count": 8},
                {"id": "p2", "sha256": "sha-selected", "category": category,
                 "title": "A User Selected Compiler Paper", "citation_count": 2},
            ],
        }
        config, profiles = discover_papers.enrich_topics_from_library({"topics": [{
            "id": "category-07-kernel-agents", "label": "GPU", "keywords": ["CUDA agent"],
            "reference_paper_ids": ["sha-selected"],
        }]}, graph)
        self.assertEqual(config["topics"][0]["reference_titles"], ["A User Selected Compiler Paper"])
        self.assertEqual(profiles[0]["reference_mode"], "selected")

    def test_openalex_resolver_sanitizes_kernelbench_question_mark(self):
        requested = []
        work = {
            "id": "https://openalex.org/W4407683692",
            "display_name": "KernelBench: Can LLMs Write Efficient GPU Kernels?",
            "authorships": [],
        }
        with patch.object(
            discover_papers, "request_json",
            side_effect=lambda url: requested.append(url) or {"results": [work]},
        ):
            result = discover_papers.resolve_openalex_work({
                "title": "KernelBench: Can LLMs Write Efficient GPU Kernels?", "authors": [],
            }, "test@example.com")
        params = urllib.parse.parse_qs(urllib.parse.urlsplit(requested[0]).query)
        self.assertEqual(params["search"], ["KernelBench: Can LLMs Write Efficient GPU Kernels"])
        self.assertEqual(result["id"], work["id"])

    def test_shared_references_report_kernelbench_when_it_is_already_in_library(self):
        kernel = {
            "id": "https://openalex.org/WK", "display_name": "KernelBench",
            "referenced_works": [], "authorships": [],
        }
        citing_one = {
            "id": "https://openalex.org/W1", "display_name": "Kernel Agent One",
            "referenced_works": [kernel["id"]], "authorships": [],
        }
        citing_two = {
            "id": "https://openalex.org/W2", "display_name": "Kernel Agent Two",
            "referenced_works": [kernel["id"]], "authorships": [],
        }
        graph = {"nodes": [
            {"id": "p0", "title": "KernelBench", "category": "07", "sha256": "a"},
            {"id": "p1", "title": "Kernel Agent One", "category": "07", "sha256": "b"},
            {"id": "p2", "title": "Kernel Agent Two", "category": "07", "sha256": "c"},
        ]}
        with tempfile.TemporaryDirectory() as directory, patch.object(
            discover_papers, "resolve_openalex_work", side_effect=[kernel, citing_one, citing_two],
        ):
            candidates, errors, stats = discover_papers.discover_shared_references(
                graph,
                {"shared_references": {"enabled": True, "min_library_citations": 2, "request_delay_seconds": 0}},
                Path(directory) / "cache.json",
            )
        self.assertEqual(errors, [])
        self.assertEqual(candidates, [])
        self.assertEqual(stats["shared_reference_library_count"], 1)
        self.assertEqual(stats["shared_reference_library_matches"][0]["title"], "KernelBench")

    def test_shared_reference_local_evidence_survives_target_deletion(self):
        kernel = {
            "id": "https://openalex.org/WK", "display_name": "KernelBench",
            "referenced_works": [], "authorships": [], "cited_by_count": 10,
        }
        citing_works = [
            {"id": f"https://openalex.org/W{i}", "display_name": f"Kernel Agent {i}",
             "referenced_works": [], "authorships": []}
            for i in range(1, 4)
        ]
        graph = {
            "nodes": [
                {"id": "p0", "title": "KernelBench", "category": "07", "sha256": "kernel"},
                *[
                    {"id": f"p{i}", "title": f"Kernel Agent {i}", "category": "07", "sha256": f"agent-{i}"}
                    for i in range(1, 4)
                ],
            ],
            "edges": {"citation": [
                {"source": f"p{i}", "target": "p0"} for i in range(1, 4)
            ]},
        }
        config = {"shared_references": {
            "enabled": True, "min_library_citations": 3, "request_delay_seconds": 0,
        }}
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "cache.json"
            with patch.object(
                discover_papers, "resolve_openalex_work",
                side_effect=[kernel, *citing_works],
            ):
                discover_papers.discover_shared_references(graph, config, cache)
            missing_graph = {"nodes": graph["nodes"][1:], "edges": {"citation": []}}
            with patch.object(discover_papers, "fetch_openalex_works", return_value=[kernel]):
                candidates, errors, _stats = discover_papers.discover_shared_references(
                    missing_graph, config, cache
                )
        self.assertEqual(errors, [])
        self.assertEqual([item["title"] for item in candidates], ["KernelBench"])
        self.assertEqual(candidates[0]["support_count"], 3)

    def test_local_graph_is_authoritative_for_internal_shared_references(self):
        graph = {
            "nodes": [
                {"id": "p0", "title": "KernelBench", "category": "07", "sha256": "a"},
                {"id": "p1", "title": "Kernel Agent One", "category": "07", "sha256": "b"},
                {"id": "p2", "title": "Kernel Agent Two", "category": "07", "sha256": "c"},
            ],
            "edges": {"citation": [
                {"source": "p1", "target": "p0"},
                {"source": "p2", "target": "p0"},
            ]},
        }
        with tempfile.TemporaryDirectory() as directory, patch.object(
            discover_papers, "resolve_openalex_work", return_value=None,
        ):
            _candidates, _errors, stats = discover_papers.discover_shared_references(
                graph,
                {"shared_references": {"enabled": True, "min_library_citations": 2, "request_delay_seconds": 0}},
                Path(directory) / "cache.json",
            )
        match = stats["shared_reference_library_matches"][0]
        self.assertEqual(match["title"], "KernelBench")
        self.assertEqual(match["support_count"], 2)
        self.assertEqual(match["evidence_source"], "library_graph")

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
                "relevance_score": 1.08,
                "primary_topic": {"display_name": "GPU Computing"},
            },
            {
                "id": "https://openalex.org/W2",
                "display_name": "GPU Kernel Note",
                "publication_year": 2024,
                "cited_by_count": 9,
                "authorships": [],
                "primary_location": {},
                "relevance_score": 0.94,
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
            candidates, errors, stats = discover_papers.discover_highly_cited(config)

        self.assertEqual(errors, [])
        self.assertEqual([candidate["id"] for candidate in candidates], ["openalex:W1"])
        self.assertEqual(candidates[0]["sources"], ["highly_cited"])
        self.assertEqual(candidates[0]["cited_by_count"], 420)
        self.assertEqual(candidates[0]["relevance_evidence"][1], "OpenAlex 主题 GPU Computing")
        self.assertEqual(stats["highly_cited_raw_count"], 2)
        self.assertEqual(stats["highly_cited_threshold_count"], 1)
        self.assertEqual(stats["highly_cited_selected_count"], 1)
        params = urllib.parse.parse_qs(requested[0].query)
        self.assertEqual(params["search.semantic"], ["Academic research papers about GPU kernel"])
        self.assertEqual(params["per-page"], ["50"])
        self.assertNotIn("sort", params)

    def test_highly_cited_soft_match_does_not_require_literal_keyword(self):
        work = {
            "id": "https://openalex.org/W3",
            "display_name": "Scaling Neural Network Training Across Accelerator Clusters",
            "publication_year": 2023,
            "cited_by_count": 88,
            "authorships": [],
            "primary_location": {},
            "abstract_inverted_index": {
                "Sharded": [0], "optimizer": [1], "states": [2], "reduce": [3],
                "communication": [4], "costs": [5],
            },
            "relevance_score": 1.02,
            "primary_topic": {"display_name": "Distributed Deep Learning"},
        }
        config = {
            "topics": [{
                "id": "category-05-distributed-data",
                "label": "分布式训练与数据基础设施",
                "keywords": ["FSDP", "model parallel"],
            }],
            "highly_cited": {"min_citations": 1},
        }
        with patch.object(discover_papers, "request_json", return_value={"results": [work]}):
            candidates, errors, stats = discover_papers.discover_highly_cited(config)

        self.assertEqual(errors, [])
        self.assertEqual([candidate["id"] for candidate in candidates], ["openalex:W3"])
        self.assertIn("语义相似度", candidates[0]["relevance_evidence"][0])
        self.assertEqual(stats["highly_cited_relevant_count"], 1)

    def test_highly_cited_lexical_fallback_recovers_kernelbench(self):
        kernelbench = {
            "id": "https://openalex.org/W4407683692",
            "display_name": "KernelBench: Can LLMs Write Efficient GPU Kernels?",
            "publication_year": 2025,
            "publication_date": "2025-02-14",
            "cited_by_count": 1,
            "authorships": [],
            "primary_location": {},
        }

        def fake_request(url):
            params = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
            return {"results": [] if "search.semantic" in params else [kernelbench]}

        config = {
            "topics": [{
                "id": "category-07-kernel-agents",
                "label": "GPU 内核智能体与自动调优",
                "keywords": ["GPU kernel agent", "CUDA agent"],
            }],
            "highly_cited": {"min_citations": 1, "request_delay_seconds": 0},
        }
        with patch.object(discover_papers, "request_json", side_effect=fake_request), patch.object(
            discover_papers.time, "sleep", return_value=None,
        ):
            candidates, errors, stats = discover_papers.discover_highly_cited(config)
        self.assertEqual(errors, [])
        self.assertEqual([item["title"] for item in candidates], [kernelbench["display_name"]])
        self.assertIn("lexical", candidates[0]["openalex_search_modes"])
        self.assertEqual(stats["highly_cited_search_mode"], "semantic+lexical")

    def test_highly_cited_reserves_recall_slots_for_lexical_matches(self):
        semantic = [
            {
                "id": f"https://openalex.org/S{i}",
                "display_name": f"Popular Semantic Paper {i}",
                "cited_by_count": 10_000 - i,
                "authorships": [], "primary_location": {}, "relevance_score": 1.0,
            }
            for i in range(10)
        ]
        kernelbench = {
            "id": "https://openalex.org/W4407683692",
            "display_name": "KernelBench: Can LLMs Write Efficient GPU Kernels?",
            "cited_by_count": 1, "authorships": [], "primary_location": {},
        }

        def fake_request(url):
            params = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
            return {"results": semantic if "search.semantic" in params else [kernelbench]}

        config = {
            "topics": [{
                "id": "category-07-kernel-agents", "label": "GPU",
                "keywords": ["GPU kernel agent", "CUDA agent"],
            }],
            "highly_cited": {
                "min_citations": 1, "max_per_topic": 5, "max_candidates": 60,
            },
        }
        with patch.object(discover_papers, "request_json", side_effect=fake_request), patch.object(
            discover_papers.time, "sleep", return_value=None,
        ):
            candidates, _errors, _stats = discover_papers.discover_highly_cited(config)
        self.assertIn(kernelbench["display_name"], [item["title"] for item in candidates])

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
        self.assertEqual(result["suggested_category"], "08_GPU内核智能体与自动调优")
        self.assertEqual(result["category_confidence"], "高")

    def test_attention_quantization_uses_attention_boundary_rule(self):
        result = discover_papers.classify_candidate({
            "title": "Low-Precision Quantized Attention for Long Context",
            "abstract": "An attention-specific quantization method.",
        })
        self.assertEqual(result["suggested_category"], "03_注意力机制与长上下文")

    def test_foundational_attention_paper_prefers_architecture_category(self):
        result = discover_papers.classify_candidate({
            "title": "Attention Is All You Need",
            "abstract": "We introduce the Transformer architecture for sequence transduction.",
        })
        self.assertEqual(result["suggested_category"], "01_模型架构与基础组件")
        self.assertEqual(result["category_rule_version"], discover_papers.CATEGORY_RULE_VERSION)

    def test_attention_kernel_paper_stays_in_attention_category(self):
        result = discover_papers.classify_candidate({
            "title": "TiledAttention A CUDA Tile SDPA Kernel for PyTorch",
            "abstract": "We implement scaled dot-product attention with a fused CUDA kernel.",
        })
        self.assertEqual(result["suggested_category"], "03_注意力机制与长上下文")

    def test_moe_kernel_optimization_prefers_moe_category(self):
        result = discover_papers.classify_candidate({
            "title": "SonicMoE Accelerating MoE with IO and Tile-aware Optimizations",
            "abstract": "Mixture of Experts models benefit from GPU kernels that reduce IO overhead.",
        })
        self.assertEqual(result["suggested_category"], "04_MoE与稀疏模型")

    def test_llm_kernel_benchmark_prefers_kernel_agents(self):
        result = discover_papers.classify_candidate({
            "title": "KernelBench Can LLMs Write Efficient GPU Kernels?",
            "abstract": "We evaluate language models that generate and optimize GPU kernels.",
        })
        self.assertEqual(result["suggested_category"], "08_GPU内核智能体与自动调优")

    def test_non_agentic_gpu_compiler_stays_in_performance_engineering(self):
        result = discover_papers.classify_candidate({
            "title": "A Tensor Compiler for Fast GPU Kernels",
            "abstract": "We compile tiled tensor programs into optimized GPU code without agents.",
        })
        self.assertEqual(result["suggested_category"], "07_GPU内核_编译器与性能工程")

    def test_automatic_kernel_generation_is_classified_as_performance_engineering(self):
        result = discover_papers.classify_candidate({
            "title": "AKG: Automatic Kernel Generation for Neural Processing Units",
            "abstract": "We use polyhedral transformations to generate efficient kernels.",
            "topic_ids": ["category-07-kernel-agents"],
        })
        self.assertEqual(result["suggested_category"], "07_GPU内核_编译器与性能工程")

    def test_search_topic_is_used_as_low_confidence_classification_fallback(self):
        result = discover_papers.classify_candidate({
            "title": "A Specialized Method with an Unfamiliar Name",
            "abstract": "No known category phrase is available.",
            "topic_ids": ["category-07-kernel-agents"],
        })
        self.assertEqual(result["suggested_category"], "08_GPU内核智能体与自动调优")
        self.assertEqual(result["category_confidence"], "需确认")

    def test_openalex_abstract_is_restored_in_word_order(self):
        abstract = discover_papers.abstract_from_inverted_index({
            "GPU": [2], "Fast": [0], "kernels": [3], "builds": [1],
        })
        self.assertEqual(abstract, "Fast builds GPU kernels")


if __name__ == "__main__":
    unittest.main()
