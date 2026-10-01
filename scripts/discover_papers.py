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
from collections import Counter, defaultdict
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
    write_text_atomic,
)
from discovery_metadata import abstract_from_inverted_index, candidate_validation
from discovery_ranking import apply_shared_reference_minimum, merge_candidates, score_recommendation


ARXIV_API = "https://export.arxiv.org/api/query"
OPENALEX_API = "https://api.openalex.org/works"
USER_AGENT = "PaperAtlas/1.0 (local research library discovery)"
ATOM = {"atom": "http://www.w3.org/2005/Atom"}
DEFAULT_DEBUG_LOG = Path(__file__).resolve().parents[1] / ".cache" / "discovery-debug.jsonl"
_DEBUG_LOG_PATH: Path | None = None

SEMANTIC_TOPIC_CONTEXTS = {
    "category-07-kernel-agents": (
        "language models and autonomous agents writing efficient GPU kernels, "
        "optimizing CUDA or Triton code, and compiling tensor programs for accelerators"
    ),
}

OPENALEX_LEXICAL_CONTEXTS = {
    # OpenAlex semantic search currently ranks KernelBench outside its first
    # page. This compact wording is intentionally derived from the category's
    # research question and complements (rather than replaces) semantic search.
    "category-07-kernel-agents": "LLMs efficient GPU kernels",
}

RECENT_OPENALEX_CONTEXTS = {
    "category-07-kernel-agents": "multi-agent GPU kernel optimization",
}

ARXIV_QUERY_GROUPS = {
    # Broad tokens such as ``agent`` overwhelm submitted-date results. Require
    # both the application domain and an agent/LLM signal before local scoring.
    "category-07-kernel-agents": (
        ("gpu kernel", "kernel optimization", "cuda kernel", "triton kernel"),
        ("agent", "agentic", "llm", "language model", "multi-agent", "autonomous"),
    ),
}

CATEGORY_LABELS = {
    "01_模型架构与基础组件": "模型架构与基础组件",
    "02_训练方法与优化器": "训练方法与优化器",
    "03_训练动力学与模型分析": "训练动力学与模型分析",
    "04_长上下文与高效注意力": "长上下文与高效注意力",
    "05_MoE与稀疏模型": "MoE 与稀疏模型",
    "06_量化与低精度计算": "量化与低精度计算",
    "07_分布式训练与数据基础设施": "分布式训练与数据基础设施",
    "08_GPU内核_编译器与性能工程": "GPU 内核、编译器与性能工程",
    "09_GPU内核智能体与自动调优": "GPU 内核智能体与自动调优",
    "10_通用智能体与自主发现": "通用智能体与自主发现",
    "11_生成模型与视频系统": "生成模型与视频系统",
    "12_大模型技术报告与推理训练": "大模型技术报告与推理训练",
    "13_个人兴趣与跨领域": "个人兴趣与跨领域",
}

# These phrases encode the same primary-topic boundaries as the paper-organizer
# skill. They favor the application domain for cross-disciplinary work: for
# example, kernel-generation agents belong to category 06.
CATEGORY_RULES = {
    "01_模型架构与基础组件": (
        "transformer architecture", "vision transformer", "positional encoding",
        "normalization", "activation function", "residual connection", "hyper connection",
        "model architecture", "architectural component", "embedding architecture",
    ),
    "02_训练方法与优化器": (
        "optimizer", "optimization algorithm", "weight decay", "regularization",
        "knowledge distillation", "on-policy distillation", "training method",
        "stochastic optimization", "automatic differentiation", "learning rate",
        "training objective", "gradient alignment", "hyperparameter transfer",
    ),
    "03_训练动力学与模型分析": (
        "training dynamics", "loss landscape", "gradient noise", "gradient spectra",
        "spectral analysis", "edge of stability", "implicit bias", "self regularization",
        "self-regularization", "heavy tailed", "tail index", "curvature measure",
        "activation dynamics", "model diagnostics", "layer wise gradients",
    ),
    "04_长上下文与高效注意力": (
        "long context", "long-context", "context window", "kv cache", "attention sinks",
        "sparse attention", "block attention", "linear attention", "ring attention",
        "memory attention", "sparse transformer", "sparse transformers", "multi-query",
        "mixture of block attention",
        "flashattention", "pagedattention", "tiledattention", "online softmax",
        "softmax normalizer", "attention kernel", "attention kernels", "sdpa kernel",
        "flex attention", "attention implementation", "attention system",
    ),
    "05_MoE与稀疏模型": (
        "mixture of experts", "mixture-of-experts", "moe", "expert routing",
        "expert parallel", "sparse model", "sparse experts", "load balancing expert",
    ),
    "06_量化与低精度计算": (
        "sageattention", "quantized attention", "attention quantization",
        "low precision attention", "low-precision attention", "attn qat",
        "attention aware quantization", "attention-aware quantization",
        "quantization", "quantized", "low precision", "low-precision", "mixed precision",
        "int8", "int4", "fp8", "fp4", "4 bit", "8 bit", "bitnet", "weight-only",
        "post-training quantization", "outlier channel", "outlier activation",
    ),
    "07_分布式训练与数据基础设施": (
        "distributed training", "data parallel", "model parallel", "pipeline parallel",
        "tensor parallel", "fsdp", "megatron", "collective communication",
        "all-reduce", "training infrastructure", "cluster scheduling",
        "distributed systems", "data pipeline", "data loader", "dataloader",
        "pretraining data", "pre-training data", "data curation", "checkpoint loading",
        "storage system", "data preprocessing", "data mixture",
    ),
    "08_GPU内核_编译器与性能工程": (
        "gpu kernel", "cuda kernel", "triton kernel", "kernel optimization",
        "kernel fusion", "tensor compiler", "gpu compiler",
        "cuda optimization", "ptx", "gpu benchmark", "code generation for gpu",
        "compiler optimization", "operator fusion", "kernel scheduling", "gpu kernels",
        "triton", "gpu programming", "gpu compilation", "gpu offload",
        "automatic kernel generation", "polyhedral transformation", "polyhedral transformations",
    ),
    "09_GPU内核智能体与自动调优": (
        "gpu kernel agent", "cuda agent", "kernel agent", "kernel agents",
        "agentic kernel", "kernel generation agent", "kernel optimization agent",
        "autonomous gpu kernel", "multi-agent kernel", "kernel design agents",
        "kernel harness", "automatic kernel optimization", "llm-based gpu kernel",
        "llms write efficient gpu kernels", "language models write efficient gpu kernels",
        "language models to generate gpu kernels", "language models optimize gpu kernels",
    ),
    "10_通用智能体与自主发现": (
        "ai agent", "llm agent", "agentic", "multi-agent", "autonomous agent",
        "tool use", "tool-use", "planning agent", "research agent", "self-play",
        "autonomous search", "open-ended discovery", "evolutionary search",
        "evolutionary code search", "evolutionary program search", "variation operators",
        "persistent memory architecture", "code optimization agent", "computer use", "web agent",
    ),
    "11_生成模型与视频系统": (
        "video generation", "text-to-video", "image-to-video", "video diffusion",
        "diffusion transformer", "frame interpolation", "video inference",
        "world model video", "streaming video generation", "video model", "diffusion model",
        "diffusion models",
    ),
    "12_大模型技术报告与推理训练": (
        "technical report", "reasoning model", "reasoning training", "reasoning llm",
        "reinforcement learning for reasoning", "rlhf", "grpo", "large language model report",
        "foundation model", "inference-time scaling", "test-time scaling",
    ),
    "13_个人兴趣与跨领域": (
        "living systems", "self-reference", "self referential", "natural time",
        "representational time", "theoretical biology", "open ended creativity",
    ),
}

