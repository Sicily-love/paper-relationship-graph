#!/usr/bin/env python3
"""Shared Paper Atlas application operations for native and HTTP frontends."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import backup_restore
import build_graph
import classify_library
import discover_papers
import library_health
import manage_candidate
import system_diagnostics
import task_center
from discovery_utils import (
    DEFAULT_CONFIG,
    DEFAULT_DISCOVERY_JS,
    DEFAULT_DISCOVERY_JSON,
    DEFAULT_GRAPH,
    load_json,
    candidate_key,
    write_discovery,
    write_text_atomic,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
REMOVED_LIBRARY_DIR = ".paper-atlas-removed"
REMOVED_MANIFEST = "manifest.json"
DISCOVERY_MESSAGES = {
    "topics": "主题论文发现已完成",
    "arxiv": "arXiv 搜索已完成",
    "highly_cited": "领域高被引搜索已完成",
    "shared": "共同引用计算已完成",
}


def topic_id(label: str, index: int) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
    return value[:48] or f"topic-{index + 1}"


def validate_topics(raw_topics: object) -> list[dict]:
    if not isinstance(raw_topics, list) or len(raw_topics) > 20:
        raise ValueError("搜索主题必须是列表，且最多 20 个")
    topics: list[dict] = []
    seen_ids: set[str] = set()
    for index, raw in enumerate(raw_topics):
        if not isinstance(raw, dict):
            raise ValueError("搜索主题格式无效")
        label = str(raw.get("label") or "").strip()
        if not 1 <= len(label) <= 80:
            raise ValueError("每个主题都需要一个不超过 80 字的名称")
        keywords = [str(item).strip() for item in raw.get("keywords", []) if str(item).strip()]
        excluded = [str(item).strip() for item in raw.get("exclude_keywords", []) if str(item).strip()]
        if not 1 <= len(keywords) <= 12 or any(len(item) > 80 for item in keywords):
            raise ValueError(f"“{label}”需要 1–12 个关键词，每个不超过 80 字")
        if len(excluded) > 12 or any(len(item) > 80 for item in excluded):
            raise ValueError(f"“{label}”的排除词最多 12 个，每个不超过 80 字")
        identifier = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(raw.get("id") or "")).strip("-")[:64]
        identifier = identifier or topic_id(label, index)
        base = identifier
        suffix = 2
        while identifier in seen_ids:
            identifier = f"{base}-{suffix}"
            suffix += 1
        seen_ids.add(identifier)
        try:
            maximum = int(raw.get("max_results", 10))
        except (TypeError, ValueError) as error:
            raise ValueError(f"“{label}”的每日数量无效") from error
        if not 1 <= maximum <= 50:
            raise ValueError(f"“{label}”的每日数量需要在 1–50 之间")
        topics.append({
            "id": identifier,
            "label": label,
            "keywords": keywords,
            "exclude_keywords": excluded,
            "enabled": bool(raw.get("enabled", True)),
            "max_results": maximum,
        })
    return topics


def validate_bounded_integer(value: object, minimum: int, maximum: int, label: str) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label}必须是整数") from error
    if not minimum <= result <= maximum:
        raise ValueError(f"{label}需要在 {minimum:,}–{maximum:,} 之间")
    return result


def validate_shared_reference_minimum(value: object) -> int:
    return validate_bounded_integer(value, 2, 20, "共同引用次数下限")


def validate_highly_cited_minimum(value: object) -> int:
    return validate_bounded_integer(value, 1, 1_000_000, "高被引次数下限")


def discovery_mode(value: object) -> str:
    mode = str(value or "arxiv")
    if mode not in DISCOVERY_MESSAGES:
        raise ValueError("未知的论文发现方式")
    return mode


def write_json_atomic(path: Path, data: dict) -> None:
    write_text_atomic(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def clear_new_candidates(data: dict) -> int:
    candidates = data.get("candidates", [])
    retained = [candidate for candidate in candidates if candidate.get("status") != "new"]
    data["candidates"] = retained
    metadata = data.setdefault("metadata", {})
    metadata.update({
        "candidate_count": len(retained),
        "new_count": 0,
        "shared_reference_count": sum(
            "shared_reference" in candidate.get("sources", []) for candidate in retained
        ),
        "arxiv_topic_count": sum("arxiv_topic" in candidate.get("sources", []) for candidate in retained),
        "highly_cited_count": sum("highly_cited" in candidate.get("sources", []) for candidate in retained),
        "cleared_at": datetime.now(timezone.utc).isoformat(),
    })
    return len(candidates) - len(retained)


def validated_discovery() -> dict:
    data = load_json(DEFAULT_DISCOVERY_JSON, {"metadata": {}, "candidates": []})
    for candidate in data.get("candidates", []):
        if candidate.get("suggested_category") not in build_graph.STANDARD_CATEGORIES:
            candidate.update(discover_papers.classify_candidate(candidate))
        candidate.update(discover_papers.candidate_validation(candidate))
    return data


def command_error(result: subprocess.CompletedProcess, fallback: str) -> str:
    output = result.stderr or result.stdout or fallback
    return output.strip().splitlines()[-1]


def discovery_debug_log(limit: int = 80) -> list[dict]:
    path = discover_papers.DEFAULT_DEBUG_LOG
    if not path.exists():
        return []
    events = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def tail_text(path: Path, limit: int = 40_000) -> str:
    """Read the useful tail of a runtime log without loading an unbounded file."""
    if not path.is_file():
        return "尚无日志"
    with path.open("rb") as handle:
        handle.seek(0, 2)
        size = handle.tell()
        handle.seek(max(0, size - limit))
        content = handle.read().decode("utf-8", errors="replace")
    return content.lstrip("\n") or "尚无日志"


def unique_destination(path: Path) -> Path:
    if not path.exists():
        return path
    for index in range(2, 10_000):
        candidate = path.with_name(f"{path.stem} ({index}){path.suffix}")
        if not candidate.exists():
            return candidate
    raise ValueError("移出目录中同名文件过多，请先整理该目录")


class AppServices:
    """Business operations shared by Paper Atlas' two local transports."""

    def __init__(self, papers_dir: Path):
        self.papers_dir = papers_dir.expanduser().resolve()

    def state(self) -> dict:
        config = load_json(DEFAULT_CONFIG, {})
        graph_stat = DEFAULT_GRAPH.stat() if DEFAULT_GRAPH.exists() else None
        return {
            "discovery": validated_discovery(),
            "topics": config.get("topics", []),
            "shared_reference_minimum": int(
                config.get("shared_references", {}).get("min_library_citations", 2)
            ),
            "highly_cited_minimum": int(
                config.get("highly_cited", {}).get("min_citations", 50)
            ),
            "categories": [
                {"id": identifier, "label": re.sub(r"^\d+_", "", identifier)}
                for identifier in build_graph.STANDARD_CATEGORIES
            ],
            "health": library_health.validate_library(self.papers_dir),
            "tasks": task_center.task_state(),
            "classification_review": classify_library.load_review_queue(),
            "graph_revision": (
                f"{graph_stat.st_mtime_ns}:{graph_stat.st_size}" if graph_stat else None
            ),
            "discovery_log": discovery_debug_log(),
        }

    def runtime_logs(self, _body: dict | None = None) -> dict:
        cache = REPO_ROOT / ".cache"
        logs = [
            {
                "id": "operations",
                "label": "操作记录",
                "content": tail_text(cache / "operation-log.jsonl"),
            },
            {
                "id": "discovery",
                "label": "论文发现",
                "content": tail_text(discover_papers.DEFAULT_DEBUG_LOG),
            },
            {
                "id": "application",
                "label": "App 后端",
                "content": tail_text(cache / "paper-atlas-app.log"),
            },
        ]
        for task in task_center.task_state().get("tasks", []):
            if task.get("last_log"):
                logs.append({
                    "id": f"task-{task.get('id')}",
                    "label": f"每日任务 · {task.get('label')}",
                    "content": str(task["last_log"]),
                })
        return {"logs": logs, "generated_at": datetime.now(timezone.utc).isoformat()}

    def remove_graph_node(self, body: dict) -> dict:
        node_id = str(body.get("id") or "").strip()
        graph = load_json(DEFAULT_GRAPH, {"nodes": []})
        node = next((item for item in graph.get("nodes", []) if item.get("id") == node_id), None)
        if node is None:
            raise ValueError("论文节点不存在或已经移出")
        source = (self.papers_dir / str(node.get("path") or "")).resolve()
        try:
            source.relative_to(self.papers_dir)
        except ValueError as error:
            raise ValueError("论文文件路径无效") from error
        if not source.is_file() or source.suffix.lower() not in {".pdf", ".pptx"}:
            raise ValueError("节点对应的论文文件已不存在")

        archive_root = self.papers_dir / REMOVED_LIBRARY_DIR
        destination = unique_destination(archive_root / source.parent.name / source.name)
        destination.parent.mkdir(parents=True, exist_ok=True)
        source.replace(destination)
        try:
            result = self._run_graph_update()
            if result.returncode:
                raise ValueError(command_error(result, "图谱更新失败"))
        except Exception:
            source.parent.mkdir(parents=True, exist_ok=True)
            destination.replace(source)
            raise

        manifest_path = archive_root / REMOVED_MANIFEST
        manifest = load_json(manifest_path, {"version": 1, "items": []})
        if not isinstance(manifest, dict):
            manifest = {"version": 1, "items": []}
        manifest.setdefault("items", []).append({
            "id": node_id,
            "title": node.get("title"),
            "original_path": str(source.relative_to(self.papers_dir)),
            "archived_path": str(destination.relative_to(self.papers_dir)),
            "removed_at": datetime.now(timezone.utc).isoformat(),
        })
        write_json_atomic(manifest_path, manifest)
        return {
            "message": "已从论文图谱移出；原文件保存在可恢复归档中",
            "graph_updated": True,
            "removed_path": str(destination.relative_to(self.papers_dir)),
            "health": library_health.validate_library(self.papers_dir),
        }

    def review_classification(self, body: dict) -> dict:
        item_id = str(body.get("id") or "").strip()
        category = str(body.get("category") or "").strip()
        if category not in build_graph.STANDARD_CATEGORIES:
            raise ValueError("请选择有效的论文类别")
        queue = classify_library.load_review_queue()
        item = next(
            (candidate for candidate in queue.get("items", []) if candidate.get("id") == item_id),
            None,
        )
        if item is None:
            raise ValueError("待审核论文不存在或已处理")
        source = (self.papers_dir / str(item.get("path") or "")).resolve()
        try:
            source.relative_to(self.papers_dir)
        except ValueError as error:
            raise ValueError("待审核论文路径无效") from error
        if not source.is_file() or source.suffix.lower() not in {".pdf", ".pptx"}:
            raise ValueError("待审核论文文件已不存在")
        destination = self.papers_dir / category / source.name
        if destination.exists():
            raise ValueError("目标类别中已有同名文件")
        destination.parent.mkdir(parents=True, exist_ok=True)
        source.replace(destination)
        try:
            result = self._run_graph_update()
            if result.returncode:
                raise ValueError(command_error(result, "图谱更新失败"))
        except Exception:
            destination.replace(source)
            raise
        queue["items"] = [candidate for candidate in queue.get("items", []) if candidate is not item]
        queue["updated_at"] = datetime.now(timezone.utc).isoformat()
        write_json_atomic(classify_library.DEFAULT_REVIEW_QUEUE, queue)
        return {
            "message": "分类已确认并更新图谱",
            "graph_updated": True,
            "classification_review": queue,
            "health": library_health.validate_library(self.papers_dir),
        }

    def save_topics(self, body: dict) -> dict:
        topics = validate_topics(body.get("topics"))
        config = load_json(DEFAULT_CONFIG, {})
        config["topics"] = topics
        write_json_atomic(DEFAULT_CONFIG, config)
        return {"message": "搜索主题已保存", "topics": topics}

    def review_candidate(self, body: dict) -> dict:
        action = str(body.get("action") or "")
        candidate_id = str(body.get("id") or "")
        category = str(body.get("category") or "") or None
        replace_path = None
        if action == "replace":
            replace_node_id = str(body.get("replace_node_id") or "")
            graph = load_json(DEFAULT_GRAPH, {"nodes": []})
            node = next(
                (item for item in graph.get("nodes", []) if item.get("id") == replace_node_id),
                None,
            )
            if node is None:
                raise ValueError("请选择需要替换的库内论文")
            replace_path = str(node.get("path") or "")
            category = str(node.get("category") or "") or category
        data = load_json(DEFAULT_DISCOVERY_JSON, {"metadata": {}, "candidates": []})
        candidate = manage_candidate.commit_decision(
            data, candidate_id, action, self.papers_dir, category,
            DEFAULT_DISCOVERY_JSON, DEFAULT_DISCOVERY_JS,
            replace_path=replace_path,
            cache_path=DEFAULT_CONFIG.parents[1] / ".cache" / "openalex-library.json",
        )
        graph_updated, graph_error = self._refresh_after_review(action)
        if action in {"accept", "replace"}:
            manage_candidate.mark_graph_status(
                data, candidate_id, "complete" if graph_updated else "pending",
                DEFAULT_DISCOVERY_JSON, DEFAULT_DISCOVERY_JS, graph_error,
            )
        return {
            "message": (
                "已加入论文库并更新图谱"
                if action == "accept" and graph_updated
                else "论文已归档；图谱将在下次整理时更新"
                if action == "accept"
                else "已替换库内版本并更新图谱"
                if action == "replace" and graph_updated
                else "新版已写入；图谱将在下次整理时更新"
                if action == "replace"
                else "已暂时移出；下次发现时仍可重新出现"
                if action == "dismiss"
                else "已永久忽略该候选"
                if action == "reject"
                else "已永久忽略并清除引用证据"
            ),
            "graph_updated": graph_updated,
            "graph_error": graph_error,
            "candidate": candidate,
            "discovery": validated_discovery(),
        }

    def candidate_feedback(self, body: dict) -> dict:
        candidate_id = str(body.get("id") or "").strip()
        feedback = str(body.get("feedback") or "").strip()
        if feedback not in {"accurate", "irrelevant", "wrong_category"}:
            raise ValueError("未知的推荐反馈")
        data = load_json(DEFAULT_DISCOVERY_JSON, {"metadata": {}, "candidates": []})
        candidate = next(
            (item for item in data.get("candidates", []) if item.get("id") == candidate_id), None,
        )
        if candidate is None:
            raise ValueError("候选论文不存在")
        entry = {
            "feedback": feedback,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "category": candidate.get("suggested_category"),
            "title": candidate.get("title"),
        }
        data.setdefault("feedback", {})[candidate_key(candidate)] = entry
        candidate["user_feedback"] = feedback
        write_discovery(data, DEFAULT_DISCOVERY_JSON, DEFAULT_DISCOVERY_JS)

        config = load_json(DEFAULT_CONFIG, {})
        category = str(candidate.get("suggested_category") or "")
        if category and feedback in {"accurate", "irrelevant"}:
            tokens = [
                token for token in re.findall(r"[a-z][a-z0-9+.-]{2,}", str(candidate.get("title") or "").lower())
                if token not in discover_papers.PROFILE_STOPWORDS
            ]
            terms = list(dict.fromkeys(
                [" ".join(pair) for pair in zip(tokens, tokens[1:])] + tokens
            ))[:4]
            profile = config.setdefault("feedback_profiles", {}).setdefault(
                category, {"positive_terms": [], "negative_terms": []},
            )
            field = "positive_terms" if feedback == "accurate" else "negative_terms"
            profile[field] = list(dict.fromkeys([*profile.get(field, []), *terms]))[-12:]
            write_json_atomic(DEFAULT_CONFIG, config)
        messages = {
            "accurate": "已记录：推荐准确，后续搜索会参考这篇论文",
            "irrelevant": "已记录：不相关，后续搜索会降低相似结果",
            "wrong_category": "已记录：分类不准确，将纳入诊断记录",
        }
        return {"message": messages[feedback], "discovery": validated_discovery()}

    def _refresh_after_review(self, action: str) -> tuple[bool | None, str | None]:
        if action not in {"accept", "replace"}:
            return None, None
        try:
            result = self._run_graph_update()
        except (subprocess.TimeoutExpired, OSError) as error:
            return False, str(error)
        return result.returncode == 0, (
            None if result.returncode == 0 else command_error(result, "图谱更新失败")
        )

    def _run_graph_update(self) -> subprocess.CompletedProcess:
        return subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "update_library.py"),
                "--papers-dir", str(self.papers_dir),
                "--allow-unclassified",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=360,
            check=False,
        )

    def rebuild_graph(self, _body: dict | None = None) -> dict:
        result = self._run_graph_update()
        if result.returncode:
            raise ValueError(command_error(result, "图谱更新失败"))
        self._complete_pending_graph_updates()
        return {
            "message": "图谱已重新生成",
            "graph_updated": True,
            "health": library_health.validate_library(self.papers_dir),
        }

    def run_diagnostics(self, body: dict | None = None) -> dict:
        report = system_diagnostics.run(
            self.papers_dir, bool((body or {}).get("include_network", True)),
        )
        return {"message": "诊断完成", "diagnostics": report}

    def _complete_pending_graph_updates(self) -> None:
        data = load_json(
            DEFAULT_DISCOVERY_JSON,
            {"metadata": {}, "candidates": [], "decisions": {}},
        )
        pending = {
            candidate_id
            for candidate_id, decision in (data.get("decisions") or {}).items()
            if decision.get("status") in {"accepted", "replaced"}
            and decision.get("graph_status") == "pending"
        }
        if not pending:
            return
        for candidate_id in pending:
            decision = data["decisions"][candidate_id]
            decision["graph_status"] = "complete"
            decision.pop("graph_error", None)
        for candidate in data.get("candidates", []):
            if candidate.get("id") in pending:
                candidate["graph_status"] = "complete"
        write_discovery(data, DEFAULT_DISCOVERY_JSON, DEFAULT_DISCOVERY_JS)

    def manage_tasks(self, body: dict) -> dict:
        action = str(body.get("action") or "state")
        if action == "state":
            return task_center.task_state()
        if action == "run":
            result = task_center.run_task(str(body.get("task_id") or ""), self.papers_dir)
            return {**result, **task_center.task_state()}
        if action == "configure":
            return task_center.configure_tasks({"tasks": body.get("tasks")}, self.papers_dir)
        raise ValueError("未知自动任务操作")

    def manage_backup(self, body: dict) -> dict:
        action = str(body.get("action") or "export")
        if action == "export":
            return {"message": "备份已生成", "backup": backup_restore.create_backup()}
        if action != "restore":
            raise ValueError("未知备份操作")
        backup = backup_restore.validate_backup(body.get("backup"))
        config = dict(backup["config"])
        config["topics"] = validate_topics(config.get("topics"))
        tasks = task_center.validate_config(backup["tasks"])
        result = backup_restore.restore_backup(backup, config, tasks)
        return {**result, "discovery": validated_discovery()}

    def clear_candidates(self, _body: dict | None = None) -> dict:
        data = load_json(DEFAULT_DISCOVERY_JSON, {"metadata": {}, "candidates": []})
        removed = clear_new_candidates(data)
        write_discovery(data, DEFAULT_DISCOVERY_JSON, DEFAULT_DISCOVERY_JS)
        return {
            "message": f"已清空 {removed} 篇待审核候选",
            "removed_count": removed,
            "discovery": validated_discovery(),
        }

    def run_discovery(self, body: dict) -> dict:
        mode = discovery_mode(body.get("mode"))
        arguments = [sys.executable, str(REPO_ROOT / "scripts" / "discover_papers.py")]
        if mode == "topics":
            config = load_json(DEFAULT_CONFIG, {})
            minimum = validate_highly_cited_minimum(
                body.get("min_citations", config.get("highly_cited", {}).get("min_citations", 50))
            )
            if "min_citations" in body:
                config.setdefault("highly_cited", {})["min_citations"] = minimum
                write_json_atomic(DEFAULT_CONFIG, config)
            arguments.append("--skip-shared")
        elif mode == "arxiv":
            arguments.extend(("--skip-shared", "--skip-highly-cited"))
        elif mode == "highly_cited":
            config = load_json(DEFAULT_CONFIG, {})
            minimum = validate_highly_cited_minimum(
                body.get("min_citations", config.get("highly_cited", {}).get("min_citations", 50))
            )
            config.setdefault("highly_cited", {})["min_citations"] = minimum
            write_json_atomic(DEFAULT_CONFIG, config)
            arguments.extend(("--skip-arxiv", "--skip-shared"))
        else:
            config = load_json(DEFAULT_CONFIG, {})
            minimum = validate_shared_reference_minimum(body.get("min_library_citations", 2))
            config.setdefault("shared_references", {})["min_library_citations"] = minimum
            write_json_atomic(DEFAULT_CONFIG, config)
            arguments.extend(("--skip-arxiv", "--skip-highly-cited"))
        result = subprocess.run(
            arguments,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=360,
            check=False,
        )
        if result.returncode:
            raise ValueError(command_error(result, "论文发现失败"))
        return {
            "message": DISCOVERY_MESSAGES[mode],
            "mode": mode,
            "discovery": validated_discovery(),
        }
