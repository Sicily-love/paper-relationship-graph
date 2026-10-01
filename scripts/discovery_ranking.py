"""Candidate merging, retention and recommendation scoring."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math

from discovery_utils import candidate_key, normalize_title


def merge_candidates(
    candidates: list[dict],
    previous: dict,
    library_titles: set[str],
    limit: int,
    now: datetime | None = None,
    retention_days: int = 60,
) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    now_iso = now.isoformat()
    previous_by_key = {candidate_key(item): item for item in previous.get("candidates", [])}
    decisions = previous.get("decisions", {})
    merged: dict[str, dict] = {}
    for candidate in candidates:
        if normalize_title(str(candidate.get("title") or "")) in library_titles:
            continue
        key = candidate_key(candidate)
        version = {
            field: candidate.get(field)
            for field in ("id", "arxiv_id", "openalex_id", "doi", "published", "url", "pdf_url")
            if candidate.get(field)
        }
        candidate.setdefault("versions", [version] if version else [])
        existing = merged.get(key)
        if existing:
            combined_sources = sorted(set(existing.get("sources", [])) | set(candidate.get("sources", [])))
            combined_topics = sorted(set(existing.get("topics", [])) | set(candidate.get("topics", [])))
            combined_topic_ids = sorted(set(existing.get("topic_ids", [])) | set(candidate.get("topic_ids", [])))
            combined_score = max(float(existing.get("score", 0)), float(candidate.get("score", 0))) + 10
            if candidate.get("support_count", 0) > existing.get("support_count", 0):
                existing.update({key: value for key, value in candidate.items() if value is not None})
            for field in ("abstract", "authors", "url", "pdf_url", "openalex_id", "published", "year"):
                if not existing.get(field) and candidate.get(field):
                    existing[field] = candidate[field]
            existing["cited_by_count"] = max(
                int(existing.get("cited_by_count") or 0), int(candidate.get("cited_by_count") or 0),
            )
            if candidate.get("highly_cited_threshold"):
                existing["highly_cited_threshold"] = candidate["highly_cited_threshold"]
            existing["sources"] = combined_sources
            existing["topics"] = combined_topics
            existing["topic_ids"] = combined_topic_ids
            existing["score"] = combined_score
            known_versions = {
                candidate_key(item) if isinstance(item, dict) else str(item)
                for item in existing.get("versions", [])
            }
            for item in candidate.get("versions", []):
                if candidate_key(item) not in known_versions:
                    existing.setdefault("versions", []).append(item)
                    known_versions.add(candidate_key(item))
            if existing.get("arxiv_id"):
                existing["id"] = f"arxiv:{existing['arxiv_id']}"
            if len(combined_sources) > 1:
                existing["reason"] = "；".join(
                    reason for reason in (
                        f"被 {existing.get('support_count', 0)} 篇库内论文共同引用"
                        if existing.get("support_count") else None,
                        f"领域高被引 · OpenAlex 被引 {int(existing.get('cited_by_count') or 0):,} 次"
                        if "highly_cited" in combined_sources else None,
                        f"匹配每日主题：{'、'.join(combined_topics)}" if combined_topics else None,
                    ) if reason
                )
            continue
        prior = previous_by_key.get(key, {})
        decision = decisions.get(candidate["id"], decisions.get(key, {}))
        saved_status = decision.get("status", prior.get("status", candidate.get("status", "new")))
        candidate["status"] = "new" if saved_status == "dismissed" else saved_status
        candidate["first_seen"] = prior.get("first_seen", now_iso)
        candidate["last_seen"] = now_iso
        accepted_path = decision.get("accepted_path", prior.get("accepted_path"))
        if accepted_path:
            candidate["accepted_path"] = accepted_path
        merged[key] = candidate

    cutoff = now - timedelta(days=retention_days)
    for key, prior in previous_by_key.items():
        if key in merged or normalize_title(str(prior.get("title") or "")) in library_titles:
            continue
        decision = decisions.get(prior.get("id"), decisions.get(key, {}))
        if decision.get("status", prior.get("status")) != "new":
            continue
        last_seen_text = prior.get("last_seen") or prior.get("first_seen")
        if last_seen_text:
            try:
                if datetime.fromisoformat(str(last_seen_text).replace("Z", "+00:00")) < cutoff:
                    continue
            except ValueError:
                pass
        merged[key] = dict(prior)

    active = [item for item in merged.values() if item.get("status") not in {"rejected", "purged"}]

    def published_timestamp(item: dict) -> float:
        try:
            published = str(item.get("published") or "")
            if published:
                return datetime.fromisoformat(published).timestamp()
        except ValueError:
            pass
        try:
            return datetime(int(item.get("year")), 1, 1, tzinfo=timezone.utc).timestamp()
        except (TypeError, ValueError):
            return 0

    active.sort(key=lambda item: (
        item.get("status") == "accepted", -published_timestamp(item),
        -float(item.get("score", 0)), item.get("title") or "",
    ))
    return active[:limit]


def score_recommendation(candidate: dict, graph: dict, now: datetime | None = None) -> dict:
    """Build a bounded, explainable score without changing newest-first ordering."""
    now = now or datetime.now(timezone.utc)
    relevance = max(0.0, min(100.0, float(candidate.get("relevance_score") or 0)))
    support = max(0, int(candidate.get("support_count") or 0))
    citations = max(0, int(candidate.get("cited_by_count") or 0))
    year = int(candidate.get("year") or now.year)
    age = max(0, now.year - year)
    citation_velocity = citations / max(1, age + 1)
    sources = set(candidate.get("sources") or [])
    category = candidate.get("suggested_category")
    category_counts = {item.get("id"): int(item.get("paper_count") or 0) for item in graph.get("categories", [])}
    largest_category = max(category_counts.values(), default=0)
    category_gap = max(0, largest_category - category_counts.get(category, largest_category))
    components = {
        "topic_relevance": round(relevance * 0.30, 2),
        "shared_evidence": round(min(25.0, support * 5.0), 2),
        "citation_impact": round(min(25.0, math.log10(citation_velocity + 1) * 8.0), 2),
        "source_diversity": round(min(10.0, max(0, len(sources) - 1) * 5.0), 2),
        "category_gap": round(min(10.0, category_gap * 1.5), 2),
    }
    score = round(min(100.0, sum(components.values())), 1)
    explanation = []
    if relevance:
        explanation.append(f"主题相关度 {relevance:.0f}")
    if support:
        explanation.append(f"{support} 篇库内论文共同引用")
    if citations:
        explanation.append(f"被引 {citations:,} 次，按发表年校正")
    if len(sources) > 1:
        explanation.append(f"{len(sources)} 条发现路径相互印证")
    if category_gap:
        explanation.append("补充当前相对稀疏的类别")
    return {
        "recommendation_score": score,
        "ranking_components": components,
        "ranking_explanation": explanation or ["满足基础发现规则"],
    }


def apply_shared_reference_minimum(candidates: list[dict], minimum: int) -> list[dict]:
    """Remove shared-reference provenance that no longer meets the configured threshold."""
    filtered: list[dict] = []
    for original in candidates:
        sources = list(original.get("sources", []))
        if "shared_reference" not in sources or int(original.get("support_count") or 0) >= minimum:
            filtered.append(original)
            continue
        remaining_sources = [source for source in sources if source != "shared_reference"]
        if not remaining_sources:
            continue
        candidate = dict(original)
        candidate["sources"] = remaining_sources
        candidate.pop("support_count", None)
        candidate.pop("supporting_papers", None)
        topics = candidate.get("topics", [])
        reasons = []
        if "highly_cited" in remaining_sources:
            reasons.append(f"领域高被引 · OpenAlex 被引 {int(candidate.get('cited_by_count') or 0):,} 次")
        if topics:
            reasons.append(f"匹配每日主题：{'、'.join(topics)}")
        candidate["reason"] = "；".join(reasons) or "匹配 arXiv 搜索主题"
        filtered.append(candidate)
    return filtered