# Keep rule changes auditable in candidate metadata and regression fixtures.
# The classifier still returns one primary category, but these boundaries make
# broad words such as "attention" and "agent" defer to more specific signals.
CATEGORY_RULE_VERSION = "2026-09-03.2"

ATTENTION_SPECIFIC_MARKERS = (
    "long context", "long-context", "context window", "kv cache",
    "flashattention", "sageattention", "sparse attention", "block attention",
    "linear attention", "ring attention", "memory attention", "pagedattention",
    "multi-query", "online softmax", "softmax normalizer",
)

QUANTIZATION_MARKERS = (
    "quantization", "quantized", "low precision", "low-precision",
    "mixed precision", "int8", "int4", "fp8", "fp4", "4 bit", "8 bit", "weight-only",
    "post-training quantization",
)

ML_DOMAIN_ANCHORS = (
    "machine learning", "deep learning", "neural network", "neural networks",
    "language model", "llm", "transformer", "attention", "inference", "training",
    "convolution", "cnn", "gpu", "accelerator", "model compression", "generative model",
)

TOPIC_DOMAIN_ANCHORS = {
    "category-01-model-architecture": ML_DOMAIN_ANCHORS,
    "category-02-training-optimization": ML_DOMAIN_ANCHORS,
    "category-03-training-dynamics": ML_DOMAIN_ANCHORS,
    "category-04-long-context": ("attention", "transformer", "language model", "llm", "kv cache"),
    "category-05-attention-kernels": ("attention", "gpu", "kernel", "softmax", "transformer"),
    "category-06-attention-quantization": ("attention", "quantization", "low precision", "llm"),
    "category-07-moe-sparse": ("mixture of experts", "moe", "expert", "language model", "transformer"),
    "category-08-quantization": ML_DOMAIN_ANCHORS,
    "category-09-distributed-data": ("distributed", "training", "gpu", "model", "checkpoint", "data pipeline"),
    "category-10-gpu-performance": ("gpu", "cuda", "kernel", "compiler", "triton", "tensor"),
    "category-07-kernel-agents": ("gpu", "cuda", "kernel", "compiler", "agent", "llm"),
    "category-12-general-agents": ("agent", "llm", "language model", "tool use", "autonomous"),
    "category-13-generative-video": ("video", "diffusion", "generative", "frame", "transformer"),
    "category-14-model-reports": ("language model", "llm", "reasoning", "foundation model", "training"),
    "category-15-personal-cross-domain": ("living systems", "self-reference", "biology", "cognition", "complex systems"),
    # Compatibility for topics saved before the taxonomy redesign.
    "category-02-attention-context": ("attention", "transformer", "language model", "llm", "kv cache"),
    "category-03-moe-sparse": ("mixture of experts", "moe", "expert", "language model", "transformer"),
    "category-04-quantization": ML_DOMAIN_ANCHORS,
    "category-05-distributed-data": ("distributed", "training", "gpu", "model", "checkpoint", "data pipeline"),
    "category-06-gpu-performance": ("gpu", "cuda", "kernel", "compiler", "triton", "tensor"),
    "category-08-general-agents": ("agent", "llm", "language model", "tool use", "autonomous"),
    "category-09-generative-video": ("video", "diffusion", "generative", "frame", "transformer"),
    "category-10-model-reports": ("language model", "llm", "reasoning", "foundation model", "training"),
}

TOPIC_CATEGORY_MAP = {
    "category-01-model-architecture": "01_模型架构与基础组件",
    "category-02-training-optimization": "02_训练方法与优化器",
    "category-03-training-dynamics": "03_训练动力学与模型分析",
    "category-04-long-context": "04_长上下文与高效注意力",
    "category-05-attention-kernels": "04_长上下文与高效注意力",
    "category-06-attention-quantization": "06_量化与低精度计算",
    "category-07-moe-sparse": "05_MoE与稀疏模型",
    "category-08-quantization": "06_量化与低精度计算",
    "category-09-distributed-data": "07_分布式训练与数据基础设施",
    "category-10-gpu-performance": "08_GPU内核_编译器与性能工程",
    "category-07-kernel-agents": "09_GPU内核智能体与自动调优",
    "category-12-general-agents": "10_通用智能体与自主发现",
    "category-13-generative-video": "11_生成模型与视频系统",
    "category-14-model-reports": "12_大模型技术报告与推理训练",
    "category-15-personal-cross-domain": "13_个人兴趣与跨领域",
    # Compatibility for search topics saved under the previous taxonomy.
    "category-02-attention-context": "04_长上下文与高效注意力",
    "category-03-moe-sparse": "05_MoE与稀疏模型",
    "category-04-quantization": "06_量化与低精度计算",
    "category-05-distributed-data": "07_分布式训练与数据基础设施",
    "category-06-gpu-performance": "08_GPU内核_编译器与性能工程",
    "category-08-general-agents": "10_通用智能体与自主发现",
    "category-09-generative-video": "11_生成模型与视频系统",
    "category-10-model-reports": "12_大模型技术报告与推理训练",
}

PROFILE_STOPWORDS = {
    "the", "and", "for", "with", "from", "into", "via", "using", "based", "towards",
    "toward", "efficient", "large", "models", "model", "paper", "learning", "neural",
    "language", "deep", "new", "system", "systems", "method", "methods", "approach",
    "can", "write", "are", "all", "you", "your", "our", "their", "its", "llms",
}


def configure_debug_log(path: Path) -> None:
    global _DEBUG_LOG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 5_000_000:
        path.replace(path.with_suffix(path.suffix + ".1"))
    _DEBUG_LOG_PATH = path


def debug_event(event: str, **details: object) -> None:
    if _DEBUG_LOG_PATH is None:
        return
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **details,
    }
    try:
        with _DEBUG_LOG_PATH.open("a", encoding="utf-8") as output:
            output.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
    except OSError:
        pass


def category_profile_keywords(nodes: list[dict], limit: int = 6) -> list[str]:
    unigrams: Counter[str] = Counter()
    bigrams: Counter[str] = Counter()
    for node in nodes:
        tokens = re.findall(r"[a-z][a-z0-9+.-]{2,}", str(node.get("title") or "").lower())
        meaningful = [token.strip(".-") for token in tokens if token.strip(".-") not in PROFILE_STOPWORDS]
        unigrams.update(set(meaningful))
        bigrams.update(set(" ".join(pair) for pair in zip(meaningful, meaningful[1:])))
    ranked = [
        phrase for phrase, count in sorted(bigrams.items(), key=lambda item: (-item[1], item[0]))
        if count >= 2
    ]
    ranked.extend(
        word for word, count in sorted(unigrams.items(), key=lambda item: (-item[1], item[0]))
        if count >= 2 and all(word not in phrase.split() for phrase in ranked)
    )
    return ranked[:limit]


