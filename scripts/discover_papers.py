#!/usr/bin/env python3
"""Discover recent, highly cited, and shared-reference papers for the library."""

from __future__ import annotations

import argparse
import http.client
import json
import math
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path

from discovery_utils import (
    DEFAULT_CONFIG,
    DEFAULT_DISCOVERY_JS,
    DEFAULT_DISCOVERY_JSON,
    DEFAULT_GRAPH,
    candidate_key,
    compact_text,
    load_json,
    normalize_title,
    write_discovery,
)


ARXIV_API = "https://export.arxiv.org/api/query"
OPENALEX_API = "https://api.openalex.org/works"
USER_AGENT = "PaperAtlas/1.0 (local research library discovery)"
ATOM = {"atom": "http://www.w3.org/2005/Atom"}

CATEGORY_LABELS = {
    "01_模型架构与训练优化": "模型架构与训练优化",
    "02_注意力机制与长上下文": "注意力机制与长上下文",
    "03_MoE与稀疏模型": "MoE 与稀疏模型",
    "04_量化与低精度计算": "量化与低精度计算",
    "05_分布式训练与数据基础设施": "分布式训练与数据基础设施",
    "06_GPU内核_编译器与性能工程": "GPU 内核、编译器与性能工程",
    "07_GPU内核智能体与自动调优": "GPU 内核智能体与自动调优",
    "08_通用智能体与自主学习": "通用智能体与自主学习",
    "09_生成模型与视频系统": "生成模型与视频系统",
    "10_大模型技术报告与推理训练": "大模型技术报告与推理训练",
}

# These phrases encode the same primary-topic boundaries as the paper-organizer
# skill. They favor the application domain for cross-disciplinary work: for
# example, kernel-generation agents belong to category 06.
CATEGORY_RULES = {
    "01_模型架构与训练优化": (
        "transformer architecture", "vision transformer", "positional encoding",
        "normalization", "optimizer", "regularization", "knowledge distillation",
        "activation function", "residual connection", "training method", "scaling laws",
        "automatic differentiation", "convolutional network", "convolutional networks",
        "neural network", "language model", "language modeling", "long short-term memory",
        "speech recognition", "u-net", "stochastic optimization", "pointer sentinel",
    ),
    "02_注意力机制与长上下文": (
        "attention", "long context", "long-context", "context window", "kv cache",
        "flashattention", "sageattention", "sparse attention", "block attention",
        "linear attention", "ring attention", "memory attention",
        "sparse transformer", "sparse transformers", "pagedattention", "multi-query", "non-local neural",
    ),
    "03_MoE与稀疏模型": (
        "mixture of experts", "mixture-of-experts", "moe", "expert routing",
        "expert parallel", "sparse model", "sparse experts", "load balancing expert",
    ),
    "04_量化与低精度计算": (
        "quantization", "quantized", "low precision", "low-precision", "mixed precision",
        "int8", "int4", "fp8", "fp4", "bitnet", "weight-only", "post-training quantization",
    ),
    "05_分布式训练与数据基础设施": (
        "distributed training", "data parallel", "model parallel", "pipeline parallel",
        "tensor parallel", "fsdp", "megatron", "collective communication",
        "all-reduce", "training infrastructure", "cluster scheduling",
        "distributed systems", "data pipeline", "data loader", "dataloader",
        "pretraining data", "pre-training data", "data curation", "checkpoint loading",
        "storage system", "data preprocessing", "data mixture",
    ),
    "06_GPU内核_编译器与性能工程": (
        "gpu kernel", "cuda kernel", "triton kernel", "kernel optimization",
        "kernel fusion", "tensor compiler", "gpu compiler",
        "cuda optimization", "ptx", "gpu benchmark", "code generation for gpu",
        "compiler optimization", "operator fusion", "kernel scheduling", "gpu kernels",
        "triton", "gpu programming", "gpu compilation", "gpu offload",
    ),
    "07_GPU内核智能体与自动调优": (
        "gpu kernel agent", "cuda agent", "kernel agent", "kernel agents",
        "agentic kernel", "kernel generation agent", "kernel optimization agent",
        "autonomous gpu kernel", "multi-agent kernel", "kernel design agents",
        "kernel harness", "automatic kernel optimization", "llm-based gpu kernel",
    ),
    "08_通用智能体与自主学习": (
        "ai agent", "llm agent", "agentic", "multi-agent", "autonomous agent",
        "tool use", "tool-use", "planning agent", "research agent", "self-play",
        "autonomous search", "computer use", "web agent",
    ),
    "09_生成模型与视频系统": (
        "video generation", "text-to-video", "image-to-video", "video diffusion",
        "diffusion transformer", "frame interpolation", "video inference",
        "world model video", "streaming video generation", "video model", "diffusion model",
    ),
    "10_大模型技术报告与推理训练": (
        "technical report", "reasoning model", "reasoning training", "reasoning llm",
        "reinforcement learning for reasoning", "rlhf", "grpo", "large language model report",
        "foundation model", "inference-time scaling", "test-time scaling",
    ),
}

