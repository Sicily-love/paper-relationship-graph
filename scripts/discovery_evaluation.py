#!/usr/bin/env python3
"""Run Paper Atlas' deterministic offline discovery quality baseline."""

from __future__ import annotations

import argparse
import copy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import discover_papers
from discovery_utils import load_json, normalize_title


DEFAULT_CORPUS = Path(__file__).resolve().parents[1] / "config" / "discovery-evaluation.json"


def parse_day(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def evaluate_case(case: dict, reference_time: datetime) -> tuple[bool, dict, str]:
    candidate = copy.deepcopy(case.get("candidate") or {})
    pipeline = str(case.get("pipeline") or "")
    settings = case.get("settings") or {}
    reason = ""
    included = False
    if pipeline == "arxiv":
        published = parse_day(candidate.get("published"))
        cutoff = reference_time - timedelta(days=int(settings.get("max_age_days", 14)))
        relevance = discover_papers.candidate_relevance(candidate, case.get("topic") or {})
        candidate.update({key: value for key, value in relevance.items() if key != "relevant"})
        included = bool(published and published >= cutoff and relevance["relevant"])
        reason = "时间窗和主题均通过" if included else "超过时间窗或主题证据不足"
    elif pipeline == "highly_cited":
        minimum = max(1, int(settings.get("min_citations", 50)))
        included = int(candidate.get("cited_by_count") or 0) >= minimum
        reason = f"被引 {int(candidate.get('cited_by_count') or 0)} / 下限 {minimum}"
    elif pipeline == "shared_reference":
        minimum = max(2, int(settings.get("min_library_citations", 2)))
        included = int(candidate.get("support_count") or 0) >= minimum
        reason = f"共同引用 {int(candidate.get('support_count') or 0)} / 下限 {minimum}"
    else:
        reason = "未知评测管线"
    if included:
        candidate.setdefault("score", 50)
        candidate.setdefault("status", "new")
        candidate.update(discover_papers.classify_candidate(candidate))
    return included, candidate, reason


def evaluate(corpus: dict) -> dict:
    reference_time = parse_day(corpus.get("reference_time")) or datetime.now(timezone.utc)
    cases = corpus.get("cases") if isinstance(corpus.get("cases"), list) else []
    results = []
    predicted_candidates = []
    true_positive = false_positive = false_negative = true_negative = 0
    category_total = category_correct = 0
    for case in cases:
        if not isinstance(case, dict):
            continue
        actual, candidate, reason = evaluate_case(case, reference_time)
        expected = bool(case.get("expected_recommended"))
        if actual and expected:
            true_positive += 1
        elif actual:
            false_positive += 1
        elif expected:
            false_negative += 1
        else:
            true_negative += 1
        expected_category = str(case.get("expected_category") or "")
        category_match = None
        if expected and actual and expected_category:
            category_total += 1
            category_match = candidate.get("suggested_category") == expected_category
            category_correct += int(category_match)
        if actual:
            predicted_candidates.append(candidate)
        results.append({
            "id": case.get("id"),
            "pipeline": case.get("pipeline"),
            "title": candidate.get("title"),
            "expected": expected,
            "actual": actual,
            "passed": expected == actual and category_match is not False,
            "category_match": category_match,
            "reason": reason,
        })

    merged = discover_papers.merge_candidates(
        predicted_candidates, {}, set(), 100, reference_time, 60,
    )
    expected_keys = {
        discover_papers.candidate_key(case.get("candidate") or {})
        for case in cases if case.get("expected_recommended")
    }
    actual_keys = {discover_papers.candidate_key(candidate) for candidate in merged}
    expected_unique = len(expected_keys)
    dedupe_accuracy = 1.0 if not expected_unique else min(expected_unique, len(actual_keys & expected_keys)) / expected_unique
    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 1.0
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 1.0
    classification_accuracy = category_correct / category_total if category_total else 1.0
    passed = all(result["passed"] for result in results) and dedupe_accuracy == 1.0
    return {
        "status": "passed" if passed else "failed",
        "corpus_version": corpus.get("version"),
        "reference_time": reference_time.isoformat(),
        "case_count": len(results),
        "metrics": {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "classification_accuracy": round(classification_accuracy, 4),
            "dedupe_accuracy": round(dedupe_accuracy, 4),
            "true_positive": true_positive,
            "false_positive": false_positive,
            "false_negative": false_negative,
            "true_negative": true_negative,
            "merged_candidate_count": len(merged),
        },
        "cases": results,
    }


def run(path: Path = DEFAULT_CORPUS) -> dict:
    corpus = load_json(path, {})
    if not isinstance(corpus, dict) or not isinstance(corpus.get("cases"), list):
        raise ValueError("论文发现评测集格式无效")
    return evaluate(corpus)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = run(args.corpus)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        metrics = report["metrics"]
        print(
            f"评测 {report['status']}：precision={metrics['precision']:.2%} "
            f"recall={metrics['recall']:.2%} classification={metrics['classification_accuracy']:.2%} "
            f"dedupe={metrics['dedupe_accuracy']:.2%}"
        )
    raise SystemExit(0 if report["status"] == "passed" else 1)


if __name__ == "__main__":
    main()