def enrich_topics_from_library(config: dict, graph: dict) -> tuple[dict, list[dict]]:
    """Build live search profiles from the papers currently assigned to each category."""
    nodes_by_id = {node.get("id"): node for node in graph.get("nodes", [])}
    nodes_by_reference_id = {
        str(reference_id): node
        for node in graph.get("nodes", [])
        for reference_id in (node.get("sha256"), node.get("id"))
        if reference_id
    }
    main_by_category = {
        category.get("id"): nodes_by_id.get(category.get("main_node"))
        for category in graph.get("categories", [])
    }
    enriched = dict(config)
    enriched_topics = []
    profiles = []
    for original in config.get("topics", []):
        topic = dict(original)
        category = TOPIC_CATEGORY_MAP.get(str(topic.get("id") or ""))
        if category is None:
            normalized_label = normalize_title(str(topic.get("label") or ""))
            category = next(
                (
                    identifier for identifier, label in CATEGORY_LABELS.items()
                    if normalize_title(label) == normalized_label
                ),
                None,
            )
        category_nodes = [node for node in graph.get("nodes", []) if node.get("category") == category]
        category_nodes.sort(key=lambda node: (-int(node.get("citation_count") or 0), str(node.get("title") or "")))
        main = main_by_category.get(category)
        selected_reference_ids = [
            str(value) for value in topic.get("reference_paper_ids", []) if value
        ]
        selected_nodes = [
            nodes_by_reference_id[reference_id]
            for reference_id in selected_reference_ids
            if reference_id in nodes_by_reference_id
        ]
        reference_nodes = selected_nodes or (([main] if main else []) + category_nodes)
        references = []
        reference_papers = []
        for node in reference_nodes:
            title = compact_text(str((node or {}).get("title") or ""))
            if title and title not in references:
                references.append(title)
                reference_papers.append({
                    "id": node.get("sha256") or node.get("id"),
                    "title": title,
                    "category": node.get("category"),
                })
            if len(references) >= (8 if selected_nodes else 5):
                break
        dynamic_keywords = category_profile_keywords(category_nodes)
        feedback = (config.get("feedback_profiles") or {}).get(category, {}) if category else {}
        learned_keywords = [
            compact_text(str(value)) for value in feedback.get("positive_terms", [])
            if compact_text(str(value))
        ]
        learned_exclusions = [
            compact_text(str(value)) for value in feedback.get("negative_terms", [])
            if compact_text(str(value))
        ]
        keywords = list(dict.fromkeys([
            *(compact_text(str(value)) for value in topic.get("keywords", []) if compact_text(str(value))),
            *dynamic_keywords,
            *learned_keywords,
        ]))[:12]
        topic.update({
            "keywords": keywords,
            "exclude_keywords": list(dict.fromkeys([
                *(compact_text(str(value)) for value in topic.get("exclude_keywords", []) if compact_text(str(value))),
                *learned_exclusions,
            ]))[:12],
            "dynamic_keywords": dynamic_keywords,
            "reference_titles": references,
            "reference_papers": reference_papers,
            "reference_mode": "selected" if selected_nodes else "automatic",
            "learned_keywords": learned_keywords,
            "learned_exclusions": learned_exclusions,
            "library_category": category,
        })
        profile = {
            "id": topic.get("id"),
            "label": topic.get("label"),
            "category": category,
            "paper_count": len(category_nodes),
            "dynamic_keywords": dynamic_keywords,
            "reference_titles": references,
            "reference_papers": reference_papers,
            "reference_mode": "selected" if selected_nodes else "automatic",
        }
        profiles.append(profile)
        enriched_topics.append(topic)
    enriched["topics"] = enriched_topics
    return enriched, profiles


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
    abstract_focus = abstract[:2200]
    scores = {
        category: phrase_score(title, phrases, 8)
        + phrase_score(abstract_focus, phrases, 2)
        + phrase_score(topics, phrases, 4)
        for category, phrases in CATEGORY_RULES.items()
    }
    support_counts: dict[str, int] = defaultdict(int)
    for paper in candidate.get("supporting_papers") or []:
        category = str(paper.get("category") or "")
        if category in scores:
            support_counts[category] += 1
            scores[category] += 3

    combined = f" {normalize_title(' '.join((title, abstract_focus, topics)))} "
    normalized_title = normalize_title(title)
    video_category = "11_生成模型与视频系统"
    architecture_category = "01_模型架构与基础组件"
    kernel_category = "08_GPU内核_编译器与性能工程"
    kernel_agent_category = "09_GPU内核智能体与自动调优"
    long_context_category = "04_长上下文与高效注意力"
    attention_kernel_category = "04_长上下文与高效注意力"
    attention_quantization_category = "06_量化与低精度计算"
    quantization_category = "06_量化与低精度计算"
    has_quantization = any(marker in combined for marker in QUANTIZATION_MARKERS)

    title_has_attention = " attention " in f" {normalized_title} "
    if "attention is all you need" in f" {normalized_title} ":
        scores[architecture_category] += 64
    attention_kernel_signal = any(marker in normalized_title for marker in (
        "flashattention", "pagedattention", "tiledattention", "sdpa", "flex attention",
        "online normalizer", "online softmax", "attention kernel", "attention kernels",
    ))
    attention_quantization_signal = has_quantization and (
        title_has_attention
        or any(marker in normalized_title for marker in ("sageattention", "attn qat"))
    )
    long_context_signal = any(marker in normalized_title for marker in (
        "long context", "long-context", "attention sinks", "sparse attention",
        "block attention", "mixture of block attention", "ring attention",
    ))
    if attention_quantization_signal:
        scores[attention_quantization_category] += 80
        scores[quantization_category] = max(0, scores[quantization_category] - 8)
    elif attention_kernel_signal:
        scores[attention_kernel_category] += 80
        scores[kernel_category] = max(0, scores[kernel_category] - 25)
    elif long_context_signal:
        scores[long_context_category] += 48

    # Quantization is a distinct method family. Preserve attention as the
    # primary category only when the paper explicitly focuses on an
    # attention-specific quantization technique.
    if has_quantization and not attention_quantization_signal:
        scores[quantization_category] += 12
    video_title_signal = any(marker in f" {normalized_title} " for marker in (
        " video ", " text to video ", " image to video ",
    )) or (
        " diffusion " in f" {normalized_title} " and not has_quantization
    )
    if video_title_signal:
        scores[video_category] += 24
    moe_focus = f" {normalize_title(' '.join((title, abstract[:450])))} "
    if any(marker in moe_focus for marker in (" mixture of experts ", " moe ")):
        scores["05_MoE与稀疏模型"] += 22
    kernel_markers = (
        " gpu kernel ", " gpu kernels ", " cuda kernel ", " cuda kernels ",
        " triton kernel ", " triton kernels ", " accelerator kernel ",
        " accelerator kernels ", " tensor accelerator ", " kernel benchmark ",
        " kernel benchmarks ", " kernel ", " kernels ", " ptx ",
    )
    agent_markers = (
        " agent ", " agents ", " agentic ", " multi agent ", " autonomous ",
    )
    if any(marker in combined for marker in kernel_markers):
        agent_context = re.sub(
            r"\b(?:without|no|not using|does not use)\s+(?:an?\s+)?(?:llms?|language models?|agents?)\b",
            " ", combined,
        )
        if any(marker in agent_context for marker in agent_markers):
            scores[kernel_agent_category] += 32
        else:
            scores[kernel_category] += 24 if any(marker in f" {normalized_title} " for marker in kernel_markers) else 8
    title_kernel_signal = any(marker in f" {normalized_title} " for marker in kernel_markers)
    title_agent_signal = any(marker in f" {normalized_title} " for marker in (
        " agent ", " agents ", " agentic ", " multi agent ", " llm ", " llms ",
        " language model ", " language models ",
    ))
    if title_kernel_signal and title_agent_signal:
        scores[kernel_agent_category] += 60
        scores[kernel_category] = max(0, scores[kernel_category] - 12)
    if (
        any(marker in combined for marker in (" autonomous coding agent ", " autonomous coding agents "))
        and any(marker in combined for marker in (" kernel ", " kernels "))
    ):
        scores[kernel_agent_category] += 28
    performance_title_signal = any(marker in f" {normalized_title} " for marker in (
        " gpu ", " gpgpu ", " cuda ", " kernel ", " kernels ", " triton ",
        " tile level ", " tile level ",
    ))
    if performance_title_signal:
        scores[kernel_category] += 28
    if any(marker in f" {normalized_title} " for marker in (" gpgpu ", " tile level ")):
        scores[kernel_category] += 20
    accelerator_context = any(marker in combined for marker in (
        " accelerator ", " accelerators ", " tensor processor ", " tensor accelerator ",
    ))
    accelerator_agent_signal = any(marker in combined for marker in (
        " llm driven ", " llm based ", " automated llm ", " code generation ",
        " code optimizer ", " agentic ",
    ))
    if accelerator_context and accelerator_agent_signal:
        scores[kernel_agent_category] += 36
    if " benchmark " in combined and any(marker in combined for marker in (
        " hardware limits ", " speed of light ", " execbench ",
    )):
        scores[kernel_category] += 26
        scores[kernel_agent_category] = max(0, scores[kernel_agent_category] - 8)
    report_title_signal = any(marker in f" {normalized_title} " for marker in (
        " technical report ", " open large language models ", " model card ",
    )) or normalized_title.startswith("deepseek ")
    if report_title_signal:
        scores["12_大模型技术报告与推理训练"] += 24
    if " optimizer " in f" {normalized_title} ":
        scores["02_训练方法与优化器"] += 18
    if (
        not title_kernel_signal
        and any(marker in combined for marker in (" evolutionary ", " evolution "))
        and any(marker in combined for marker in (" code search ", " program search ", " persistent memory "))
    ):
        scores["10_通用智能体与自主发现"] += 18
    distributed_title_signal = any(marker in f" {normalized_title} " for marker in (
        " pipeline parallelism ", " distributed training ",
        " compute communication ", " communication overlapping ",
    ))
    if distributed_title_signal:
        scores["07_分布式训练与数据基础设施"] += 18
        scores[long_context_category] = max(0, scores[long_context_category] - 8)

    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    category, top_score = ranked[0]
    runner_up = ranked[1][1]
    if top_score <= 0:
        topic_categories = [
            TOPIC_CATEGORY_MAP[topic_id]
            for topic_id in candidate.get("topic_ids") or []
            if topic_id in TOPIC_CATEGORY_MAP
        ]
        if topic_categories:
            category = topic_categories[0]
            return {
                "suggested_category": category,
                "category_label": category_label(category),
                "category_confidence": "需确认",
                "category_reason": "根据命中的搜索主题给出建议，请结合摘要确认",
                "category_rule_version": CATEGORY_RULE_VERSION,
            }
        return {
            "suggested_category": "",
            "category_label": "待确认类别",
            "category_confidence": "需确认",
            "category_reason": "标题与摘要尚不足以判断主类别",
            "category_rule_version": CATEGORY_RULE_VERSION,
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
        "category_rule_version": CATEGORY_RULE_VERSION,
    }