ML_DOMAIN_ANCHORS = (
    "machine learning", "deep learning", "neural network", "neural networks",
    "language model", "llm", "transformer", "attention", "inference", "training",
    "convolution", "cnn", "gpu", "accelerator", "model compression", "generative model",
)

TOPIC_DOMAIN_ANCHORS = {
    "category-01-model-architecture": ML_DOMAIN_ANCHORS,
    "category-02-attention-context": ("attention", "transformer", "language model", "llm", "kv cache"),
    "category-03-moe-sparse": ("mixture of experts", "moe", "expert", "language model", "transformer"),
    "category-04-quantization": ML_DOMAIN_ANCHORS,
    "category-05-distributed-data": ("distributed", "training", "gpu", "model", "checkpoint", "data pipeline"),
    "category-06-gpu-performance": ("gpu", "cuda", "kernel", "compiler", "triton", "tensor"),
    "category-07-kernel-agents": ("gpu", "cuda", "kernel", "compiler", "agent", "llm"),
    "category-08-general-agents": ("agent", "llm", "language model", "tool use", "autonomous"),
    "category-09-generative-video": ("video", "diffusion", "generative", "frame", "transformer"),
    "category-10-model-reports": ("language model", "llm", "reasoning", "foundation model", "training"),
}


def category_label(category: str) -> str:
    return CATEGORY_LABELS.get(category, re.sub(r"^\d+_", "", category))


def phrase_score(text: str, phrases: tuple[str, ...], weight: float) -> float:
    normalized = f" {normalize_title(text)} "
    return sum(weight for phrase in phrases if f" {normalize_title(phrase)} " in normalized)


def classify_candidate(candidate: dict) -> dict:
    """Assign one explainable primary category from title, abstract and library support."""
    title = str(candidate.get("title") or "")
    abstract = str(candidate.get("abstract") or "")
    topics = " ".join(str(topic) for topic in candidate.get("topics") or [])
    scores = {
        category: phrase_score(title, phrases, 8)
        + phrase_score(abstract, phrases, 2)
        + phrase_score(topics, phrases, 4)
        for category, phrases in CATEGORY_RULES.items()
    }
    support_counts: dict[str, int] = defaultdict(int)
    for paper in candidate.get("supporting_papers") or []:
        category = str(paper.get("category") or "")
        if category in scores:
            support_counts[category] += 1
            scores[category] += 3

    combined = f" {normalize_title(' '.join((title, abstract, topics)))} "
    video_category = "09_生成模型与视频系统"
    kernel_category = "06_GPU内核_编译器与性能工程"
    kernel_agent_category = "07_GPU内核智能体与自动调优"
    attention_category = "02_注意力机制与长上下文"
    if any(marker in combined for marker in (" video generation ", " text to video ", " image to video ")):
        scores[video_category] += 24
    kernel_markers = (" gpu kernel ", " cuda kernel ", " triton kernel ", " ptx ")
    agent_markers = (" agent ", " agentic ", " multi agent ", " autonomous ", " llm based ")
    if any(marker in combined for marker in kernel_markers):
        if any(marker in combined for marker in agent_markers):
            scores[kernel_agent_category] += 32
        else:
            scores[kernel_category] += 24
    if " attention " in combined and any(marker in combined for marker in (" quantization ", " quantized ", " low precision ")):
        scores[attention_category] += 12

    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    category, top_score = ranked[0]
    runner_up = ranked[1][1]
    if top_score <= 0:
        return {
            "suggested_category": "",
            "category_label": "待确认类别",
            "category_confidence": "需确认",
            "category_reason": "标题与摘要尚不足以判断主类别",
        }

    gap = top_score - runner_up
    confidence = "高" if top_score >= 16 and gap >= 6 else "中" if top_score >= 6 and gap >= 2 else "需确认"
    evidence = []
    if phrase_score(title, CATEGORY_RULES[category], 1):
        evidence.append("标题与类别特征匹配")
    elif phrase_score(abstract, CATEGORY_RULES[category], 1):
        evidence.append("摘要与类别特征匹配")
    if support_counts.get(category):
        evidence.append(f"{support_counts[category]} 篇同类库内论文共同支撑")
    if not evidence:
        evidence.append("搜索主题与类别匹配")
    return {
        "suggested_category": category,
        "category_label": category_label(category),
        "category_confidence": confidence,
        "category_reason": "；".join(evidence),
    }


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


