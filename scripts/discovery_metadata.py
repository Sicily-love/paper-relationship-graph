"""Metadata reconstruction and validation for discovery candidates."""

from __future__ import annotations

from datetime import datetime, timezone
import re
import urllib.parse

from discovery_utils import compact_text


def abstract_from_inverted_index(index: object) -> str | None:
    """Restore OpenAlex's compact inverted-index abstract into readable text."""
    if not isinstance(index, dict) or not index:
        return None
    positioned: list[tuple[int, str]] = []
    for word, positions in index.items():
        if not isinstance(word, str) or not isinstance(positions, list):
            continue
        for position in positions:
            if isinstance(position, int) and 0 <= position < 10000:
                positioned.append((position, word))
    if not positioned:
        return None
    return compact_text(" ".join(word for _position, word in sorted(positioned)))


def candidate_validation(candidate: dict, now: datetime | None = None) -> dict:
    """Return an explainable confidence score and metadata warnings."""
    now = now or datetime.now(timezone.utc)
    score = 20
    checks: list[str] = []
    warnings: list[str] = []

    title = compact_text(str(candidate.get("title") or ""))
    if len(title) >= 8:
        score += 15
        checks.append("标题完整")
    else:
        warnings.append("标题缺失或过短")

    if candidate.get("authors"):
        score += 12
        checks.append("作者信息完整")
    else:
        warnings.append("缺少作者信息")

    try:
        year = int(candidate.get("year"))
    except (TypeError, ValueError):
        year = 0
    if 1990 <= year <= now.year + 1:
        score += 10
        checks.append("年份合理")
    else:
        warnings.append("年份缺失或异常")

    for field, label, points in (("url", "来源页", 8), ("pdf_url", "PDF 链接", 12)):
        parsed = urllib.parse.urlsplit(str(candidate.get(field) or ""))
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            score += points
            checks.append(f"{label}可用")
        else:
            warnings.append(f"缺少有效{label}")

    sources = set(candidate.get("sources") or [])
    if "arxiv_topic" in sources:
        if candidate.get("arxiv_id"):
            score += 8
            checks.append("arXiv 编号完整")
        else:
            warnings.append("缺少 arXiv 编号")
        if candidate.get("published"):
            score += 5
        relevance_score = int(candidate.get("relevance_score") or 0)
        relevance_threshold = int(candidate.get("relevance_threshold") or 0)
        if relevance_score >= relevance_threshold and relevance_score > 0:
            score += min(8, relevance_score // 10)
            checks.append(f"主题相关性 {relevance_score}")
        elif relevance_threshold:
            warnings.append("主题相关性不足")
    if "shared_reference" in sources:
        support_count = int(candidate.get("support_count") or 0)
        if support_count >= 2:
            score += min(14, 8 + support_count)
            checks.append(f"{support_count} 篇库内论文共同支撑")
        else:
            warnings.append("共同引用支撑不足")
        if int(candidate.get("cited_by_count") or 0) > 0:
            score += 4
    if "highly_cited" in sources:
        cited_by_count = int(candidate.get("cited_by_count") or 0)
        threshold = int(candidate.get("highly_cited_threshold") or 0)
        if cited_by_count >= threshold > 0:
            score += 12
            checks.append(f"OpenAlex 被引 {cited_by_count:,} 次")
        else:
            warnings.append("被引次数未达到高被引阈值")
    if len(sources) > 1:
        score += 8
        checks.append("多个发现来源相互印证")

    arxiv_id = str(candidate.get("arxiv_id") or "")
    match = re.match(r"^(\d{2})(\d{2})\.\d+", arxiv_id)
    if match and year:
        arxiv_year = 2000 + int(match.group(1))
        if abs(arxiv_year - year) > 1:
            score -= 24
            warnings.append(f"年份与 arXiv 编号不一致（编号对应 {arxiv_year} 年）")

    score = max(0, min(100, score))
    has_conflict = any("不一致" in warning or "异常" in warning for warning in warnings)
    label = "高" if score >= 80 and not warnings else "中" if score >= 60 and not has_conflict else "需核验"
    return {
        "confidence": score,
        "confidence_label": label,
        "metadata_checks": checks,
        "metadata_warnings": warnings,
    }