def query_term(value: str) -> tuple[str, str]:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'ti:"{escaped}"', f'abs:"{escaped}"'


def topic_query(topic: dict) -> str:
    """Build a safe arXiv query from human-friendly keywords."""
    keywords = [compact_text(str(item)) for item in topic.get("keywords", []) if compact_text(str(item))]
    if keywords:
        terms = []
        for keyword in keywords:
            terms.extend(query_term(keyword))
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


def arxiv_topic_query(topic: dict) -> str:
    """Prefer a domain + intent query for categories prone to generic noise."""
    groups = ARXIV_QUERY_GROUPS.get(str(topic.get("id") or ""))
    if not groups:
        return topic_query(topic)
    clauses = []
    for group in groups:
        terms = [term for keyword in group for term in query_term(keyword)]
        clauses.append("(" + " OR ".join(terms) + ")")
    query = " AND ".join(clauses)
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
    if topic_id == "category-07-kernel-agents":
        combined = title + abstract
        kernel_signal = any(marker in combined for marker in (
            " gpu kernel ", " gpu kernels ", " cuda kernel ", " cuda kernels ",
            " triton kernel ", " triton kernels ", " kernel optimization ",
        ))
        agent_signal = any(marker in combined for marker in (
            " agent ", " agents ", " agentic ", " multi agent ", " autonomous ",
            " llm ", " llms ", " language model ", " language models ",
        ))
        relevant = relevant and kernel_signal and agent_signal
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
        debug_event("http_retry", host=urllib.parse.urlsplit(url).hostname, attempt=attempt + 1, error=str(last_error))
        if attempt < attempts - 1:
            retry_after = 0.0
            if isinstance(last_error, urllib.error.HTTPError) and last_error.code == 429:
                try:
                    retry_after = float(last_error.headers.get("Retry-After") or 0)
                except (TypeError, ValueError):
                    retry_after = 0.0
            time.sleep(max(retry_after, 5.0 * (2**attempt)) if retry_after else 1.5 * (2**attempt))
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
                "topic_ids": [topic["id"]] if topic.get("id") else [],
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


