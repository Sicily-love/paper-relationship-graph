import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from pypdf import PdfWriter


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import backup_restore  # noqa: E402
import build_graph  # noqa: E402
import classify_library  # noqa: E402
import discover_papers  # noqa: E402
import generate_release_notes  # noqa: E402
import library_health  # noqa: E402
import manage_candidate  # noqa: E402
import prepare_release_seed  # noqa: E402
import task_center  # noqa: E402
from discovery_utils import write_discovery  # noqa: E402


class TransactionTests(unittest.TestCase):
    def make_pdf(self, path: Path) -> None:
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        with path.open("wb") as output:
            writer.write(output)

    def test_archive_rolls_back_when_decision_persistence_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.pdf"
            self.make_pdf(source)
            papers = root / "papers"
            data = {"candidates": [{
                "id": "arxiv:1", "title": "Transactional Paper",
                "pdf_url": source.as_uri(), "status": "new",
            }]}
            before = json.loads(json.dumps(data))
            with patch.object(manage_candidate, "write_discovery", side_effect=OSError("disk full")):
                with self.assertRaisesRegex(OSError, "disk full"):
                    manage_candidate.commit_decision(
                        data, "arxiv:1", "accept", papers,
                        "07_GPU内核_编译器与性能工程", root / "d.json", root / "d.js",
                    )
            self.assertEqual(data, before)
            self.assertFalse(any(papers.rglob("*.pdf")))

    def test_committed_archive_is_marked_pending_then_complete(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.pdf"
            self.make_pdf(source)
            papers = root / "papers"
            json_path, js_path = root / "d.json", root / "d.js"
            data = {"candidates": [{
                "id": "arxiv:1", "title": "Transactional Paper",
                "pdf_url": source.as_uri(), "status": "new",
            }]}
            candidate = manage_candidate.commit_decision(
                data, "arxiv:1", "accept", papers,
                "07_GPU内核_编译器与性能工程", json_path, js_path,
            )
            self.assertEqual(candidate["graph_status"], "pending")
            manage_candidate.mark_graph_status(data, "arxiv:1", "complete", json_path, js_path)
            self.assertEqual(data["decisions"]["arxiv:1"]["graph_status"], "complete")


class RelevanceTests(unittest.TestCase):
    topic = {
        "id": "category-04-quantization",
        "label": "量化与低精度计算",
        "keywords": ["quantization", "low precision"],
    }

    def test_physics_keyword_collision_is_filtered(self):
        result = discover_papers.candidate_relevance({
            "title": "Quantization of a scalar field in de Sitter space",
            "abstract": "We study Hilbert spaces and reflection positivity in quantum field theory.",
        }, self.topic)
        self.assertFalse(result["relevant"])

    def test_machine_learning_quantization_is_retained_with_evidence(self):
        result = discover_papers.candidate_relevance({
            "title": "INT4 Quantization for Transformer Inference",
            "abstract": "A low precision method for efficient large language model inference on GPU accelerators.",
        }, self.topic)
        self.assertTrue(result["relevant"])
        self.assertGreaterEqual(result["relevance_score"], 40)
        self.assertTrue(result["relevance_evidence"])


class HealthAndBackupTests(unittest.TestCase):
    def test_health_matches_files_json_and_browser_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            papers = root / "papers"
            for category in build_graph.STANDARD_CATEGORIES:
                (papers / category).mkdir(parents=True)
            category = build_graph.STANDARD_CATEGORIES[0]
            pdf = papers / category / "Example.pdf"
            pdf.write_bytes(b"test")
            graph = {
                "metadata": {"unique_papers": 1, "citation_edges": 0},
                "categories": [{"id": category, "main_node": "p00", "paper_count": 1}],
                "nodes": [{"id": "p00", "path": f"{category}/Example.pdf", "category": category}],
                "edges": {"citation": []}, "duplicates": [],
            }
            graph_json, graph_js = root / "g.json", root / "g.js"
            graph_json.write_text(json.dumps(graph), encoding="utf-8")
            graph_js.write_text("window.PAPER_GRAPH=" + json.dumps(graph) + ";\n", encoding="utf-8")
            discovery = {"metadata": {}, "candidates": [], "decisions": {}}
            discovery_json, discovery_js = root / "d.json", root / "d.js"
            write_discovery(discovery, discovery_json, discovery_js)
            health = library_health.validate_library(
                papers, graph_json, graph_js, discovery_json, discovery_js,
            )
            self.assertEqual(health["status"], "healthy")

    def test_backup_roundtrip_preserves_topics_decisions_and_tasks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_path, tasks_path = root / "config.json", root / "tasks.json"
            discovery_path, discovery_js = root / "discovery.json", root / "discovery.js"
            graph_path = root / "graph.json"
            config = {"topics": [{"label": "GPU", "keywords": ["GPU kernel"]}]}
            tasks = task_center.default_config()
            discovery = {"candidates": [], "decisions": {"x": {"status": "rejected"}}}
            config_path.write_text(json.dumps(config), encoding="utf-8")
            tasks_path.write_text(json.dumps(tasks), encoding="utf-8")
            discovery_path.write_text(json.dumps(discovery), encoding="utf-8")
            graph_path.write_text(json.dumps({"metadata": {}, "categories": []}), encoding="utf-8")
            backup = backup_restore.create_backup(config_path, discovery_path, graph_path, tasks_path)
            backup_restore.restore_backup(
                backup, config, tasks, config_path, discovery_path, discovery_js, tasks_path,
            )
            self.assertEqual(json.loads(discovery_path.read_text())["decisions"]["x"]["status"], "rejected")


class TaskCenterTests(unittest.TestCase):
    def test_task_times_are_validated_and_next_run_is_future(self):
        config = task_center.validate_config({"tasks": {
            "classification": {"enabled": True, "time": "10:30"},
            "arxiv": {"enabled": True, "time": "11:00"},
        }})
        self.assertEqual(config["tasks"]["arxiv"]["time"], "11:00")
        now = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)
        self.assertGreater(datetime.fromisoformat(task_center.next_run("10:30", now)), now)
        with self.assertRaises(ValueError):
            task_center.validate_time("25:00")

    def test_launch_agent_contains_calendar_and_selected_library(self):
        payload = task_center.launch_agent_payload(
            "classification", {"enabled": True, "time": "10:30"}, Path("/papers")
        )
        self.assertEqual(payload["StartCalendarInterval"], {"Hour": 10, "Minute": 30})
        self.assertIn("/papers", payload["ProgramArguments"])
        self.assertEqual(payload["EnvironmentVariables"]["PYTHONDONTWRITEBYTECODE"], "1")
        self.assertEqual(payload["EnvironmentVariables"]["PYTHONNOUSERSITE"], "1")
        self.assertEqual(payload["EnvironmentVariables"]["SSL_CERT_FILE"], "/etc/ssl/cert.pem")


