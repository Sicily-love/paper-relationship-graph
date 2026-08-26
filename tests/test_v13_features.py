import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_graph  # noqa: E402
import discovery_evaluation  # noqa: E402
import discover_papers  # noqa: E402
import manage_candidate  # noqa: E402


class DiscoveryEvaluationTests(unittest.TestCase):
    def test_offline_quality_baseline_passes(self):
        report = discovery_evaluation.run()
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["metrics"]["recall"], 1.0)
        self.assertEqual(report["metrics"]["precision"], 1.0)


class ExternalReferenceTests(unittest.TestCase):
    def test_reference_index_groups_kernelbench_across_library_papers(self):
        nodes = [
            {"id": "a", "title": "Agent A", "category": "07", "sha256": "a"},
            {"id": "b", "title": "Agent B", "category": "07", "sha256": "b"},
        ]
        citation = (
            ("Body text about autonomous compiler agents and GPU optimization.\n" * 8)
            + "References\n[1] Anne Ouyang et al. KernelBench: Can LLMs Write Efficient GPU "
            "Kernels? arXiv preprint arXiv:2502.10517, 2025."
        )
        records = build_graph.build_external_reference_index(nodes, {"a": citation, "b": citation})
        kernel = next(item for item in records if item.get("arxiv_id") == "2502.10517")
        self.assertEqual(kernel["support_count"], 2)
        self.assertIn("KernelBench", kernel["title"])

    def test_pdf_reference_evidence_uses_existing_openalex_resolver(self):
        graph = {
            "nodes": [
                {"id": "a", "title": "Agent A", "category": "07", "sha256": "a"},
                {"id": "b", "title": "Agent B", "category": "07", "sha256": "b"},
            ],
            "edges": {"citation": []},
            "external_references": [{
                "key": "arxiv:2502.10517",
                "title": "KernelBench: Can LLMs Write Efficient GPU Kernels?",
                "arxiv_id": "2502.10517",
                "support_count": 2,
                "supporting_papers": [
                    {"id": "a", "title": "Agent A", "category": "07", "sha256": "a"},
                    {"id": "b", "title": "Agent B", "category": "07", "sha256": "b"},
                ],
            }],
        }
        work = {
            "id": "https://openalex.org/WK", "display_name": "KernelBench: Can LLMs Write Efficient GPU Kernels?",
            "publication_year": 2025, "cited_by_count": 100, "authorships": [],
            "referenced_works": [], "primary_location": {},
            "ids": {"arxiv": "https://arxiv.org/abs/2502.10517"},
        }

        def resolve(node, _mailto):
            return work if "KernelBench" in str(node.get("title")) else None

        with tempfile.TemporaryDirectory() as directory, (
            patch.object(discover_papers, "resolve_openalex_work", side_effect=resolve)
        ), patch.object(discover_papers, "fetch_openalex_works", return_value=[]):
            candidates, errors, stats = discover_papers.discover_shared_references(
                graph,
                {"shared_references": {"enabled": True, "min_library_citations": 2, "request_delay_seconds": 0}},
                Path(directory) / "cache.json",
            )
        self.assertEqual(errors, [])
        self.assertEqual([item["title"] for item in candidates], [work["display_name"]])
        self.assertEqual(candidates[0]["support_count"], 2)
        self.assertEqual(stats["pdf_external_resolved_count"], 1)


class CandidateLifecycleTests(unittest.TestCase):
    def test_dismissed_candidate_can_return_but_rejected_candidate_cannot(self):
        candidate = {"id": "arxiv:1", "arxiv_id": "1", "title": "Paper", "status": "new", "year": 2026}
        dismissed = {"candidates": [candidate], "decisions": {"arxiv:1": {"status": "dismissed"}}}
        rejected = {"candidates": [candidate], "decisions": {"arxiv:1": {"status": "rejected"}}}
        now = datetime(2026, 8, 26, tzinfo=timezone.utc)
        self.assertEqual(discover_papers.merge_candidates([dict(candidate)], dismissed, set(), 10, now)[0]["status"], "new")
        self.assertEqual(discover_papers.merge_candidates([dict(candidate)], rejected, set(), 10, now), [])

    def test_purge_removes_matching_reference_and_node_cache(self):
        cache = {
            "version": 3,
            "reference_index": {"https://openalex.org/WK": {"title": "KernelBench"}},
            "nodes": {"a": {"work": {"id": "https://openalex.org/WK", "display_name": "KernelBench", "ids": {}}}},
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cache.json"
            path.write_text(json.dumps(cache), encoding="utf-8")
            removed = manage_candidate.purge_reference_evidence(
                {"title": "KernelBench", "openalex_id": "https://openalex.org/WK"}, path,
            )
            saved = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(removed, 2)
        self.assertEqual(saved["reference_index"], {})
        self.assertEqual(saved["nodes"], {})


class RankingTests(unittest.TestCase):
    def test_composite_score_rewards_independent_evidence(self):
        graph = {"categories": [{"id": "07", "paper_count": 2}, {"id": "06", "paper_count": 10}]}
        base = {"year": 2025, "suggested_category": "07", "relevance_score": 80}
        single = discover_papers.score_recommendation({**base, "sources": ["arxiv_topic"]}, graph)
        combined = discover_papers.score_recommendation({
            **base, "sources": ["arxiv_topic", "shared_reference", "highly_cited"],
            "support_count": 4, "cited_by_count": 200,
        }, graph)
        self.assertGreater(combined["recommendation_score"], single["recommendation_score"])
        self.assertTrue(any("相互印证" in item for item in combined["ranking_explanation"]))


if __name__ == "__main__":
    unittest.main()