def topic_query(topic: dict) -> str:
    """Build a safe arXiv query from human-friendly keywords."""
    keywords = [compact_text(str(item)) for item in topic.get("keywords", []) if compact_text(str(item))]
    if keywords:
        terms = []
        for keyword in keywords:
            escaped = keyword.replace("\\", "\\\\").replace('"', '\\"')
            terms.extend((f'ti:"{escaped}"', f'abs:"{escaped}"'))
        query = "(" + " OR ".join(terms) + ")"
    else:
        query = compact_text(str(topic.get("query") or ""))
    if not query:
        raise ValueError(f"主题“{topic.get('label') or '未命名'}”没有关键词")
    excluded = [compact_text(str(item)) for item in topic.get("exclude_keywords", []) if compact_text(str(item))]
    if excluded:
        terms = []
        for keyword in excluded:
            escaped = keyword.replace("\\", "\\\\").replace('"', '\\"')
            terms.append(f'all:"{escaped}"')
        query += " ANDNOT (" + " OR ".join(terms) + ")"
    return query


def candidate_relevance(candidate: dict, topic: dict) -> dict:
    """Score topical relevance and explain why an arXiv result was retained."""
    title = f" {normalize_title(str(candidate.get('title') or ''))} "
    abstract = f" {normalize_title(str(candidate.get('abstract') or ''))} "
    keywords = [
        normalize_title(str(value)) for value in topic.get("keywords", [])
        if normalize_title(str(value))
    ]
    if not keywords:
        return {
            "relevance_score": 50,
            "relevance_label": "中",
            "relevance_evidence": ["arXiv 查询匹配"],
            "relevance_threshold": 0,
            "relevant": True,
        }
    title_hits = [keyword for keyword in keywords if f" {keyword} " in title]
    abstract_hits = [keyword for keyword in keywords if f" {keyword} " in abstract]
    all_hits = sorted(set(title_hits + abstract_hits))
    score = min(64, len(title_hits) * 32) + min(36, len(abstract_hits) * 12)
    if len(all_hits) >= 2:
        score += 10
    if any(" " in keyword for keyword in title_hits):
        score += 8

    topic_id = str(topic.get("id") or "")
    anchors = TOPIC_DOMAIN_ANCHORS.get(topic_id, ())
    title_anchors = [anchor for anchor in anchors if f" {normalize_title(anchor)} " in title]
    abstract_anchors = [anchor for anchor in anchors if f" {normalize_title(anchor)} " in abstract]
    if title_anchors:
        score += 14
    elif abstract_anchors:
        score += 8
    score = min(100, score)
    threshold = int(topic.get("min_relevance_score", 40 if anchors else 24))
    relevant = bool(all_hits) and score >= threshold and (not anchors or bool(title_anchors or abstract_anchors))
    evidence = []
    if title_hits:
        evidence.append("标题命中 " + "、".join(title_hits[:3]))
    if abstract_hits:
        evidence.append("摘要命中 " + "、".join(abstract_hits[:3]))
    anchor_hits = title_anchors or abstract_anchors
    if anchor_hits:
        evidence.append("领域信号 " + "、".join(anchor_hits[:3]))
    if not evidence:
        evidence.append("未发现足够的主题证据")
    return {
        "relevance_score": score,
        "relevance_label": "高" if score >= 70 else "中" if score >= threshold else "低",
        "relevance_evidence": evidence,
        "relevance_threshold": threshold,
        "relevant": relevant,
    }


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


def request_bytes(url: str, timeout: int = 45, attempts: int = 3) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            if error.code < 500 and error.code != 429:
                raise
            last_error = error
        except (urllib.error.URLError, TimeoutError, http.client.RemoteDisconnected, ConnectionResetError) as error:
            last_error = error
        if attempt < attempts - 1:
            time.sleep(1.5 * (2**attempt))
    raise urllib.error.URLError(last_error or "request failed")