class ClassificationTests(unittest.TestCase):
    def test_matching_presentation_follows_existing_paper_category(self):
        with tempfile.TemporaryDirectory() as directory:
            papers = Path(directory)
            category = build_graph.STANDARD_CATEGORIES[1]
            (papers / category).mkdir()
            (papers / category / "UltraAttn Efficient Attention.pdf").write_bytes(b"pdf")
            presentation = papers / "ultraattn.pptx"
            presentation.write_bytes(b"pptx")
            result = classify_library.classify_files(papers)
            self.assertEqual(len(result["classified"]), 1)
            self.assertTrue((papers / category / "ultraattn.pptx").exists())

    def test_pending_classification_is_persisted_for_review(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "review.json"
            queue = classify_library.write_review_queue([{
                "path": "Unknown.pdf", "suggested_category": "", "confidence": "需确认",
                "reason": "分类依据不足",
            }], path)
            self.assertEqual(len(queue["items"]), 1)
            self.assertTrue(queue["items"][0]["id"])
            self.assertEqual(classify_library.load_review_queue(path)["items"][0]["path"], "Unknown.pdf")

    def test_unreadable_pdf_becomes_review_item_instead_of_failing_task(self):
        with tempfile.TemporaryDirectory() as directory:
            papers = Path(directory)
            (papers / "Broken.pdf").write_bytes(b"not a pdf")
            result = classify_library.classify_files(papers)
            self.assertEqual(result["classified"], [])
            self.assertEqual(result["pending"][0]["confidence"], "读取失败")


class WebContractTests(unittest.TestCase):
    def test_v1_controls_and_default_relation_mode_are_present(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
        styles = (ROOT / "web" / "styles.css").read_text(encoding="utf-8")
        self.assertIn("Paper Atlas 1.4.0", html)
        self.assertIn('id="version-history"', html)
        self.assertIn('id="release-notes-dialog"', html)
        self.assertIn("window.PAPER_RELEASES", script)
        self.assertIn('id="task-list"', html)
        self.assertIn('id="classification-review-panel"', html)
        self.assertIn('id="discovery-debug-output"', html)
        self.assertIn('data/graph-data.js?v=${Date.now()}', html)
        self.assertIn('id="export-backup"', html)
        self.assertIn('id="run-diagnostics"', html)
        self.assertIn('id="open-runtime-logs"', html)
        self.assertIn('id="logs-dialog"', html)
        self.assertIn('id="remove-graph-node"', html)
        self.assertIn('id="run-topic-discovery"', html)
        self.assertIn('id="graph-heading">论文图谱', html)
        self.assertIn('id="diagnostics-panel"', html)
        self.assertNotIn('id="show-citations"', html)
        self.assertIn('id="run-highly-cited"', html)
        self.assertIn('id="highly-cited-minimum"', html)
        self.assertIn('data-source="highly_cited"', html)
        self.assertIn('data-view-panel="graph"', html)
        self.assertIn('data-view-panel="discovery"', html)
        self.assertIn('data-view-panel="system"', html)
        self.assertIn('class="review-workspace"', html)
        self.assertIn('id="candidate-preview"', html)
        self.assertIn("function activateView", script)
        self.assertIn("function renderCandidateRow", script)
        self.assertIn("function highlyCitedPipeline", script)
        self.assertIn("function renderClassificationReview", script)
        self.assertIn("function pollApiState", script)
        self.assertIn("function runDiagnostics", script)
        self.assertIn("function removeGraphNode", script)
        self.assertIn("function openRuntimeLogs", script)
        self.assertIn("Math.hypot(candidate.x - other.x", script)
        self.assertIn("node.hitRadius + other.node.hitRadius", script)
        self.assertIn("node-port incoming-port", script)
        self.assertIn("node-port outgoing-port", script)
        self.assertIn("const boundaryPoint = (node, toward)", script)
        self.assertNotIn("candidate-more-actions", script)
        self.assertNotIn("更多操作", script)
        self.assertIn("function sendCandidateFeedback", script)
        self.assertIn("OpenAlex 语义召回", script)
        self.assertIn("JSON.stringify({mode: 'topics'})", script)
        self.assertNotIn("citationsExpanded", script)
        self.assertIn("const visible = focused;", script)
        self.assertIn("log.className = 'task-log'", script)
        self.assertNotIn('id="citation-arrow"', html)
        self.assertNotIn("marker-end:", styles)
        self.assertIn(".edge.focused.outgoing { stroke: #f08a3e; }", styles)
        self.assertIn(".edge.focused.incoming { stroke: var(--citation); }", styles)
        self.assertIn("--cat-10:", styles)

    def test_v14_taxonomy_has_distinct_architecture_and_training_categories(self):
        self.assertEqual(len(build_graph.STANDARD_CATEGORIES), 11)
        self.assertEqual(build_graph.STANDARD_CATEGORIES[0], "01_模型架构与基础组件")
        self.assertEqual(build_graph.STANDARD_CATEGORIES[1], "02_训练方法与优化器")
        self.assertIn("09_通用智能体与自主发现", build_graph.STANDARD_CATEGORIES)

    def test_native_titlebar_is_draggable_without_covering_web_actions(self):
        launcher = (ROOT / "platform" / "macos" / "PaperAtlasLauncher.m").read_text(encoding="utf-8")
        self.assertIn("NSWindowStyleMaskTitled", launcher)
        self.assertNotIn("NSWindowStyleMaskFullSizeContentView", launcher)
        self.assertNotIn("PaperAtlasDragRegion", launcher)
        self.assertIn('@selector(copy:)', launcher)
        self.assertIn('@selector(paste:)', launcher)
        self.assertIn('@"config/discovery-evaluation.json"', launcher)

    def test_automatic_update_does_not_launch_browser_preview(self):
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        update_recipe = makefile.split("\nupdate:\n", 1)[1].split("\n\n", 1)[0]
        preview_recipe = makefile.split("\nupdate-preview: update\n", 1)[1].split("\n\n", 1)[0]
        self.assertNotIn("capture_preview.py", update_recipe)
        self.assertIn("capture_preview.py", preview_recipe)

    def test_manual_preview_uses_native_webkit_instead_of_chrome(self):
        capture = (ROOT / "scripts" / "capture_preview.py").read_text(encoding="utf-8")
        native_capture = (ROOT / "platform" / "macos" / "CapturePreview.m").read_text(encoding="utf-8")
        self.assertNotIn("Google Chrome", capture)
        self.assertNotIn("Chromium", capture)
        self.assertIn("CapturePreview.m", capture)
        self.assertIn("WKWebView", native_capture)

    def test_release_notes_are_generated_from_changelog(self):
        payload = json.loads(
            (ROOT / "web" / "data" / "releases.json").read_text(encoding="utf-8")
        )
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(generate_release_notes.check_generated_files(), [])
        self.assertEqual(payload["current_version"], version)
        self.assertEqual(payload["releases"][0]["version"], version)
        self.assertNotIn("Unreleased", [release["version"] for release in payload["releases"]])


class ReleasePrivacyTests(unittest.TestCase):
    def make_runtime(self, root: Path) -> Path:
        runtime = root / "runtime"
        (runtime / "config").mkdir(parents=True)
        (runtime / "web" / "data").mkdir(parents=True)
        (runtime / "config" / "discovery.json").write_text(json.dumps({
            "topics": [{"label": "private topic"}],
            "arxiv": {"max_age_days": 14},
        }), encoding="utf-8")
        (runtime / "config" / "tasks.json").write_text("{}", encoding="utf-8")
        discovery = {
            "metadata": {},
            "topics": [{"label": "private topic"}],
            "decisions": {"paper": {"status": "accepted"}},
            "candidates": [{"id": "paper", "title": "private candidate"}],
        }
        write_discovery(
            discovery,
            runtime / "web" / "data" / "discovery.json",
            runtime / "web" / "data" / "discovery-data.js",
        )
        (runtime / "web" / "data" / "graph.json").write_text("{}", encoding="utf-8")
        (runtime / "web" / "data" / "graph-data.js").write_text(
            "window.PAPER_GRAPH={};", encoding="utf-8",
        )
        return runtime

    def test_release_runtime_removes_mutable_personal_state(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = self.make_runtime(Path(directory))
            self.assertTrue(prepare_release_seed.privacy_issues(runtime))
            prepare_release_seed.sanitize_runtime(runtime)
            self.assertEqual(prepare_release_seed.privacy_issues(runtime), [])
            config = json.loads((runtime / "config" / "discovery.json").read_text())
            discovery = json.loads((runtime / "web" / "data" / "discovery.json").read_text())
            self.assertEqual(config["topics"], [])
            self.assertEqual(discovery["candidates"], [])
            self.assertEqual(discovery["decisions"], {})
            (runtime / "web" / "data" / "discovery-data.js").write_text(
                "window.PAPER_DISCOVERY={\"candidates\":[{\"id\":\"leak\"}]};\n",
                encoding="utf-8",
            )
            self.assertIn(
                "发布包的候选 JSON 与页面数据不一致",
                prepare_release_seed.privacy_issues(runtime),
            )


if __name__ == "__main__":
    unittest.main()