def discover_recent_openalex(topic: dict, cutoff: datetime, pool_size: int, mailto: str) -> list[dict]:
    """Recover recent arXiv records when the official Atom endpoint is rate-limited."""
    query = RECENT_OPENALEX_CONTEXTS.get(str(topic.get("id") or ""))
    if not query:
        phrases = [
            compact_text(str(value)) for value in topic.get("keywords", [])
            if len(normalize_title(str(value)).split()) >= 2
        ]
        query = " ".join(phrases[:2])
    if not query:
        raise ValueError(f"主题“{topic.get('label') or '未命名'}”没有可用的近期论文查询")
    params = {
        "search": query,
        "filter": f"from_publication_date:{cutoff.date().isoformat()}",
        "per-page": min(100, max(25, pool_size)),
        "sort": "publication_date:desc",
        "select": (
            "id,display_name,publication_year,publication_date,ids,cited_by_count,"
            "authorships,primary_location,abstract_inverted_index"
        ),
        "mailto": mailto,
    }
    works = request_json(f"{OPENALEX_API}?{urllib.parse.urlencode(params)}").get("results") or []
    candidates = []
    for work in works:
        arxiv_id = arxiv_id_from_work(work)
        if not arxiv_id:
            continue
        published = str(work.get("publication_date") or "")
        try:
            if published and datetime.fromisoformat(published).replace(tzinfo=timezone.utc) < cutoff:
                continue
        except ValueError:
            continue
        candidate = {
            "id": f"arxiv:{arxiv_id}",
            "arxiv_id": arxiv_id,
            "openalex_id": work.get("id"),
            "title": compact_text(str(work.get("display_name") or "")),
            "authors": author_names(work),
            "abstract": abstract_from_inverted_index(work.get("abstract_inverted_index")) or "",
            "year": work.get("publication_year"),
            "published": published or None,
            "url": f"https://arxiv.org/abs/{arxiv_id}",
            "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}",
            "sources": ["arxiv_topic"],
            "topics": [topic["label"]],
            "topic_ids": [topic["id"]] if topic.get("id") else [],
            "reason": f"匹配每日主题：{topic['label']}",
            "score": 50,
            "status": "new",
            "discovery_provider": "openalex_arxiv_fallback",
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
    settings = config.get("arxiv", {})
    delay = float(settings.get("request_delay_seconds", 3))
    fetch_pool_size = min(200, max(25, int(settings.get("fetch_pool_size", 100))))
    mailto = str(
        os.environ.get("OPENALEX_MAILTO")
        or config.get("shared_references", {}).get("mailto")
        or "paper-atlas@example.com"
    )
    for index, topic in enumerate(topics):
        try:
            query = arxiv_topic_query(topic)
        except ValueError as error:
            errors.append(f"arXiv / {topic.get('label', '未命名主题')}: {error}")
            continue
        params = urllib.parse.urlencode(
            {
                "search_query": query,
                "start": 0,
                # max_results controls how many cards the user wants, not how
                # deep we must look through submitted-date results to find them.
                "max_results": max(fetch_pool_size, int(topic.get("max_results", 10))),
                "sortBy": "submittedDate",
                "sortOrder": "descending",
            }
        )
        try:
            payload = request_bytes(f"{ARXIV_API}?{params}")
            found = parse_arxiv_feed(payload, topic, cutoff)
            candidates.extend(found)
            debug_event(
                "arxiv_topic",
                topic_id=topic.get("id"),
                query=query,
                fetch_pool_size=fetch_pool_size,
                candidate_count=len(found),
                dynamic_keywords=topic.get("dynamic_keywords", []),
                reference_titles=topic.get("reference_titles", []),
            )
        except (urllib.error.URLError, TimeoutError, ET.ParseError) as error:
            try:
                found = discover_recent_openalex(topic, cutoff, fetch_pool_size, mailto)
                candidates.extend(found)
                debug_event(
                    "arxiv_fallback",
                    topic_id=topic.get("id"),
                    upstream_error=str(error),
                    candidate_count=len(found),
                    provider="openalex",
                )
            except (ValueError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as fallback_error:
                errors.append(f"arXiv / {topic['label']}: {error}；OpenAlex 回退: {fallback_error}")
                debug_event(
                    "arxiv_error", topic_id=topic.get("id"), error=str(error),
                    fallback_error=str(fallback_error),
                )
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
    # OpenAlex regular search treats these characters as query operators. A
    # literal question mark in titles such as KernelBench otherwise yields 400.
    search_title = compact_text(re.sub(r"[?*~]+", " ", str(node.get("title") or "")))
    if not search_title:
        return None
    params = {
        "search": search_title,
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


def openalex_semantic_query(topic: dict) -> str:
    """Turn soft topic keywords into a natural-language semantic query."""
    keywords = [
        compact_text(str(value)) for value in topic.get("keywords", [])
        if compact_text(str(value))
    ]
    if not keywords:
        raise ValueError(f"主题“{topic.get('label') or '未命名'}”没有关键词")
    context = SEMANTIC_TOPIC_CONTEXTS.get(str(topic.get("id") or "")) or "; ".join(keywords)
    references = [compact_text(str(value)) for value in topic.get("reference_titles", []) if value]
    if references:
        context += ". Reference papers include: " + "; ".join(references)
    return ("Academic research papers about " + context)[:2000]


def openalex_semantic_queries(topic: dict) -> list[str]:
    queries = [openalex_semantic_query(topic)]
    references = [compact_text(str(value)) for value in topic.get("reference_titles", []) if value]
    if references:
        queries.append(("Academic papers semantically related to: " + "; ".join(references))[:2000])
    return list(dict.fromkeys(queries))


def openalex_lexical_queries(topic: dict) -> list[str]:
    """Return compact full-text searches that recover precise named concepts."""
    configured = OPENALEX_LEXICAL_CONTEXTS.get(str(topic.get("id") or ""))
    queries = [configured] if configured else []
    phrases = [
        compact_text(str(value)) for value in topic.get("keywords", [])
        if len(normalize_title(str(value)).split()) >= 2
    ]
    if phrases:
        # A short phrase query behaves much better than sending the entire live
        # profile as one bag of words to OpenAlex regular search.
        queries.append(" ".join(phrases[:2]))
    return list(dict.fromkeys(query for query in queries if query))


def openalex_work_text(work: dict) -> str:
    primary_topic = work.get("primary_topic") or {}
    topics = work.get("topics") or []
    return " ".join(
        value for value in (
            str(work.get("display_name") or ""),
            abstract_from_inverted_index(work.get("abstract_inverted_index")) or "",
            str(primary_topic.get("display_name") or ""),
            " ".join(str((topic or {}).get("display_name") or "") for topic in topics),
        ) if value
    )


def lexical_work_relevant(work: dict) -> bool:
    """Validate regular-search results against the compact query that found them."""
    text_tokens = set(normalize_title(openalex_work_text(work)).split())
    for query in work.get("_lexical_queries") or []:
        query_tokens = set(normalize_title(str(query)).split())
        if not query_tokens:
            continue
        required = max(2, math.ceil(len(query_tokens) * 0.5))
        if len(query_tokens & text_tokens) >= required:
            return True
    return False


def excluded_from_topic(work: dict, topic: dict) -> bool:
    """Keep exclusions explicit even though positive keywords use semantic matching."""
    text = f" {normalize_title(openalex_work_text(work))} "
    return any(
        f" {term} " in text
        for value in topic.get("exclude_keywords", [])
        if (term := normalize_title(str(value)))
    )


def semantic_relevance(work: dict, rank: int) -> dict:
    """Expose OpenAlex semantic relevance without requiring literal keyword hits."""
    try:
        semantic_score = max(0.0, float(work.get("relevance_score") or 0))
    except (TypeError, ValueError):
        semantic_score = 0.0
    score = (
        round(min(100, max(50, semantic_score * 80)))
        if semantic_score
        else max(50, 92 - rank)
    )
    modes = set(work.get("_search_modes") or [])
    evidence = [
        f"OpenAlex 语义相似度 {semantic_score:.2f}"
        if semantic_score
        else f"OpenAlex 关键词结果第 {rank} 位"
        if "lexical" in modes
        else f"OpenAlex 语义结果第 {rank} 位"
    ]
    primary_topic = str((work.get("primary_topic") or {}).get("display_name") or "").strip()
    if primary_topic:
        evidence.append(f"OpenAlex 主题 {primary_topic}")
    return {
        "relevance_score": score,
        "relevance_label": "高" if score >= 70 else "中",
        "relevance_evidence": evidence,
        "relevance_threshold": 0,
        "semantic_relevance_score": semantic_score,
        "semantic_rank": rank,
        "openalex_search_modes": sorted(modes),
    }


def highly_cited_stats() -> dict:
    return {
        "highly_cited_raw_count": 0,
        "highly_cited_relevant_count": 0,
        "highly_cited_threshold_count": 0,
        "highly_cited_selected_count": 0,
        "highly_cited_search_mode": "semantic+lexical",
        "highly_cited_library_count": 0,
        "highly_cited_library_matches": [],
        "highly_cited_library_below_threshold_matches": [],
    }


def discover_highly_cited(config: dict) -> tuple[list[dict], list[str], dict]:
    """Find established papers through hybrid topic recall, then rank by citations."""
    settings = config.get("highly_cited", {})
    stats = highly_cited_stats()
    if not settings.get("enabled", True):
        stats["highly_cited_search_mode"] = "disabled"
        return [], [], stats
    minimum = max(1, int(settings.get("min_citations", 50)))
    maximum_per_topic = min(50, max(1, int(settings.get("max_per_topic", 20))))
    maximum = min(100, max(1, int(settings.get("max_candidates", 60))))
    pool_size = min(50, max(10, int(settings.get("semantic_pool_size", 50))))
    delay = max(1.0, float(settings.get("request_delay_seconds", 1.0)))
    mailto = str(
        os.environ.get("OPENALEX_MAILTO")
        or settings.get("mailto")
        or config.get("shared_references", {}).get("mailto")
        or "paper-atlas@example.com"
    )
    topics = [topic for topic in config.get("topics", []) if topic.get("enabled", True)]
    candidates_by_id: dict[str, dict] = {}
    errors: list[str] = []
    raw_ids: set[str] = set()
    relevant_ids: set[str] = set()
    threshold_ids: set[str] = set()
    threshold_papers: dict[str, dict] = {}
    relevant_papers: dict[str, dict] = {}
    for index, topic in enumerate(topics):
        try:
            semantic_queries = openalex_semantic_queries(topic)
            lexical_queries = openalex_lexical_queries(topic)
            works_by_id: dict[str, dict] = {}

            def remember(work: dict, rank: int, mode: str, query: str) -> None:
                work_id = str(work.get("id") or "")
                if not work_id:
                    return
                existing = works_by_id.setdefault(work_id, dict(work))
                modes = set(existing.get("_search_modes") or [])
                modes.add(mode)
                existing["_search_modes"] = sorted(modes)
                rank_key = f"_{mode}_rank"
                existing[rank_key] = min(rank, int(existing.get(rank_key) or rank))
                if mode == "lexical":
                    existing["_lexical_queries"] = list(dict.fromkeys([
                        *(existing.get("_lexical_queries") or []), query,
                    ]))
                incoming_score = float(work.get("relevance_score") or 0)
                if incoming_score > float(existing.get("relevance_score") or 0):
                    existing["relevance_score"] = incoming_score

            for query_index, query in enumerate(semantic_queries):
                params = {
                    "search.semantic": query,
                    "per-page": pool_size,
                    "select": (
                        "id,display_name,publication_year,publication_date,ids,cited_by_count,"
                        "authorships,primary_location,abstract_inverted_index,relevance_score,"
                        "primary_topic,topics"
                    ),
                    "mailto": mailto,
                }
                results = request_json(f"{OPENALEX_API}?{urllib.parse.urlencode(params)}").get("results") or []
                for rank, work in enumerate(results, 1):
                    remember(work, rank, "semantic", query)
                if query_index < len(semantic_queries) - 1 and delay > 0:
                    time.sleep(delay)
            if semantic_queries and lexical_queries and delay > 0:
                time.sleep(delay)
            for query_index, query in enumerate(lexical_queries):
                params = {
                    "search": query,
                    "per-page": pool_size,
                    "select": (
                        "id,display_name,publication_year,publication_date,ids,cited_by_count,"
                        "authorships,primary_location,abstract_inverted_index,relevance_score,"
                        "primary_topic,topics"
                    ),
                    "mailto": mailto,
                }
                results = request_json(f"{OPENALEX_API}?{urllib.parse.urlencode(params)}").get("results") or []
                for rank, work in enumerate(results, 1):
                    remember(work, rank, "lexical", query)
                if query_index < len(lexical_queries) - 1 and delay > 0:
                    time.sleep(delay)
            works = list(works_by_id.values())
        except (ValueError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            errors.append(f"OpenAlex 高被引 / {topic.get('label', '未命名主题')}: {error}")
            debug_event("highly_cited_error", topic_id=topic.get("id"), error=str(error))
            continue

        eligible: list[dict] = []
        for work in works:
            modes = set(work.get("_search_modes") or [])
            if modes == {"lexical"} and not lexical_work_relevant(work):
                continue
            rank = int(work.get("_semantic_rank") or work.get("_lexical_rank") or 1)
            cited_by_count = int(work.get("cited_by_count") or 0)
            title = compact_text(str(work.get("display_name") or ""))
            work_id = str(work.get("id") or "")
            if not work_id or not title:
                continue
            raw_ids.add(work_id)
            if excluded_from_topic(work, topic):
                continue
            relevant_ids.add(work_id)
            relevant_papers[work_id] = {
                "id": work_id,
                "title": title,
                "cited_by_count": cited_by_count,
                "topic": topic.get("label") or "",
            }
            if cited_by_count < minimum:
                continue
            threshold_ids.add(work_id)
            threshold_papers[work_id] = {
                "id": work_id,
                "title": title,
                "cited_by_count": cited_by_count,
                "topic": topic.get("label") or "",
            }
            arxiv_id = arxiv_id_from_work(work)
            location = work.get("primary_location") or {}
            ids = work.get("ids") or {}
            url = location.get("landing_page_url") or ids.get("doi") or work_id
            pdf_url = location.get("pdf_url") or (f"https://arxiv.org/pdf/{arxiv_id}" if arxiv_id else None)
            relevance = semantic_relevance(work, rank)
            primary_topic = str((work.get("primary_topic") or {}).get("display_name") or "").strip()
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
                "topic_ids": [topic["id"]] if topic.get("id") else [],
                "reason": f"领域高被引 · OpenAlex 被引 {cited_by_count:,} 次 · 语义匹配 {topic['label']}",
                "score": 70 + min(40, math.log10(max(1, cited_by_count)) * 10),
                "status": "new",
                "openalex_primary_topic": primary_topic or None,
                **relevance,
            }
            candidate["score"] += relevance["relevance_score"] / 4
            eligible.append(candidate)
        eligible.sort(key=lambda item: (
            -int(item.get("cited_by_count") or 0),
            -float(item.get("semantic_relevance_score") or 0),
            item["title"],
        ))
        selected_for_topic = eligible[:maximum_per_topic]
        lexical_recall = sorted(
            (
                candidate for candidate in eligible
                if "lexical" in set(candidate.get("openalex_search_modes") or [])
            ),
            key=lambda item: (
                int(item.get("semantic_rank") or 10_000),
                -int(item.get("cited_by_count") or 0),
                item["title"],
            ),
        )[:maximum_per_topic]
        selected_for_topic = list({
            candidate["id"]: candidate for candidate in selected_for_topic + lexical_recall
        }.values())
        debug_event(
            "highly_cited_topic",
            topic_id=topic.get("id"),
            semantic_queries=semantic_queries,
            lexical_queries=lexical_queries,
            raw_count=len(works),
            eligible_count=len(eligible),
            citation_selected_count=min(len(eligible), maximum_per_topic),
            lexical_selected_count=len(lexical_recall),
            selected_count=len(selected_for_topic),
            min_citations=minimum,
        )
        for candidate in selected_for_topic:
            candidate_id = candidate["id"]
            existing = candidates_by_id.get(candidate_id)
            if existing is None:
                candidates_by_id[candidate_id] = candidate
                continue
            existing["topics"] = sorted(set(existing.get("topics", [])) | set(candidate.get("topics", [])))
            existing["topic_ids"] = sorted(
                set(existing.get("topic_ids", [])) | set(candidate.get("topic_ids", []))
            )
            if float(candidate.get("semantic_relevance_score") or 0) > float(
                existing.get("semantic_relevance_score") or 0
            ):
                for field in (
                    "relevance_score", "relevance_label", "relevance_evidence",
                    "semantic_relevance_score", "semantic_rank", "openalex_primary_topic",
                ):
                    existing[field] = candidate.get(field)
            existing["reason"] = (
                f"领域高被引 · OpenAlex 被引 {int(existing.get('cited_by_count') or 0):,} 次"
                f" · 语义匹配 {'、'.join(existing['topics'])}"
            )
        if index < len(topics) - 1 and delay > 0:
            time.sleep(delay)

    candidates = list(candidates_by_id.values())
    candidates.sort(
        key=lambda item: (
            -int(item.get("cited_by_count") or 0),
            -float(item.get("semantic_relevance_score") or 0),
            item["title"],
        )
    )
    selected = candidates[:maximum]
    stats.update({
        "highly_cited_raw_count": len(raw_ids),
        "highly_cited_relevant_count": len(relevant_ids),
        "highly_cited_threshold_count": len(threshold_ids),
        "highly_cited_selected_count": len(selected),
        "_highly_cited_threshold_papers": list(threshold_papers.values()),
        "_highly_cited_relevant_papers": list(relevant_papers.values()),
    })
    return selected, errors, stats


def load_openalex_cache(path: Path) -> dict:
    return load_json(
        path,
        {"version": 3, "nodes": {}, "reference_index": {}, "external_references": {}},
    )  # type: ignore[return-value]


def reusable_openalex_cache_entry(cached: object, cache_version: int, now: datetime) -> bool:
    if not isinstance(cached, dict):
        return False
    if cached.get("work"):
        return True
    if cache_version < 2:
        return False
    try:
        resolved_at = datetime.fromisoformat(
            str(cached.get("resolved_at") or "").replace("Z", "+00:00")
        )
    except ValueError:
        return False
    return now - resolved_at < timedelta(days=7)


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
    cache_version = int(cache.get("version") or 1)
    cache["version"] = 3
    node_cache = cache.setdefault("nodes", {})
    reference_index = cache.setdefault("reference_index", {})
    external_cache = cache.setdefault("external_references", {})
    errors: list[str] = []
    matched: dict[str, dict] = {}
    nodes_by_id = {node["id"]: node for node in graph.get("nodes", [])}

    for index, node in enumerate(graph.get("nodes", [])):
        cache_key = str(node.get("sha256") or normalize_title(node["title"]))
        cached = node_cache.get(cache_key)
        if not reusable_openalex_cache_entry(cached, cache_version, datetime.now(timezone.utc)):
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

    library_work_ids = {work["id"] for work in matched.values() if work.get("id")}
    supporting_nodes: dict[str, set[str]] = defaultdict(set)
    for node_id, work in matched.items():
        for referenced_id in work.get("referenced_works") or []:
            supporting_nodes[referenced_id].add(node_id)

    # Preserve local PDF evidence independently from the target node. If a
    # previously archived paper is removed, its surviving citing papers can
    # still reconstruct it as a shared-reference candidate on the next run.
    local_support: dict[str, set[str]] = defaultdict(set)
    for edge in (graph.get("edges") or {}).get("citation", []):
        source_id = str(edge.get("source") or "")
        target_id = str(edge.get("target") or "")
        if source_id in nodes_by_id and target_id in nodes_by_id:
            local_support[target_id].add(source_id)
    now_iso = datetime.now(timezone.utc).isoformat()
    for target_id, work in matched.items():
        work_id = str(work.get("id") or "")
        if not work_id:
            continue
        target = nodes_by_id[target_id]
        reference_index[work_id] = {
            "title": target["title"],
            "work": work,
            "supporting_papers": [
                {
                    "sha256": nodes_by_id[source_id].get("sha256"),
                    "title": nodes_by_id[source_id]["title"],
                    "category": nodes_by_id[source_id].get("category"),
                }
                for source_id in sorted(local_support.get(target_id, set()))
            ],
            "last_seen": now_iso,
        }

    node_id_by_sha = {
        str(node.get("sha256")): node_id
        for node_id, node in nodes_by_id.items()
        if node.get("sha256")
    }
    node_id_by_title = {
        normalize_title(node["title"]): node_id for node_id, node in nodes_by_id.items()
    }
    historical_works: dict[str, dict] = {}
    for work_id, evidence in reference_index.items():
        if not isinstance(evidence, dict):
            continue
        cached_work = evidence.get("work")
        if isinstance(cached_work, dict):
            historical_works[work_id] = cached_work
        for paper in evidence.get("supporting_papers") or []:
            if not isinstance(paper, dict):
                continue
            node_id = node_id_by_sha.get(str(paper.get("sha256") or ""))
            if node_id is None:
                node_id = node_id_by_title.get(normalize_title(str(paper.get("title") or "")))
            if node_id is not None:
                supporting_nodes[work_id].add(node_id)

    # Add evidence extracted from the PDFs themselves. This recovers common
    # references even when a library paper cannot be resolved to OpenAlex or
    # its OpenAlex reference list is incomplete.
    external_records = [
        item for item in graph.get("external_references", [])
        if isinstance(item, dict)
        and int(item.get("support_count") or 0) >= minimum
        and item.get("title")
    ]
    external_records.sort(
        key=lambda item: (-int(item.get("support_count") or 0), str(item.get("key") or ""))
    )
    resolution_limit = int(settings.get("max_external_resolutions", max(30, maximum * 3)))
    external_resolved = 0
    for index, reference in enumerate(external_records[:resolution_limit]):
        reference_key = str(
            reference.get("key") or normalize_title(str(reference.get("title") or ""))
        )
        cached = external_cache.get(reference_key)
        if not reusable_openalex_cache_entry(cached, cache_version, datetime.now(timezone.utc)):
            try:
                work = resolve_openalex_work(
                    {"title": reference.get("title"), "authors": ""}, mailto,
                )
                cached = {
                    "title": reference.get("title"),
                    "work": work,
                    "resolved_at": datetime.now(timezone.utc).isoformat(),
                }
                external_cache[reference_key] = cached
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
                errors.append(f"OpenAlex bibliography / {reference.get('title')}: {error}")
                continue
            if delay > 0 and index < min(len(external_records), resolution_limit) - 1:
                time.sleep(delay)
        work = cached.get("work") if isinstance(cached, dict) else None
        work_id = str((work or {}).get("id") or "") if isinstance(work, dict) else ""
        if not work_id or work_id in library_work_ids:
            continue
        external_resolved += 1
        historical_works[work_id] = work
        for paper in reference.get("supporting_papers") or []:
            node_id = node_id_by_sha.get(str(paper.get("sha256") or ""))
            if node_id is None:
                node_id = node_id_by_title.get(normalize_title(str(paper.get("title") or "")))
            if node_id is not None:
                supporting_nodes[work_id].add(node_id)

    write_text_atomic(cache_path, json.dumps(cache, ensure_ascii=False, indent=2) + "\n")

    ranked_ids = sorted(
        (
            work_id for work_id, node_ids in supporting_nodes.items()
            if work_id not in library_work_ids and len(node_ids) >= minimum
        ),
        key=lambda work_id: (-len(supporting_nodes[work_id]), work_id),
    )[: maximum * 3]
    try:
        works = fetch_openalex_works(ranked_ids, mailto) if ranked_ids else []
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        errors.append(f"OpenAlex / candidate metadata: {error}")
        works = []

    returned_ids = {str(work.get("id") or "") for work in works}
    works.extend(
        historical_works[work_id]
        for work_id in ranked_ids
        if work_id not in returned_ids and work_id in historical_works
    )

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
    node_by_work_id = {
        work.get("id"): nodes_by_id[node_id]
        for node_id, work in matched.items()
        if work.get("id") and node_id in nodes_by_id
    }
    library_matches_by_title: dict[str, dict] = {}
    for target_id, support_ids in local_support.items():
        if len(support_ids) < minimum:
            continue
        node = nodes_by_id[target_id]
        library_matches_by_title[normalize_title(node["title"])] = {
            "title": node["title"],
            "support_count": len(support_ids),
            "supporting_papers": sorted(nodes_by_id[node_id]["title"] for node_id in support_ids),
            "evidence_source": "library_graph",
        }
    for work_id in sorted(library_work_ids):
        support_ids = supporting_nodes.get(work_id, set())
        if len(support_ids) < minimum or work_id not in node_by_work_id:
            continue
        node = node_by_work_id[work_id]
        key = normalize_title(node["title"])
        openalex_match = {
            "title": node["title"],
            "support_count": len(support_ids),
            "supporting_papers": sorted(nodes_by_id[node_id]["title"] for node_id in support_ids),
            "evidence_source": "openalex",
        }
        existing_match = library_matches_by_title.get(key)
        if existing_match is None or openalex_match["support_count"] > existing_match["support_count"]:
            library_matches_by_title[key] = openalex_match
    library_matches = list(library_matches_by_title.values())
    library_matches.sort(key=lambda item: (-item["support_count"], item["title"]))
    stats = {
        "matched_library_papers": len(matched),
        "unmatched_library_papers": len(graph.get("nodes", [])) - len(matched),
        "shared_reference_library_count": len(library_matches),
        "shared_reference_library_matches": library_matches[:20],
        "pdf_external_reference_count": len(graph.get("external_references", [])),
        "pdf_external_qualified_count": len(external_records),
        "pdf_external_resolved_count": external_resolved,
    }
    debug_event(
        "shared_reference_summary",
        library_papers=len(graph.get("nodes", [])),
        matched_library_papers=len(matched),
        candidate_count=min(len(candidates), maximum),
        library_match_count=len(library_matches),
        minimum=minimum,
        pdf_external_qualified=len(external_records),
        pdf_external_resolved=external_resolved,
        errors=errors,
    )
    return candidates[:maximum], errors, stats


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_DISCOVERY_JSON)
    parser.add_argument("--output-js", type=Path, default=DEFAULT_DISCOVERY_JS)
    parser.add_argument("--cache", type=Path, default=DEFAULT_CONFIG.parents[1] / ".cache" / "openalex-library.json")
    parser.add_argument("--debug-log", type=Path, default=DEFAULT_DEBUG_LOG)
    parser.add_argument("--skip-arxiv", action="store_true")
    parser.add_argument("--skip-highly-cited", action="store_true")
    parser.add_argument("--skip-shared", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configure_debug_log(args.debug_log)
    debug_event(
        "discovery_started",
        skip_arxiv=args.skip_arxiv,
        skip_highly_cited=args.skip_highly_cited,
        skip_shared=args.skip_shared,
    )
    config = load_json(args.config, {})
    graph = load_json(args.graph, {})
    config, topic_profiles = enrich_topics_from_library(config, graph)
    for profile in topic_profiles:
        debug_event("topic_profile", **profile)
    previous = load_json(args.output_json, {"candidates": []})
    now = datetime.now(timezone.utc)
    max_age = int(config.get("arxiv", {}).get("max_age_days", 14))
    cutoff = now - timedelta(days=max_age)

    arxiv_candidates, arxiv_errors = ([], []) if args.skip_arxiv else discover_arxiv(config, cutoff)
    highly_cited_candidates, highly_cited_errors, highly_cited_run_stats = (
        ([], [], highly_cited_stats())
        if args.skip_highly_cited
        else discover_highly_cited(config)
    )
    shared_candidates, shared_errors, shared_stats = (
        ([], [], {"matched_library_papers": 0, "unmatched_library_papers": 0})
        if args.skip_shared
        else discover_shared_references(graph, config, args.cache)
    )
    library_titles = {normalize_title(node["title"]) for node in graph.get("nodes", [])}
    threshold_papers = highly_cited_run_stats.pop("_highly_cited_threshold_papers", [])
    relevant_papers = highly_cited_run_stats.pop("_highly_cited_relevant_papers", [])
    highly_cited_library_matches = [
        paper for paper in threshold_papers
        if normalize_title(str(paper.get("title") or "")) in library_titles
    ]
    highly_cited_library_matches.sort(
        key=lambda paper: (-int(paper.get("cited_by_count") or 0), str(paper.get("title") or ""))
    )
    highly_cited_run_stats.update({
        "highly_cited_library_count": len(highly_cited_library_matches),
        "highly_cited_library_matches": highly_cited_library_matches[:20],
        "highly_cited_library_below_threshold_matches": [
            paper for paper in relevant_papers
            if normalize_title(str(paper.get("title") or "")) in library_titles
            and int(paper.get("cited_by_count") or 0)
            < int(config.get("highly_cited", {}).get("min_citations", 50))
        ][:20],
    })
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
        candidate.update(score_recommendation(candidate, graph, now))

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
            **highly_cited_run_stats,
            **shared_stats,
            "topic_profiles": topic_profiles,
        },
        "topics": enabled_topics,
        "decisions": previous.get("decisions", {}),
        "candidates": candidates,
    }
    write_discovery(output, args.output_json, args.output_js)
    debug_event(
        "discovery_finished",
        candidate_count=len(candidates),
        new_count=output["metadata"]["new_count"],
        error_count=len(output["metadata"]["errors"]),
        metadata={
            key: value for key, value in output["metadata"].items()
            if key.endswith("_count") and isinstance(value, (int, float))
        },
    )
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