def request_json(url: str) -> dict:
    return json.loads(request_bytes(url).decode("utf-8"))


def arxiv_id_from_url(url: str) -> str | None:
    value = url.strip().rstrip("/")
    lowered = value.lower()
    for marker in ("arxiv.org/abs/", "arxiv.org/pdf/"):
        if marker in lowered:
            value = value[lowered.index(marker) + len(marker) :]
            break
    else:
        if "://" in value:
            value = value.rsplit("/", 1)[-1]
    value = re.sub(r"\.pdf$", "", value, flags=re.IGNORECASE)
    value = re.sub(r"v\d+$", "", value, flags=re.IGNORECASE)
    return value or None


def parse_arxiv_feed(payload: bytes, topic: dict, cutoff: datetime) -> list[dict]:
    root = ET.fromstring(payload)
    candidates: list[dict] = []
    for entry in root.findall("atom:entry", ATOM):
        published_text = entry.findtext("atom:published", default="", namespaces=ATOM)
        if not published_text:
            continue
        published = datetime.fromisoformat(published_text.replace("Z", "+00:00"))
        if published < cutoff:
            continue
        entry_url = entry.findtext("atom:id", default="", namespaces=ATOM)
        arxiv_id = arxiv_id_from_url(entry_url)
        if not arxiv_id:
            continue
        links = {
            link.attrib.get("title") or link.attrib.get("rel"): link.attrib.get("href")
            for link in entry.findall("atom:link", ATOM)
        }
        authors = [
            compact_text(author.findtext("atom:name", default="", namespaces=ATOM))
            for author in entry.findall("atom:author", ATOM)
        ]
        candidate = {
                "id": f"arxiv:{arxiv_id}",
                "arxiv_id": arxiv_id,
                "title": compact_text(entry.findtext("atom:title", default="", namespaces=ATOM)),
                "authors": authors,
                "abstract": compact_text(entry.findtext("atom:summary", default="", namespaces=ATOM)),
                "year": published.year,
                "published": published.date().isoformat(),
                "url": entry_url,
                "pdf_url": links.get("pdf") or f"https://arxiv.org/pdf/{arxiv_id}",
                "sources": ["arxiv_topic"],
                "topics": [topic["label"]],
                "reason": f"匹配每日主题：{topic['label']}",
                "score": 50,
                "status": "new",
            }
        relevance = candidate_relevance(candidate, topic)
        if not relevance.pop("relevant"):
            continue
        candidate.update(relevance)
        candidate["score"] = 50 + relevance["relevance_score"] / 2
        candidate["reason"] = f"匹配每日主题：{topic['label']} · {relevance['relevance_evidence'][0]}"
        candidates.append(candidate)
    return candidates


def discover_arxiv(config: dict, cutoff: datetime) -> tuple[list[dict], list[str]]:
    candidates: list[dict] = []
    errors: list[str] = []
    topics = [topic for topic in config.get("topics", []) if topic.get("enabled", True)]
    delay = float(config.get("arxiv", {}).get("request_delay_seconds", 3))
    for index, topic in enumerate(topics):
        try:
            query = topic_query(topic)
        except ValueError as error:
            errors.append(f"arXiv / {topic.get('label', '未命名主题')}: {error}")
            continue
        params = urllib.parse.urlencode(
            {
                "search_query": query,
                "start": 0,
                "max_results": int(topic.get("max_results", 10)),
                "sortBy": "submittedDate",
                "sortOrder": "descending",
            }
        )
        try:
            payload = request_bytes(f"{ARXIV_API}?{params}")
            candidates.extend(parse_arxiv_feed(payload, topic, cutoff))
        except (urllib.error.URLError, TimeoutError, ET.ParseError) as error:
            errors.append(f"arXiv / {topic['label']}: {error}")
        if index < len(topics) - 1 and delay > 0:
            time.sleep(delay)
    return candidates, errors


def author_names(work: dict, limit: int = 8) -> list[str]:
    names = []
    for authorship in work.get("authorships") or []:
        name = compact_text(str((authorship.get("author") or {}).get("display_name") or ""))
        if name:
            names.append(name)
    return names[:limit]


def arxiv_id_from_work(work: dict) -> str | None:
    ids = work.get("ids") or {}
    arxiv_url = ids.get("arxiv")
    if arxiv_url:
        return arxiv_id_from_url(str(arxiv_url))
    doi = str(ids.get("doi") or "")
    marker = "10.48550/arxiv."
    if marker in doi.lower():
        return doi.lower().split(marker, 1)[1]
    location = work.get("primary_location") or {}
    for url in (location.get("landing_page_url"), location.get("pdf_url")):
        if url and "arxiv.org/" in str(url):
            return arxiv_id_from_url(str(url))
    return None


def work_score(node: dict, work: dict) -> float:
    title_score = SequenceMatcher(
        None,
        normalize_title(str(node.get("title") or "")),
        normalize_title(str(work.get("display_name") or "")),
    ).ratio()
    node_author_tokens = set(normalize_title(str(node.get("authors") or "")).split())
    work_author_tokens = set(normalize_title(" ".join(author_names(work))).split())
    author_score = (
        len(node_author_tokens & work_author_tokens) / min(len(node_author_tokens), len(work_author_tokens))
        if node_author_tokens and work_author_tokens
        else 0
    )
    return title_score * 0.85 + author_score * 0.15


def resolve_openalex_work(node: dict, mailto: str) -> dict | None:
    params = {
        "search": node["title"],
        "per-page": 5,
        "select": "id,display_name,publication_year,referenced_works,ids,cited_by_count,authorships,primary_location",
        "mailto": mailto,
    }
    payload = request_json(f"{OPENALEX_API}?{urllib.parse.urlencode(params)}")
    results = payload.get("results") or []
    if not results:
        return None
    best = max(results, key=lambda work: work_score(node, work))
    return best if work_score(node, best) >= 0.80 else None


def fetch_openalex_works(work_ids: list[str], mailto: str) -> list[dict]:
    works: list[dict] = []
    for start in range(0, len(work_ids), 50):
        batch = [work_id.rsplit("/", 1)[-1] for work_id in work_ids[start : start + 50]]
        params = {
            "filter": "openalex_id:" + "|".join(batch),
            "per-page": len(batch),
            "select": "id,display_name,publication_year,ids,cited_by_count,authorships,primary_location,abstract_inverted_index",
            "mailto": mailto,
        }
        payload = request_json(f"{OPENALEX_API}?{urllib.parse.urlencode(params)}")
        works.extend(payload.get("results") or [])
    return works


def openalex_topic_query(topic: dict) -> str:
    """Build a broad Boolean query whose results can then be ranked by citations."""
    keywords = [compact_text(str(value)) for value in topic.get("keywords", []) if compact_text(str(value))]
    if not keywords:
        raise ValueError(f"主题“{topic.get('label') or '未命名'}”没有关键词")

    def quoted(value: str) -> str:
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"' if " " in escaped else escaped

    query = "(" + " OR ".join(quoted(value) for value in keywords) + ")"
    excluded = [
        compact_text(str(value)) for value in topic.get("exclude_keywords", [])
        if compact_text(str(value))
    ]
    if excluded:
        query += " NOT (" + " OR ".join(quoted(value) for value in excluded) + ")"
    return query


def discover_highly_cited(config: dict) -> tuple[list[dict], list[str]]:
    """Find established topic papers, independently of their publication date."""
    settings = config.get("highly_cited", {})
    if not settings.get("enabled", True):
        return [], []
    minimum = max(1, int(settings.get("min_citations", 50)))
    maximum_per_topic = min(20, max(1, int(settings.get("max_per_topic", 5))))
    maximum = min(100, max(1, int(settings.get("max_candidates", 20))))
    delay = max(0.0, float(settings.get("request_delay_seconds", 0.12)))
    mailto = str(
        os.environ.get("OPENALEX_MAILTO")
        or settings.get("mailto")
        or config.get("shared_references", {}).get("mailto")
        or "paper-atlas@example.com"
    )
    topics = [topic for topic in config.get("topics", []) if topic.get("enabled", True)]
    candidates: list[dict] = []
    errors: list[str] = []
    for index, topic in enumerate(topics):
        try:
            query = openalex_topic_query(topic)
            params = {
                "search": query,
                "sort": "cited_by_count:desc",
                "per-page": min(100, max(25, maximum_per_topic * 5)),
                "select": (
                    "id,display_name,publication_year,publication_date,ids,cited_by_count,"
                    "authorships,primary_location,abstract_inverted_index"
                ),
                "mailto": mailto,
            }
            works = request_json(f"{OPENALEX_API}?{urllib.parse.urlencode(params)}").get("results") or []
        except (ValueError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            errors.append(f"OpenAlex 高被引 / {topic.get('label', '未命名主题')}: {error}")
            continue

        retained = 0
        for work in works:
            cited_by_count = int(work.get("cited_by_count") or 0)
            title = compact_text(str(work.get("display_name") or ""))
            work_id = str(work.get("id") or "")
            if not work_id or not title or cited_by_count < minimum:
                continue
            arxiv_id = arxiv_id_from_work(work)
            location = work.get("primary_location") or {}
            ids = work.get("ids") or {}
            url = location.get("landing_page_url") or ids.get("doi") or work_id
            pdf_url = location.get("pdf_url") or (f"https://arxiv.org/pdf/{arxiv_id}" if arxiv_id else None)
            candidate = {
                "id": f"openalex:{work_id.rsplit('/', 1)[-1]}",
                "openalex_id": work_id,
                "arxiv_id": arxiv_id,
                "title": title,
                "authors": author_names(work),
                "abstract": abstract_from_inverted_index(work.get("abstract_inverted_index")),
                "year": work.get("publication_year"),
                "published": work.get("publication_date"),
                "url": url,
                "pdf_url": pdf_url,
                "cited_by_count": cited_by_count,
                "highly_cited_threshold": minimum,
                "sources": ["highly_cited"],
                "topics": [topic["label"]],
                "reason": f"领域高被引 · OpenAlex 被引 {cited_by_count:,} 次 · 匹配 {topic['label']}",
                "score": 70 + min(40, math.log10(max(1, cited_by_count)) * 10),
                "status": "new",
            }
            relevance = candidate_relevance(candidate, topic)
            if not relevance.pop("relevant"):
                continue
            candidate.update(relevance)
            candidate["score"] += relevance["relevance_score"] / 4
            candidates.append(candidate)
            retained += 1
            if retained >= maximum_per_topic:
                break
        if index < len(topics) - 1 and delay > 0:
            time.sleep(delay)

    candidates.sort(
        key=lambda item: (-int(item.get("cited_by_count") or 0), -float(item.get("score") or 0), item["title"])
    )
    return candidates[:maximum], errors


def load_openalex_cache(path: Path) -> dict:
    return load_json(path, {"version": 1, "nodes": {}})  # type: ignore[return-value]


def discover_shared_references(
    graph: dict,
    config: dict,
    cache_path: Path,
) -> tuple[list[dict], list[str], dict]:
    settings = config.get("shared_references", {})
    if not settings.get("enabled", True):
        return [], [], {"matched_library_papers": 0, "unmatched_library_papers": 0}

    mailto = str(os.environ.get("OPENALEX_MAILTO") or settings.get("mailto") or "paper-atlas@example.com")
    delay = float(settings.get("request_delay_seconds", 0.12))
    minimum = int(settings.get("min_library_citations", 2))
    maximum = int(settings.get("max_candidates", 30))
    cache = load_openalex_cache(cache_path)
    node_cache = cache.setdefault("nodes", {})
    errors: list[str] = []
    matched: dict[str, dict] = {}

    for index, node in enumerate(graph.get("nodes", [])):
        cache_key = str(node.get("sha256") or normalize_title(node["title"]))
        cached = node_cache.get(cache_key)
        if cached is None:
            try:
                work = resolve_openalex_work(node, mailto)
                cached = {
                    "title": node["title"],
                    "work": work,
                    "resolved_at": datetime.now(timezone.utc).isoformat(),
                }
                node_cache[cache_key] = cached
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
                errors.append(f"OpenAlex / {node['title']}: {error}")
                continue
            if delay > 0 and index < len(graph.get("nodes", [])) - 1:
                time.sleep(delay)
        work = cached.get("work") if isinstance(cached, dict) else None
        if work:
            matched[node["id"]] = work

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    library_work_ids = {work["id"] for work in matched.values() if work.get("id")}
    supporting_nodes: dict[str, set[str]] = defaultdict(set)
    for node_id, work in matched.items():
        for referenced_id in work.get("referenced_works") or []:
            if referenced_id not in library_work_ids:
                supporting_nodes[referenced_id].add(node_id)

    ranked_ids = sorted(
        (work_id for work_id, node_ids in supporting_nodes.items() if len(node_ids) >= minimum),
        key=lambda work_id: (-len(supporting_nodes[work_id]), work_id),
    )[: maximum * 3]
    try:
        works = fetch_openalex_works(ranked_ids, mailto) if ranked_ids else []
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        errors.append(f"OpenAlex / candidate metadata: {error}")
        works = []

    nodes_by_id = {node["id"]: node for node in graph.get("nodes", [])}
    library_titles = {normalize_title(node["title"]) for node in graph.get("nodes", [])}
    candidates = []
    for work in works:
        work_id = work.get("id")
        title = compact_text(str(work.get("display_name") or ""))
        if not work_id or not title or normalize_title(title) in library_titles:
            continue
        support = sorted(
            (nodes_by_id[node_id] for node_id in supporting_nodes.get(work_id, set())),
            key=lambda node: node["title"],
        )
        support_count = len(support)
        if support_count < minimum:
            continue
        arxiv_id = arxiv_id_from_work(work)
        location = work.get("primary_location") or {}
        url = location.get("landing_page_url") or work_id
        pdf_url = location.get("pdf_url") or (f"https://arxiv.org/pdf/{arxiv_id}" if arxiv_id else None)
        candidate = {
            "id": f"openalex:{str(work_id).rsplit('/', 1)[-1]}",
            "openalex_id": work_id,
            "arxiv_id": arxiv_id,
            "title": title,
            "authors": author_names(work),
            "abstract": abstract_from_inverted_index(work.get("abstract_inverted_index")),
            "year": work.get("publication_year"),
            "published": None,
            "url": url,
            "pdf_url": pdf_url,
            "cited_by_count": int(work.get("cited_by_count") or 0),
            "sources": ["shared_reference"],
            "topics": [],
            "support_count": support_count,
            "supporting_papers": [
                {"id": node["id"], "title": node["title"], "category": node["category"]}
                for node in support
            ],
            "reason": f"被 {support_count} 篇库内论文共同引用",
            "score": 80 + support_count * 8 + min(20, math.log10(max(1, int(work.get('cited_by_count') or 0))) * 6),
            "status": "new",
        }
        candidates.append(candidate)

    candidates.sort(key=lambda item: (-item["support_count"], -item["cited_by_count"], item["title"]))
    stats = {
        "matched_library_papers": len(matched),
        "unmatched_library_papers": len(graph.get("nodes", [])) - len(matched),
    }
    return candidates[:maximum], errors, stats


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
        existing = merged.get(key)
        if existing:
            combined_sources = sorted(set(existing.get("sources", [])) | set(candidate.get("sources", [])))
            combined_topics = sorted(set(existing.get("topics", [])) | set(candidate.get("topics", [])))
            combined_score = max(float(existing.get("score", 0)), float(candidate.get("score", 0))) + 10
            if candidate.get("support_count", 0) > existing.get("support_count", 0):
                existing.update({k: v for k, v in candidate.items() if v is not None})
            for field in ("abstract", "authors", "url", "pdf_url", "openalex_id", "published", "year"):
                if not existing.get(field) and candidate.get(field):
                    existing[field] = candidate[field]
            existing["cited_by_count"] = max(
                int(existing.get("cited_by_count") or 0),
                int(candidate.get("cited_by_count") or 0),
            )
            if candidate.get("highly_cited_threshold"):
                existing["highly_cited_threshold"] = candidate["highly_cited_threshold"]
            existing["sources"] = combined_sources
            existing["topics"] = combined_topics
            existing["score"] = combined_score
            if existing.get("arxiv_id"):
                existing["id"] = f"arxiv:{existing['arxiv_id']}"
            if len(combined_sources) > 1:
                existing["reason"] = "；".join(
                    reason
                    for reason in (
                        f"被 {existing.get('support_count', 0)} 篇库内论文共同引用"
                        if existing.get("support_count")
                        else None,
                        f"领域高被引 · OpenAlex 被引 {int(existing.get('cited_by_count') or 0):,} 次"
                        if "highly_cited" in combined_sources
                        else None,
                        f"匹配每日主题：{'、'.join(combined_topics)}" if combined_topics else None,
                    )
                    if reason
                )
            continue
        prior = previous_by_key.get(key, {})
        decision = decisions.get(candidate["id"], decisions.get(key, {}))
        candidate["status"] = decision.get("status", prior.get("status", candidate.get("status", "new")))
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

    active = [item for item in merged.values() if item.get("status") != "rejected"]
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

    active.sort(
        key=lambda item: (
            item.get("status") == "accepted",
            -published_timestamp(item),
            -float(item.get("score", 0)),
            item.get("title") or "",
        )
    )
    return active[:limit]


def apply_shared_reference_minimum(candidates: list[dict], minimum: int) -> list[dict]:
    """Remove stale shared-reference provenance that no longer meets the configured threshold."""
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_DISCOVERY_JSON)
    parser.add_argument("--output-js", type=Path, default=DEFAULT_DISCOVERY_JS)
    parser.add_argument("--cache", type=Path, default=DEFAULT_CONFIG.parents[1] / ".cache" / "openalex-library.json")
    parser.add_argument("--skip-arxiv", action="store_true")
    parser.add_argument("--skip-highly-cited", action="store_true")
    parser.add_argument("--skip-shared", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_json(args.config, {})
    graph = load_json(args.graph, {})
    previous = load_json(args.output_json, {"candidates": []})
    now = datetime.now(timezone.utc)
    max_age = int(config.get("arxiv", {}).get("max_age_days", 14))
    cutoff = now - timedelta(days=max_age)

    arxiv_candidates, arxiv_errors = ([], []) if args.skip_arxiv else discover_arxiv(config, cutoff)
    highly_cited_candidates, highly_cited_errors = (
        ([], []) if args.skip_highly_cited else discover_highly_cited(config)
    )
    shared_candidates, shared_errors, shared_stats = (
        ([], [], {"matched_library_papers": 0, "unmatched_library_papers": 0})
        if args.skip_shared
        else discover_shared_references(graph, config, args.cache)
    )
    library_titles = {normalize_title(node["title"]) for node in graph.get("nodes", [])}
    maximum = int(config.get("output", {}).get("max_candidates", 60))
    retention_days = int(config.get("output", {}).get("retention_days", 60))
    candidates = merge_candidates(
        arxiv_candidates + highly_cited_candidates + shared_candidates,
        previous,
        library_titles,
        maximum,
        now,
        retention_days,
    )
    if not args.skip_shared:
        shared_minimum = int(config.get("shared_references", {}).get("min_library_citations", 2))
        candidates = apply_shared_reference_minimum(candidates, shared_minimum)
    for candidate in candidates:
        candidate.update(classify_candidate(candidate))
        candidate.update(candidate_validation(candidate, now))

    enabled_topics = [
        {
            "id": topic["id"],
            "label": topic["label"],
            "keywords": topic.get("keywords", []),
            "exclude_keywords": topic.get("exclude_keywords", []),
        }
        for topic in config.get("topics", [])
        if topic.get("enabled", True)
    ]
    output = {
        "metadata": {
            "updated_at": now.isoformat(),
            "run_mode": "+".join(
                mode for mode, skipped in (
                    ("arxiv", args.skip_arxiv),
                    ("highly_cited", args.skip_highly_cited),
                    ("shared", args.skip_shared),
                ) if not skipped
            ),
            "candidate_count": len(candidates),
            "new_count": sum(item.get("status") == "new" for item in candidates),
            "shared_reference_count": sum("shared_reference" in item.get("sources", []) for item in candidates),
            "arxiv_topic_count": sum("arxiv_topic" in item.get("sources", []) for item in candidates),
            "highly_cited_count": sum("highly_cited" in item.get("sources", []) for item in candidates),
            "errors": arxiv_errors + highly_cited_errors + shared_errors,
            **shared_stats,
        },
        "topics": enabled_topics,
        "decisions": previous.get("decisions", {}),
        "candidates": candidates,
    }
    write_discovery(output, args.output_json, args.output_js)
    print(
        f"发现完成：候选 {len(candidates)}，共同引用 {output['metadata']['shared_reference_count']}，"
        f"arXiv 主题 {output['metadata']['arxiv_topic_count']}，"
        f"领域高被引 {output['metadata']['highly_cited_count']}，错误 {len(output['metadata']['errors'])}。"
    )
    for candidate in candidates[:10]:
        print(f"CANDIDATE\t{candidate['id']}\t{candidate['reason']}\t{candidate['title']}")
    for error in output["metadata"]["errors"]:
        print(f"WARNING\t{error}")


if __name__ == "__main__":
    main()
